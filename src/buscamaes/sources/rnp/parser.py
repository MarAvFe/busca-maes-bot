import re

from bs4 import BeautifulSoup, Tag

from .models import VehicleResult


def extract_viewstate(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    inp = soup.find("input", {"name": "javax.faces.ViewState"})
    if isinstance(inp, Tag) and inp.get("value"):
        return str(inp["value"])
    raise ValueError("ViewState not found in HTML")


def extract_form_id(html: str, anchor: str = "params", contains: str | None = None) -> str:
    soup = BeautifulSoup(html, "lxml")
    for form in soup.find_all("form"):
        form_id = form.get("id")
        if not form_id:
            continue
        if contains:
            inp = form.find("input", {"name": lambda x: x and contains in x})
            if inp:
                return str(form_id)
        elif (anchor and anchor in form_id.lower()) or not anchor:
            return str(form_id)
    if contains:
        raise ValueError(f"Form containing input '{contains}' not found")
    raise ValueError(f"Form with anchor '{anchor}' not found")


def extract_argus(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    inp = soup.find("input", {"name": "params:argus"})
    if isinstance(inp, Tag) and inp.get("value"):
        return str(inp["value"])
    raise ValueError("argus token not found in HTML")


def parse_vehicle(html: str) -> VehicleResult:
    soup = BeautifulSoup(html, "lxml")
    result = VehicleResult()
    text = soup.get_text(separator=" ", strip=True)

    known_labels = {
        "Tomo",
        "Asiento",
        "Secuencia",
        "Fecha",
        "Marca",
        "Estilo",
        "Categoría",
        "Capacidad",
        "# de Serie",
        "# de VIN",
        "# de Chasis",
        "Peso Vacio",
        "Peso Neto",
        "Carroceria",
        "Tracción",
        "PBV",
        "Longitud",
        "Año Fabricación",
        "Estado Actual",
        "Estado Tributario",
        "Clase Tributaria",
        "Uso",
        "Peso Remolque",
        "Valor Contrato",
        "Valor Hacienda",
        "Color",
        "Convertido",
        "Moneda",
        "N.Motor",
        "Modelo",
        "Cilindrada",
        "Cilindros",
        "Potencia",
        "Combustible",
        "Fabricante",
        "Procedencia",
        "Cabina",
        "Techo",
        "Numero registral",
    }

    def extract_field(label: str, max_length: int = 50) -> str:
        label_escaped = re.escape(label)
        lookahead = "|".join(re.escape(lb) for lb in known_labels if lb != label)
        pattern = rf"{label_escaped}:\s*(.+?)(?={lookahead}:\s|$)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value.upper() != "NO INDICADO":
                return value[:max_length]
        return ""

    result.marca = extract_field("Marca")
    result.estilo = extract_field("Estilo", max_length=50)
    result.categoria = extract_field("Categoría", max_length=50)
    result.año_fabricacion = extract_field("Año Fabricación")
    result.valor_contrato = extract_field("Valor Contrato", max_length=20)

    cilindrada_text = extract_field("Cilindrada", max_length=10)
    if cilindrada_text:
        match = re.search(r"([\d,]+(?:\.\d+)?)\s*", cilindrada_text)
        if match:
            result.cilindrada_cc = match.group(1).replace(",", "")

    cedula_match = re.search(
        r"CEDULA\s+DE\s+IDENTIDAD\s+(\d+)\s+(.+?)"
        r"(?=\s+(?:No Posee|Emitido|Todos los derechos|Procesando|Si Posee|"
        r"Ver Persona|Tomo)|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if cedula_match:
        result.propietario_id = cedula_match.group(1)
        result.propietario_nombre = cedula_match.group(2).strip()[:80]

    return result
