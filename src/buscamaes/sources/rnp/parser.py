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
    for form in soup.find_all("form"):
        form_id = form.get("id")
        if form_id and anchor in form_id.lower():
            return str(form_id)
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

    # Row-driven extraction: first cell is label, remaining cells are value
    text_map: dict[str, str] = {}
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True).lower()
            value = " ".join(c.get_text(strip=True) for c in cells[1:]).strip()
            if label and value:
                text_map[label] = value

    mapping = {
        "placa": "placa",
        "marca": "marca",
        "estilo": "estilo",
        "categoría": "categoria",
        "año fabricación": "año_fabricacion",
        "valor contrato": "valor_contrato",
    }

    for label_pattern, field_name in mapping.items():
        for html_label, value in text_map.items():
            if label_pattern in html_label:
                setattr(result, field_name, value)
                break

    # Extract cilindrada from motor string if present
    motor_value = next((v for k, v in text_map.items() if "motor" in k), "")
    if motor_value:
        match = re.search(r"(\d+)\s*c\.c\.", motor_value, re.IGNORECASE)
        if match:
            result.cilindrada_cc = match.group(1)

    # Extract propietario ID and name from text like "CEDULA 110350386 — NOMBRE"
    prop_text = next((v for k, v in text_map.items() if "propietario" in k), "")
    if prop_text:
        prop_match = re.search(r"cedula\s+(\d+)\s*[—-]?\s*(.*)", prop_text, re.IGNORECASE)
        if prop_match:
            result.propietario_id = prop_match.group(1)
            result.propietario_nombre = prop_match.group(2).strip()
        else:
            result.propietario_id = prop_text

    return result
