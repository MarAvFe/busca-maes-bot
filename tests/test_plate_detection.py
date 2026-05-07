"""Unit tests for plate detection and normalization."""

import pytest

from buscamaes.validation import detect_plate


class TestPlateDetection:
    """Test each plate regex pattern and edge cases."""

    @pytest.mark.parametrize(
        "text,expected_class,expected_number",
        [
            # AUT: 1–6 digits
            ("1", "AUT", "1"),
            ("123", "AUT", "123"),
            ("621335", "AUT", "621335"),
            # AUT: 3 letters + 3 digits
            ("BJV123", "AUT", "BJV123"),
            ("AAA000", "AUT", "AAA000"),
            # CL: CL + 1–6 digits
            ("CL1", "CL", "1"),
            ("CL123", "CL", "123"),
            ("CL12345", "CL", "12345"),
            ("CL123456", "CL", "123456"),
            # MOT: M + 1–6 digits
            ("M1", "MOT", "1"),
            ("M12345", "MOT", "12345"),
            ("M123456", "MOT", "123456"),
            # MOT: MOT + 1–6 digits
            ("MOT1", "MOT", "1"),
            ("MOT12345", "MOT", "12345"),
            ("MOT621335", "MOT", "621335"),
            # MOT: M + 3 digits + 3 letters
            ("M123ABC", "MOT", "123ABC"),
            # Taxis
            ("TSJ1234", "TSJ", "1234"),
            ("TSJ123456", "TSJ", "123456"),
            ("TAX123", "TAX", "123"),
            ("TA99", "TA", "99"),
            ("TC1", "TC", "1"),
            ("TG12345", "TG", "12345"),
            ("TH123456", "TH", "123456"),
            ("TL1", "TL", "1"),
            ("TP99", "TP", "99"),
            ("TE12345", "TE", "12345"),
        ],
    )
    def test_valid_plate_formats(self, text, expected_class, expected_number):
        result = detect_plate(text)
        assert result is not None
        assert result.class_code == expected_class
        assert result.car_number == expected_number
        assert result.raw == text.upper()

    @pytest.mark.parametrize(
        "text",
        [
            # Multi-word
            "621335 foo",
            "BJV 123",
            "CL 123456",
            # Invalid single word
            "abc",  # All letters
            "1234567",  # 7 digits (too many)
            "M123AB",  # M + 3 digits + 2 letters (not 3)
            "XYZ12",  # 3 letters + 2 digits (not 3)
            # Empty/whitespace
            "",
            "   ",
        ],
    )
    def test_invalid_plate_rejects(self, text):
        result = detect_plate(text)
        assert result is None

    def test_lowercase_normalization(self):
        result = detect_plate("bjv123")
        assert result is not None
        assert result.class_code == "AUT"
        assert result.car_number == "BJV123"

    def test_whitespace_strip(self):
        result = detect_plate("  621335  ")
        assert result is not None
        assert result.class_code == "AUT"
        assert result.car_number == "621335"

    def test_raw_preserves_input_case(self):
        result = detect_plate("bjv123")
        assert result.raw == "BJV123"
