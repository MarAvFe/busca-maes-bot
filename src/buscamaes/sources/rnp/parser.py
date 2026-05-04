import re

from bs4 import BeautifulSoup

from .models import VehicleResult


def extract_viewstate(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    inp = soup.find("input", {"name": "javax.faces.ViewState"})
    if inp and inp.get("value"):
        return str(inp["value"])
    raise ValueError("ViewState not found in HTML")


def extract_form_id(html: str, anchor: str = "params") -> str:
    soup = BeautifulSoup(html, "lxml")
    forms = soup.find_all("form")
    for form in forms:
        form_id = form.get("id")
        if form_id and anchor in form_id.lower():
            return str(form_id)
    if forms and forms[0].get("id"):
        return str(forms[0]["id"])
    raise ValueError(f"Form with anchor '{anchor}' not found")


def extract_argus(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    inp = soup.find("input", {"name": "params:argus"})
    if inp and inp.get("value"):
        return str(inp["value"])
    raise ValueError("argus token not found in HTML")


def parse_vehicle(html: str) -> VehicleResult:
    soup = BeautifulSoup(html, "lxml")
    result = VehicleResult()

    # Extract text from <td> pairs: label → value pattern
    tds = soup.find_all("td")
    text_map = {}
    for i in range(0, len(tds) - 1, 2):
        label = tds[i].get_text(strip=True).lower()
        value = tds[i + 1].get_text(strip=True)
        text_map[label] = value

    # Map extracted text to result fields
    mapping = {
        "placa": "placa",
        "marca": "marca",
        "estilo": "estilo",
        "categoría": "categoria",
        "año fabricación": "año_fabricacion",
        "color": "color",
        "estado actual": "estado_actual",
        "estado tributario": "estado_tributario",
        "valor hacienda": "valor_hacienda",
        "valor contrato": "valor_contrato",
        "# de serie / chasis / vin": "serie_vin",
        "propietario": "propietario_id",  # Will extract ID separately
        "motor": "motor",
        "inscripción": "inscripcion_fecha",
        "gravámenes": "gravamenes",
        "anotaciones": "anotaciones",
        "infracciones": "infracciones",
    }

    for label_pattern, field_name in mapping.items():
        for html_label, value in text_map.items():
            if label_pattern in html_label:
                setattr(result, field_name, value)
                break

    # Extract cilindrada from motor string if present
    if result.motor:
        match = re.search(r"(\d+)\s*c\.c\.", result.motor, re.IGNORECASE)
        if match:
            result.cilindrada_cc = match.group(1)

    # Extract propietario ID and name from text like "CEDULA 110350386 — NOMBRE"
    if "propietario" in text_map:
        prop_text = text_map["propietario"]
        prop_match = re.search(r"cedula\s+(\d+)\s*—?\s*(.*)", prop_text, re.IGNORECASE)
        if prop_match:
            result.propietario_id = prop_match.group(1)
            result.propietario_nombre = prop_match.group(2).strip()
        else:
            result.propietario_id = prop_text

    return result
