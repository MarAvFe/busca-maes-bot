import re
import logging
from urllib.parse import unquote
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE = "https://servicioselectorales.tse.go.cr/chc"
TSE_SEARCH_URL = "https://servicioselectorales.tse.go.cr/chc/consulta_nombres.aspx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Accept-Language": "es-CR,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class SearchResult:
    index: int       # 0-based position → used as chk1$N
    cedula: str
    nombre: str
    fallecido: bool = False


@dataclass
class SearchSession:
    muestra_url: str
    viewstate: dict
    cookies: dict[str, str]
    results: list[SearchResult]      # alive results only (fallecidos filtered)
    total_raw: int                   # total count before filter


@dataclass
class PersonResult:
    cedula: str = ""
    nombre: str = ""
    conocido_como: str = ""
    fecha_nacimiento: str = ""
    edad: str = ""
    nacionalidad: str = ""
    padre: str = ""
    madre: str = ""


def _extract_viewstate(soup: BeautifulSoup) -> dict:
    def val(name):
        tag = soup.find("input", {"name": name})
        return tag["value"] if tag else ""

    return {
        "__VIEWSTATE": val("__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": val("__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": val("__EVENTVALIDATION"),
        "__LASTFOCUS": "",
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
    }


def _parse_delta(delta: str) -> dict[str, str]:
    """Parse ASP.NET ScriptManager partial-page update delta response.

    Format: length|type|id|content| repeated.
    """
    result: dict[str, str] = {}
    i = 0
    while i < len(delta):
        pipe1 = delta.find("|", i)
        if pipe1 == -1:
            break
        length_str = delta[i:pipe1]
        try:
            length = int(length_str)
        except ValueError:
            break

        pipe2 = delta.find("|", pipe1 + 1)
        if pipe2 == -1:
            break
        type_ = delta[pipe1 + 1 : pipe2]

        pipe3 = delta.find("|", pipe2 + 1)
        if pipe3 == -1:
            break
        id_ = delta[pipe2 + 1 : pipe3]

        content_start = pipe3 + 1
        content = delta[content_start : content_start + length]
        result[f"{type_}:{id_}"] = content

        i = content_start + length + 1  # +1 skips trailing |

    return result


def _parse_results_list(soup: BeautifulSoup) -> tuple[list[SearchResult], int]:
    """Extract all result items from muestra_nombres.aspx.

    Returns (results, total_raw) where total_raw includes fallecidos.
    Items are radio/checkbox inputs named chk1$N. Label text format:
        "N- CEDULA   FULL NAME" or "N- CEDULA   FULL NAME (FALLECIDO)"
    """
    results: list[SearchResult] = []

    for inp in soup.find_all("input", type=lambda t: t in ("radio", "checkbox")):
        name = inp.get("name", "")
        parts = name.split("$")
        if len(parts) != 2 or not parts[1].isdigit():
            continue

        idx = int(parts[1])
        label = soup.find("label", {"for": inp.get("id", "")})
        if not label:
            continue

        text = label.get_text(strip=True)
        match = re.match(r"\d+[-–]\s*(\d+)\s+(.+)", text)
        if not match:
            continue

        cedula = match.group(1).strip()
        nombre = match.group(2).strip()
        fallecido = bool(re.search(r"\bFALLECID[OA]\b", nombre, re.IGNORECASE))
        if fallecido:
            nombre = re.sub(r"\s*\(?\bFALLECID[OA]\b\)?", "", nombre, flags=re.IGNORECASE).strip()

        results.append(SearchResult(index=idx, cedula=cedula, nombre=nombre, fallecido=fallecido))

    total_raw = len(results)
    return results, total_raw


def _parse_resultado(soup: BeautifulSoup) -> PersonResult | None:
    # resultado_persona.aspx has 4-column rows: label, value, label, value.
    mapping = {
        "número de cédula": "cedula",
        "nombre completo": "nombre",
        "conocido/a como": "conocido_como",
        "fecha nacimiento": "fecha_nacimiento",
        "edad": "edad",
        "nacionalidad": "nacionalidad",
        "hijo/a de": "padre",
        "y": "madre",
    }

    result = PersonResult()
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        pairs = []
        if len(cells) >= 2:
            pairs.append((cells[0], cells[1]))
        if len(cells) >= 4:
            pairs.append((cells[2], cells[3]))

        for label_cell, value_cell in pairs:
            label = label_cell.get_text(strip=True).rstrip(":").rstrip(" ").lower()
            value = value_cell.get_text(strip=True)
            attr = mapping.get(label)
            if attr:
                setattr(result, attr, value)

    if not result.cedula and not result.nombre:
        return None
    return result


async def _do_search(
    client: httpx.AsyncClient, nombre: str, apellido1: str, apellido2: str
) -> tuple[str, BeautifulSoup] | None:
    """Steps 1-3: search and load the muestra_nombres page.

    Returns (muestra_url, soup) or None if no results.
    """
    resp = await client.get(f"{BASE}/consulta_nombres.aspx")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    vs = _extract_viewstate(soup)

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
    logger.debug("Delta keys: %s", list(delta.keys()))

    redirect_path = delta.get("pageRedirect:", "")
    if not redirect_path:
        return None

    muestra_url = f"https://servicioselectorales.tse.go.cr{unquote(redirect_path)}"
    resp = await client.get(muestra_url, headers={**HEADERS, "Referer": f"{BASE}/consulta_nombres.aspx"})
    resp.raise_for_status()

    return muestra_url, BeautifulSoup(resp.text, "lxml")


def _exact_word_score(nombre_result: str, *terms: str) -> int:
    """Count how many search terms appear as whole words in the result name.

    "mora" scores a hit in "JUAN MORA FERNANDEZ" but not in "JUAN MORALES FERNANDEZ".
    """
    text = nombre_result.lower()
    return sum(
        1 for t in terms
        if t and re.search(r"\b" + re.escape(t.lower()) + r"\b", text)
    )


async def search_session(
    nombre: str, apellido1: str = "", apellido2: str = ""
) -> SearchSession | None:
    """Search by name and return the full result list without selecting anyone.

    The caller uses the returned SearchSession to either auto-select (single
    result) or present choices to the user, then call select_from_session().
    """
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        found = await _do_search(client, nombre, apellido1, apellido2)
        if not found:
            return None

        muestra_url, soup = found
        vs = _extract_viewstate(soup)
        all_results, total_raw = _parse_results_list(soup)

        alive = [r for r in all_results if not r.fallecido]
        alive.sort(key=lambda r: _exact_word_score(r.nombre, nombre, apellido1, apellido2), reverse=True)

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
