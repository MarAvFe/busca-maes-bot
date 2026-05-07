import asyncio
import logging
import re
import time
from enum import Enum
from typing import TYPE_CHECKING

import httpx

from ...settings import get_settings
from .models import VehicleResult
from .parser import extract_argus, extract_form_id, extract_viewstate, parse_vehicle

if TYPE_CHECKING:
    from typing import Optional
else:
    Optional = None

logger = logging.getLogger(__name__)

BASE_URL = "https://www.rnpdigital.com"

_rnp_client_instance: "RNPClient | None" = None


class RNPUnavailable(Exception):
    """RNP is temporarily unavailable (rate limited or circuit open)."""

    pass


class BreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RNPClient:
    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self._session: httpx.AsyncClient | None = None
        self._logged_in = False
        self._lock = asyncio.Lock()
        settings = get_settings()
        self.email = email if email is not None else settings.rnp_email
        self.password = password if password is not None else settings.rnp_password
        self.base_url = base_url if base_url is not None else settings.rnp_base_url
        self.timeout = timeout if timeout is not None else settings.rnp_timeout
        # Throttle: sliding window 120s, max 8 requests
        self._request_times: list[float] = []
        self._throttle_lock = asyncio.Lock()
        self._throttle_window = 120.0
        self._throttle_max = 8
        # Circuit breaker: trip after 3 login blocks in 10 min
        self._breaker_state = BreakerState.CLOSED
        self._breaker_failures: list[float] = []
        self._breaker_open_time: float | None = None
        self._breaker_failure_window = 600.0
        self._breaker_failure_threshold = 3
        self._breaker_cooloff = 1800.0

    async def query_plate(self, class_code: str, car_number: str) -> VehicleResult:
        """Query a vehicle plate. Ensures session is active. Retries once on expiry.

        Raises RNPUnavailable if breaker is open or throttle exhausted.
        """
        # Check breaker before attempting anything
        if not await self._check_breaker():
            raise RNPUnavailable("RNP temporarily unavailable")

        await self._ensure_session()
        try:
            return await self._do_query(class_code, car_number)
        except ValueError as e:
            if "not found in HTML" in str(e):
                logger.info("Session expired, re-logging in and retrying")
                self._logged_in = False
                await self._ensure_session()
                return await self._do_query(class_code, car_number)
            raise
        except RuntimeError as e:
            if "login blocked" in str(e):
                await self._record_breaker_failure()
            raise

    async def _throttle_acquire(self) -> None:
        """Acquire a throttle slot (8 req / 120s). Raises RNPUnavailable if exhausted."""
        async with self._throttle_lock:
            now = time.monotonic()
            self._request_times = [
                t for t in self._request_times if now - t < self._throttle_window
            ]
            if len(self._request_times) >= self._throttle_max:
                raise RNPUnavailable("Rate limit exceeded")
            self._request_times.append(now)
            logger.debug("Throttle: %d/%d slots used", len(self._request_times), self._throttle_max)

    async def _check_breaker(self) -> bool:
        """Check breaker. Returns False if open, True if closed/half-open."""
        now = time.monotonic()
        if self._breaker_state == BreakerState.CLOSED:
            return True
        if self._breaker_state == BreakerState.OPEN:
            if self._breaker_open_time is None:
                return False
            if now - self._breaker_open_time >= self._breaker_cooloff:
                logger.info("Breaker: open → half_open (cooloff expired)")
                self._breaker_state = BreakerState.HALF_OPEN
                return True
            return False
        return self._breaker_state == BreakerState.HALF_OPEN

    async def _record_breaker_failure(self) -> None:
        """Record a login block failure. Trip if threshold exceeded."""
        now = time.monotonic()
        self._breaker_failures = [
            t for t in self._breaker_failures if now - t < self._breaker_failure_window
        ]
        self._breaker_failures.append(now)
        if len(self._breaker_failures) >= self._breaker_failure_threshold:
            logger.warning(
                "Breaker: login blocks exceed threshold (%d), opening circuit",
                self._breaker_failure_threshold,
            )
            self._breaker_state = BreakerState.OPEN
            self._breaker_open_time = now
        else:
            logger.debug(
                "Breaker: recorded failure (%d/%d)",
                len(self._breaker_failures),
                self._breaker_failure_threshold,
            )

    async def _ensure_session(self) -> None:
        """Lazy login: establish session if needed."""
        async with self._lock:
            if self._logged_in and self._session is not None:
                return
            await self._login()

    def _looks_like_login_page(self, resp: httpx.Response) -> bool:
        """Detect if response is a login page (expiry or forced re-auth)."""
        if "login.jspx" in resp.url.path:
            return True
        return "correo" in resp.text.lower() and "pass" in resp.text.lower()

    async def _login(self) -> None:
        """Full login flow to RNP. Sets _logged_in=True on success."""
        if self._session is None:
            self._session = httpx.AsyncClient(timeout=self.timeout, follow_redirects=True)

        # Step 1: GET login page
        await self._throttle_acquire()
        login_resp = await self._session.get(f"{self.base_url}/shopping/login.jspx")
        login_resp.raise_for_status()
        viewstate = extract_viewstate(login_resp.text)
        form_id = extract_form_id(login_resp.text, contains=":correo")
        j_id21_match = re.search(f'{form_id}:j_id21" [^>]*value="([^"]*)"', login_resp.text)
        j_id21 = j_id21_match.group(1) if j_id21_match else ""

        # Step 2: POST login (AJAX)
        await self._throttle_acquire()
        login_data = {
            "AJAXREQUEST": "_viewRoot",
            f"{form_id}": form_id,
            f"{form_id}:j_id21": j_id21,
            f"{form_id}:correo": self.email,
            f"{form_id}:pass": self.password,
            "javax.faces.ViewState": viewstate,
            f"{form_id}:j_id29": f"{form_id}:j_id29",
        }
        login_post = await self._session.post(
            f"{self.base_url}/shopping/login.jspx",
            data=login_data,
        )
        login_post.raise_for_status()

        if "Datos incorrectos" in login_post.text:
            raise RuntimeError("invalid credentials")

        # Step 3: Probe protected page to verify login succeeded (only behavioural truth)
        await self._throttle_acquire()
        probe_resp = await self._session.get(
            f"{self.base_url}/shopping/consultaDocumentos/indiceDocumentos.jspx"
        )
        probe_resp.raise_for_status()

        if self._looks_like_login_page(probe_resp):
            logger.warning("Login failed — probe redirected to login page")
            raise RuntimeError("login blocked")

        self._logged_in = True
        logger.info("RNP login successful")

    async def _do_query(self, class_code: str, car_number: str) -> VehicleResult:
        """Execute the plate query after session is established."""
        if self._session is None:
            raise RuntimeError("Session not initialized")

        # Step 1: GET paramConsultaVehiculo.jspx (direct — no nav step needed)
        await self._throttle_acquire()
        param_resp = await self._session.get(
            f"{self.base_url}/shopping/consultaDocumentos/paramConsultaVehiculo.jspx"
        )
        param_resp.raise_for_status()
        param_viewstate = extract_viewstate(param_resp.text)
        param_argus = extract_argus(param_resp.text)

        # Step 2: POST plate query
        await self._throttle_acquire()
        query_data = {
            "params": "params",
            "params:j_id273": "PLA",
            "class": class_code,
            "code": " ",
            "carNumber": car_number,
            "params:argus": param_argus,
            "javax.faces.ViewState": param_viewstate,
            "params:j_id315": "params:j_id315",
            "numeroConsulta": "26",
            "nombreConsulta": "Consulta de Vehículo por Placa",
            "error": "",
        }
        query_resp = await self._session.post(
            f"{self.base_url}/shopping/consultaDocumentos/paramConsultaVehiculo.jspx",
            data=query_data,
        )
        query_resp.raise_for_status()

        # Step 3: GET results page
        await self._throttle_acquire()
        result_resp = await self._session.get(
            f"{self.base_url}/shopping/consultaDocumentos/RespConsultaVehiculo.jspx"
        )
        result_resp.raise_for_status()

        vehicle = parse_vehicle(result_resp.text)
        vehicle.placa = f"{class_code} {car_number}".upper()

        if self._breaker_state == BreakerState.HALF_OPEN:
            logger.info("Breaker: half_open → closed (probe succeeded)")
            self._breaker_state = BreakerState.CLOSED
            self._breaker_failures.clear()

        return vehicle

    async def close(self) -> None:
        """Close the session."""
        if self._session:
            await self._session.aclose()
            self._session = None
            self._logged_in = False


def get_rnp_client() -> RNPClient:
    global _rnp_client_instance
    if _rnp_client_instance is None:
        _rnp_client_instance = RNPClient()
    return _rnp_client_instance


def reset_rnp_client() -> None:
    """Reset the RNP client singleton. Only for testing."""
    import asyncio
    from contextlib import suppress

    global _rnp_client_instance
    if _rnp_client_instance is not None:
        with suppress(RuntimeError):
            asyncio.run(_rnp_client_instance.close())
    _rnp_client_instance = None
