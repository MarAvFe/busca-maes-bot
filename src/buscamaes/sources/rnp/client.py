import asyncio
import logging
import re
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


class RNPClient:
    def __init__(self) -> None:
        self._session: httpx.AsyncClient | None = None
        self._logged_in = False
        self._lock = asyncio.Lock()
        settings = get_settings()
        self.email = settings.rnp_email
        self.password = settings.rnp_password
        self.timeout = settings.rnp_timeout

    async def query_plate(self, class_code: str, car_number: str) -> VehicleResult:
        """Query a vehicle plate. Ensures session is active. Retries once on expiry."""
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

    async def _ensure_session(self) -> None:
        """Lazy login: establish session if needed."""
        async with self._lock:
            if self._logged_in and self._session is not None:
                return
            await self._login()

    def _looks_like_login_page(self, resp: httpx.Response) -> bool:
        """Detect if response is a login page (expiry or forced re-auth)."""
        if resp.url.path.endswith("login.jspx"):
            return True
        return "correo" in resp.text.lower() and "pass" in resp.text.lower()

    async def _login(self) -> None:
        """Full login flow to RNP. Sets _logged_in=True on success."""
        if self._session is None:
            self._session = httpx.AsyncClient(timeout=self.timeout, follow_redirects=True)

        # Step 1: GET login page
        login_resp = await self._session.get(f"{BASE_URL}/shopping/login.jspx")
        login_resp.raise_for_status()
        viewstate = extract_viewstate(login_resp.text)
        form_id = extract_form_id(login_resp.text)
        # Extract j_id21 anti-bot hidden field from form
        j_id21_match = re.search(f'{form_id}:j_id21" [^>]*value="([^"]*)"', login_resp.text)
        j_id21 = j_id21_match.group(1) if j_id21_match else ""

        # Step 2: POST login (AJAX)
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
            f"{BASE_URL}/shopping/login.jspx",
            data=login_data,
        )
        login_post.raise_for_status()

        # Check if login succeeded: auth cookie is the source of truth
        if "TSf1c497e2027" not in self._session.cookies:
            if "Datos incorrectos" in login_post.text:
                raise RuntimeError("invalid credentials")
            raise RuntimeError("login blocked")

        self._logged_in = True
        logger.info("RNP login successful")

    async def _do_query(self, class_code: str, car_number: str) -> VehicleResult:
        """Execute the plate query after session is established."""
        if self._session is None:
            raise RuntimeError("Session not initialized")

        # Step 1: GET indiceDocumentos.jspx (navigate to free queries)
        idx_resp = await self._session.get(
            f"{BASE_URL}/shopping/consultaDocumentos/indiceDocumentos.jspx"
        )
        idx_resp.raise_for_status()
        idx_viewstate = extract_viewstate(idx_resp.text)
        idx_form_id = extract_form_id(idx_resp.text)
        # Extract button ID: j_id335 is just a button name
        j_id335 = f"{idx_form_id}:j_id335"

        # Step 2: POST to navigate to vehicle query form
        nav_data = {
            f"{idx_form_id}": idx_form_id,
            "javax.faces.ViewState": idx_viewstate,
            j_id335: j_id335,
        }
        nav_resp = await self._session.post(
            f"{BASE_URL}/shopping/consultaDocumentos/indiceDocumentos.jspx",
            data=nav_data,
        )
        nav_resp.raise_for_status()

        # Step 3: GET paramConsultaVehiculo.jspx
        param_resp = await self._session.get(
            f"{BASE_URL}/shopping/consultaDocumentos/paramConsultaVehiculo.jspx"
        )
        param_resp.raise_for_status()
        param_viewstate = extract_viewstate(param_resp.text)
        param_argus = extract_argus(param_resp.text)

        # Step 4: POST plate query
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
            f"{BASE_URL}/shopping/consultaDocumentos/paramConsultaVehiculo.jspx",
            data=query_data,
        )
        query_resp.raise_for_status()

        # Step 5: GET results page
        result_resp = await self._session.get(
            f"{BASE_URL}/shopping/consultaDocumentos/RespConsultaVehiculo.jspx"
        )
        result_resp.raise_for_status()

        vehicle = parse_vehicle(result_resp.text)
        vehicle.placa = f"{class_code} {car_number}".upper()

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
