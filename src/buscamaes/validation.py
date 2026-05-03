import re
import unicodedata


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


def sanitize_user_error(exc: Exception) -> str:
    """Map exceptions to safe user-facing Spanish error messages.

    Never expose tracebacks or internal details to users.
    """
    msg = str(exc).lower()

    if isinstance(exc, ValueError):
        return str(exc)

    if "timeout" in msg or "connection" in msg:
        return "No se pudo conectar con el TSE. Intentá de nuevo más tarde."

    if "http" in msg or "status" in msg:
        return "El TSE no respondió correctamente. Intentá de nuevo."

    return "Ocurrió un error inesperado. Por favor, intentá de nuevo."
