import logging
from urllib.parse import unquote
import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

BASE = "https://servicioselectorales.tse.go.cr/chc"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Accept-Language": "es-CR,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


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


def _parse_resultado(soup: BeautifulSoup) -> PersonResult | None:
    # resultado_persona.aspx has 4-column rows: label, value, label, value.
    # Labels end with " :" or ":".
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
    parent_index = 0  # first "hijo/a de" = padre, "y" = madre

    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        # Process pairs: (cells[0], cells[1]) and (cells[2], cells[3])
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


async def search_person(
    nombre: str, apellido1: str = "", apellido2: str = ""
) -> PersonResult | None:
    async with httpx.AsyncClient(
        headers=HEADERS, follow_redirects=True, timeout=30
    ) as client:
        # Step 1: Load the search form to get fresh ViewState tokens
        resp = await client.get(f"{BASE}/consulta_nombres.aspx")
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        vs = _extract_viewstate(soup)

        # Step 2: Submit AJAX search
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

        # The delta response redirects the browser to muestra_nombres.aspx.
        # The redirect path is in the pageRedirect entry (empty id).
        redirect_path = delta.get("pageRedirect:", "")
        if not redirect_path:
            logger.info("No pageRedirect in delta — no results found")
            return None

        muestra_url = f"https://servicioselectorales.tse.go.cr{unquote(redirect_path)}"
        logger.debug("Redirect to: %s", muestra_url)

        # Step 3: Load the results list page
        resp = await client.get(
            muestra_url,
            headers={**HEADERS, "Referer": f"{BASE}/consulta_nombres.aspx"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        vs = _extract_viewstate(soup)

        # Step 4: Select the first result and submit
        resp = await client.post(
            muestra_url,
            data={
                **vs,
                "chk1$0": "on",
                "Button1": "Realizar consulta",
            },
            headers={**HEADERS, "Referer": muestra_url},
        )
        resp.raise_for_status()

        # After the 302 redirect, we land on resultado_persona.aspx
        soup = BeautifulSoup(resp.text, "lxml")
        return _parse_resultado(soup)
