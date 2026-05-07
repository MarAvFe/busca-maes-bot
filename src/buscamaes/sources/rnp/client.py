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
        # Throttle: sliding window 120s, max 15 requests
        self._request_times: list[float] = []
        self._throttle_lock = asyncio.Lock()
        self._throttle_window = 120.0
        self._throttle_max = 15
        # Circuit breaker: trip after 3 login blocks in 10 min
        self._breaker_state = BreakerState.CLOSED
        self._breaker_failures: list[float] = []
        self._breaker_open_time: float | None = None
        self._breaker_failure_window = 600.0
        self._breaker_failure_threshold = 3
        self._breaker_cooloff = 1800.0
        # Multi-query session state
        self._indice_viewstate: str | None = None
        self._result_viewstate: str | None = None
        self._param_argus: str | None = None

    async def query_plate(self, class_code: str, car_number: str) -> VehicleResult:
        """Query a vehicle plate. Ensures session is active. Retries once on expiry.

        Raises RNPUnavailable if breaker is open or throttle exhausted.
        """
        # Check breaker before attempting anything
        if not await self._check_breaker():
            raise RNPUnavailable("RNP temporarily unavailable")

        await self._ensure_session()
        try:
            result = await self._do_query(class_code, car_number)
            # _do_query returns empty VehicleResult (no marca) and resets _logged_in
            # when the POST body was empty (JSF state mismatch). Retry once with a
            # fresh session so the caller gets the correct result on this request.
            if not result.marca and not self._logged_in:
                await self._ensure_session()
                return await self._do_query(class_code, car_number)
            return result
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
        """Acquire a throttle slot (15 req / 120s). Raises RNPUnavailable if exhausted."""
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

        # Store ViewState from indiceDocumentos for first-query navigation
        try:
            self._indice_viewstate = extract_viewstate(probe_resp.text)
        except ValueError:
            self._indice_viewstate = None

        self._result_viewstate = None
        self._param_argus = None
        self._logged_in = True
        logger.info("RNP login successful")

    async def _navigate_to_param_page(self) -> tuple[str, str]:
        """Navigate to paramConsultaVehiculo, return (viewstate, argus)."""
        if self._result_viewstate is not None:
            return await self._reset_via_nueva_consulta()
        if self._indice_viewstate is not None:
            return await self._nav_from_indice(self._indice_viewstate)
        # Fallback: direct GET (shouldn't happen in normal flow)
        return await self._direct_get_param()

    async def _reset_via_nueva_consulta(self) -> tuple[str, str]:
        """POST Consultas Gratuitas AJAX → GET indice → POST nav to paramConsultaVehiculo."""
        result_vs = self._result_viewstate
        self._result_viewstate = None

        # POST "Consultas Gratuitas" (j_id53:j_id159) AJAX to RespConsultaVehiculo
        await self._throttle_acquire()
        ajax_resp = await self._session.post(  # type: ignore[union-attr]
            f"{self.base_url}/shopping/consultaDocumentos/RespConsultaVehiculo.jspx",
            data={
                "AJAXREQUEST": "_viewRoot",
                "j_id53": "j_id53",
                "javax.faces.ViewState": result_vs,
                "j_id53:j_id159": "j_id53:j_id159",
            },
        )

        # Parse AJAX redirect — <meta name="Location" content="...">
        loc_match = re.search(r'name="Location"\s+content="([^"]+)"', ajax_resp.text)
        redirect_path = (
            loc_match.group(1)
            if loc_match
            else "/shopping/consultaDocumentos/indiceDocumentos.jspx"
        )

        # GET indiceDocumentos
        await self._throttle_acquire()
        indice_resp = await self._session.get(  # type: ignore[union-attr]
            f"{self.base_url}{redirect_path}"
        )
        indice_resp.raise_for_status()
        indice_vs = extract_viewstate(indice_resp.text)

        return await self._nav_from_indice(indice_vs)

    async def _nav_from_indice(self, indice_vs: str) -> tuple[str, str]:
        """POST indiceDocumentos j_id267:j_id335 nav (follows 302) → return (viewstate, argus)."""
        self._indice_viewstate = None
        await self._throttle_acquire()
        nav_resp = await self._session.post(  # type: ignore[union-attr]
            f"{self.base_url}/shopping/consultaDocumentos/indiceDocumentos.jspx",
            data={
                "j_id267": "j_id267",
                "javax.faces.ViewState": indice_vs,
                "j_id267:j_id335": "j_id267:j_id335",
            },
        )
        nav_resp.raise_for_status()
        param_vs = extract_viewstate(nav_resp.text)
        if self._param_argus is None:
            self._param_argus = extract_argus(nav_resp.text)
        return param_vs, self._param_argus

    async def _direct_get_param(self) -> tuple[str, str]:
        """Fallback: direct GET paramConsultaVehiculo (used if indice state is missing)."""
        await self._throttle_acquire()
        resp = await self._session.get(  # type: ignore[union-attr]
            f"{self.base_url}/shopping/consultaDocumentos/paramConsultaVehiculo.jspx"
        )
        resp.raise_for_status()
        param_vs = extract_viewstate(resp.text)
        if self._param_argus is None:
            self._param_argus = extract_argus(resp.text)
        return param_vs, self._param_argus  # type: ignore[return-value]

    async def _do_query(self, class_code: str, car_number: str) -> VehicleResult:
        """Execute the plate query after session is established."""
        if self._session is None:
            raise RuntimeError("Session not initialized")

        param_viewstate, param_argus = await self._navigate_to_param_page()

        # Limpiar (AJAX form clear — same ViewState reused for actual query)
        await self._throttle_acquire()
        await self._session.post(
            f"{self.base_url}/shopping/consultaDocumentos/paramConsultaVehiculo.jspx",
            data={
                "AJAXREQUEST": "_viewRoot",
                "params": "params",
                "params:j_id273": "PLA",
                "class": " ",
                "carNumber": "",
                "params:argus": param_argus,
                "javax.faces.ViewState": param_viewstate,
                "params:limpiar": "params:limpiar",
            },
        )

        # Plate query — httpx follows 302 redirect to RespConsultaVehiculo
        await self._throttle_acquire()
        query_resp = await self._session.post(
            f"{self.base_url}/shopping/consultaDocumentos/paramConsultaVehiculo.jspx",
            data={
                "params": "params",
                "params:j_id273": "PLA",
                "class": " " if class_code == "AUT" else class_code,
                "code": " ",
                "carNumber": car_number,
                "params:argus": param_argus,
                "javax.faces.ViewState": param_viewstate,
                "params:j_id315": "params:j_id315",
                "numeroConsulta": "26",
                "nombreConsulta": "Consulta de Vehículo por Placa",
                "error": "",
            },
        )
        query_resp.raise_for_status()

        # Empty body = server rejected the query (JSF state mismatch).
        if not query_resp.text.strip():
            logger.info("Query returned empty body — resetting session")
            self._logged_in = False
            self._result_viewstate = None
            self._indice_viewstate = None
            self._param_argus = None
            return VehicleResult()

        # Store result page ViewState for next query's reset flow
        try:
            self._result_viewstate = extract_viewstate(query_resp.text)
        except ValueError:
            self._result_viewstate = None

        vehicle = parse_vehicle(query_resp.text)
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
            self._indice_viewstate = None
            self._result_viewstate = None
            self._param_argus = None


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
