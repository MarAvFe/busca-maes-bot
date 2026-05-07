import re
import unicodedata
from dataclasses import dataclass


def validate_name_query(query: str) -> str:
    """Validate and normalize name query.

    - NFKC normalization
    - Max 60 chars
    - Letters, space, hyphen only
    - Non-empty after strip
    """
    normalized = unicodedata.normalize("NFKC", query)
    normalized = normalized.strip()

    if not normalized:
        raise ValueError("La búsqueda no puede estar vacía.")

    if len(normalized) > 60:
        raise ValueError("La búsqueda es demasiado larga (máx 60 caracteres).")

    if not re.match(r"^[a-záéíóúñA-ZÁÉÍÓÚÑ\s\-]+$", normalized):
        raise ValueError("La búsqueda solo puede contener letras, espacios y guiones.")

    return normalized


@dataclass
class PlateQuery:
    class_code: str
    car_number: str
    raw: str


def detect_plate(text: str) -> PlateQuery | None:
    """Detect if text is a plate. Returns PlateQuery or None."""
    text = text.strip().upper()

    if not text or " " in text:
        return None

    patterns = [
        (r"^(\d{1,6})$", "AUT"),
        # Specific prefixes before generic 3-letter AUT to avoid collision (e.g. TAX123)
        (r"^(TSJ|TAX)(\d{1,6})$", None),
        (r"^(TA|TC|TG|TH|TL|TP|TE)(\d{1,6})$", None),
        (r"^([A-Z]{3})(\d{3})$", "AUT"),
        (r"^(CL)(\d{1,6})$", "CL"),
        (r"^(M)(\d{1,6})$", "MOT"),
        (r"^(MOT)(\d{1,6})$", "MOT"),
        (r"^(M)(\d{3})([A-Z]{3})$", "MOT"),
    ]

    for pattern, class_code in patterns:
        match = re.match(pattern, text)
        if match:
            groups = match.groups()
            if class_code == "AUT" and len(groups) == 1:
                car_number = groups[0]
            elif class_code == "AUT":
                car_number = groups[0] + groups[1]
            elif class_code is None:
                # Prefix is its own class code (e.g. taxis: TSJ, TA, TC…)
                class_code = groups[0]
                car_number = groups[1]
            else:
                car_number = "".join(groups[1:])
            return PlateQuery(class_code=class_code, car_number=car_number, raw=text)

    return None


def sanitize_user_error(exc: Exception) -> str:
    """Map exceptions to safe user-facing Spanish error messages.

    Never expose tracebacks or internal details to users.
    """
    from .sources.rnp import RNPUnavailable

    if isinstance(exc, RNPUnavailable):
        return "RNP no está disponible en este momento. Intentá más tarde."

    msg = str(exc).lower()

    if isinstance(exc, ValueError):
        return str(exc)

    if "timeout" in msg or "connection" in msg:
        return "No se pudo conectar con RNP. Intentá de nuevo más tarde."

    if "http" in msg or "status" in msg:
        return "RNP no respondió correctamente. Intentá de nuevo."

    if "login" in msg:
        return "Error de autenticación con RNP. Por favor reportar."

    return "Ocurrió un error inesperado. Por favor, intentá de nuevo."
