"""Unit tests for input validation and error sanitization."""

import httpx
import pytest

from buscamaes.validation import (
    sanitize_user_error,
    validate_name_query,
)

# ---------------------------------------------------------------------------
# validate_name_query
# ---------------------------------------------------------------------------


def test_accepts_simple_name():
    assert validate_name_query("Juan Mora") == "Juan Mora"


def test_strips_whitespace():
    assert validate_name_query("  Juan  ") == "Juan"


def test_rejects_empty():
    with pytest.raises(ValueError, match="vacía"):
        validate_name_query("   ")


def test_rejects_overlong():
    with pytest.raises(ValueError, match="larga"):
        validate_name_query("a" * 61)


def test_rejects_control_chars():
    with pytest.raises(ValueError, match="letras"):
        validate_name_query("Juan\x00Mora")


def test_rejects_digits():
    with pytest.raises(ValueError, match="letras"):
        validate_name_query("Juan123")


def test_accepts_accented_letters():
    assert validate_name_query("José Ñoño") == "José Ñoño"


# ---------------------------------------------------------------------------
# sanitize_user_error
# ---------------------------------------------------------------------------


def test_value_error_passes_through():
    msg = sanitize_user_error(ValueError("La búsqueda está vacía."))
    assert msg == "La búsqueda está vacía."


def test_timeout_returns_friendly_message():
    msg = sanitize_user_error(httpx.TimeoutException("connection timeout"))
    assert "más tarde" in msg


def test_generic_exception_returns_safe_default():
    msg = sanitize_user_error(RuntimeError("internal traceback details"))
    assert "internal traceback" not in msg
    assert "inesperado" in msg
