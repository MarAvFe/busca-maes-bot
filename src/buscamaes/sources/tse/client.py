import logging
import re
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup

from .models import PersonResult, SearchSession
from .parser import _extract_viewstate, _parse_delta, _parse_resultado, _parse_results_list

logger = logging.getLogger(__name__)

BASE = "https://servicioselectorales.tse.go.cr/chc"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CR,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _exact_word_score(nombre_result: str, *terms: str) -> int:
    """Count how many search terms appear as whole words in the result name.

    "mora" scores a hit in "JUAN MORA FERNANDEZ" but not in "JUAN MORALES FERNANDEZ".
    """
    text = nombre_result.lower()
    return sum(1 for t in terms if t and re.search(r"\b" + re.escape(t.lower()) + r"\b", text))


async def _do_search(
    client: httpx.AsyncClient, nombre: str, apellido1: str, apellido2: str
) -> tuple[str, BeautifulSoup] | None:
    """Steps 1-3: search and load the muestra_nombres page.

    Returns (muestra_url, soup) or None if no results.
    """
    logger.debug(
        f"Starting TSE search: nombre={nombre!r}, apellido1={apellido1!r}, apellido2={apellido2!r}"
    )
    resp = await client.get(f"{BASE}/consulta_nombres.aspx")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    vs = _extract_viewstate(soup)
    logger.debug(f"Extracted viewstate keys: {list(vs.keys())}")

    resp = await client.post(
        f"{BASE}/consulta_nombres.aspx",
        data={
            "ScriptManager1": "UpdatePanel1|btnConsultarNombre",
            **vs,
            "txtnombre": nombre,
            "txtapellido1": apellido1,
            "txtapellido2": apellido2,
            "referencia": "",
            "observacion": "",
            "__ASYNCPOST": "true",
            "btnConsultarNombre": "Consultar",
        },
        headers={
            **HEADERS,
            "X-MicrosoftAjax": "Delta=true",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": f"{BASE}/consulta_nombres.aspx",
        },
    )
    resp.raise_for_status()

    delta = _parse_delta(resp.text)
    logger.debug(f"Delta keys: {list(delta.keys())}")

    redirect_path = delta.get("pageRedirect:", "")
    if not redirect_path:
        logger.info(f"No redirect found in delta for search: {nombre} {apellido1} {apellido2}")
        return None

    muestra_url = f"https://servicioselectorales.tse.go.cr{unquote(redirect_path)}"
    logger.debug(f"Fetching muestra_url: {muestra_url}")
    resp = await client.get(
        muestra_url, headers={**HEADERS, "Referer": f"{BASE}/consulta_nombres.aspx"}
    )
    resp.raise_for_status()
    logger.debug(f"Got muestra response, status={resp.status_code}")

    return muestra_url, BeautifulSoup(resp.text, "lxml")


async def search_session(
    nombre: str, apellido1: str = "", apellido2: str = ""
) -> SearchSession | None:
    """Search by name and return the full result list without selecting anyone."""
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        found = await _do_search(client, nombre, apellido1, apellido2)
        if not found:
            logger.warning(f"No search results found for: {nombre} {apellido1} {apellido2}")
            return None

        muestra_url, soup = found
        vs = _extract_viewstate(soup)
        all_results, total_raw = _parse_results_list(soup)
        logger.info(
            f"Parsed {len(all_results)} alive results (total_raw={total_raw}) "
            f"for {nombre} {apellido1} {apellido2}"
        )

        alive = [r for r in all_results if not r.fallecido]
        alive.sort(
            key=lambda r: _exact_word_score(r.nombre, nombre, apellido1, apellido2),
            reverse=True,
        )
        logger.debug(f"After filtering fallecidos and sorting: {len(alive)} alive results")

        return SearchSession(
            muestra_url=muestra_url,
            viewstate=vs,
            cookies=dict(client.cookies),
            results=alive,
            total_raw=total_raw,
        )


async def select_from_session(session: SearchSession, index: int) -> PersonResult | None:
    """POST to muestra_nombres selecting the item at position `index`."""
    async with httpx.AsyncClient(
        headers=HEADERS, follow_redirects=True, timeout=30, cookies=session.cookies
    ) as client:
        resp = await client.post(
            session.muestra_url,
            data={
                **session.viewstate,
                f"chk1${index}": "on",
                "Button1": "Realizar consulta",
            },
            headers={**HEADERS, "Referer": session.muestra_url},
        )
        resp.raise_for_status()
        return _parse_resultado(BeautifulSoup(resp.text, "lxml"))


async def search_person(
    nombre: str, apellido1: str = "", apellido2: str = ""
) -> PersonResult | None:
    """Convenience wrapper: search and auto-select the first alive result."""
    session = await search_session(nombre, apellido1, apellido2)
    if not session or not session.results:
        return None
    return await select_from_session(session, session.results[0].index)
