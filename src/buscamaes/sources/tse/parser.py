import re

from bs4 import BeautifulSoup

from .models import PersonResult, SearchResult


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
        match = re.match(r"\\d+[-\u2013]\s*(\d+)\s+(.+)", text)
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
