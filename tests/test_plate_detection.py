"""Unit tests for plate detection and normalization."""

import pytest

from buscamaes.validation import detect_plate


class TestPlateDetection:
    """Test each plate regex pattern and edge cases."""

    @pytest.mark.parametrize(
        "text,expected_class,expected_number",
        [
            # AUT: 6 digits
            ("621335", "AUT", "621335"),
            ("000000", "AUT", "000000"),
            ("999999", "AUT", "999999"),
            # AUT: 3 letters + 3 digits
            ("BJV123", "AUT", "BJV123"),
            ("AAA000", "AUT", "AAA000"),
            # CL: CL + 6 digits
            ("CL123456", "CL", "123456"),
            ("CL000000", "CL", "000000"),
            # MOT: M + 6 digits
            ("M123456", "MOT", "123456"),
            ("M000000", "MOT", "000000"),
            # MOT: MOT + 6 digits
            ("MOT621335", "MOT", "621335"),
            ("MOT000000", "MOT", "000000"),
            # MOT: M + 3 digits + 3 letters
            ("M123ABC", "MOT", "123ABC"),
            ("M000ZZZ", "MOT", "000ZZZ"),
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
            "12345",  # 5 digits
            "M12345",  # M + 5 digits
            "MOT12345",  # MOT + 5 digits
            "CL12345",  # CL + 5 digits
            "M123AB",  # M + 3 digits + 2 letters
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
