"""Unit tests for input validation and error sanitization."""

import httpx
import pytest

from buscamaes.validation import (
    detect_plate,
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


# ---------------------------------------------------------------------------
# detect_plate
# ---------------------------------------------------------------------------


def test_detects_short_numeric_plates():
    """Test that numeric plates with 1-6 digits are accepted."""
    plate = detect_plate("123")
    assert plate is not None
    assert plate.class_code == "AUT"
    assert plate.car_number == "123"
    assert plate.raw == "123"


def test_detects_short_and_long_numeric_plates():
    """Test range of numeric plate lengths."""
    for digits in ["1", "12", "123", "1234", "12345", "123456"]:
        plate = detect_plate(digits)
        assert plate is not None, f"Failed for {digits}"
        assert plate.class_code == "AUT"
        assert plate.car_number == digits


def test_rejects_numeric_plates_over_6_digits():
    """Test that numeric plates > 6 digits are rejected."""
    plate = detect_plate("1234567")
    assert plate is None


def test_detects_alphanumeric_plates_still_require_exact_format():
    """Test that letter-based plates still enforce their exact formats."""
    # 3-letter + 3-digit (still valid)
    plate = detect_plate("BJV123")
    assert plate is not None
    assert plate.class_code == "AUT"

    # CL + 6-digit (cargo)
    plate = detect_plate("CL123456")
    assert plate is not None
    assert plate.class_code == "CL"

    # MOT + 6-digit
    plate = detect_plate("MOT123456")
    assert plate is not None
    assert plate.class_code == "MOT"
