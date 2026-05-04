"""Unit tests for vehicle formatting and Markdown safety."""

import pytest

from buscamaes.bot.formatting import _escape_markdown, _format_vehicle
from buscamaes.sources.rnp import VehicleResult


class TestEscapeMarkdown:
    """Test Markdown escaping."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("hello world", "hello world"),
            ("hello*world", r"hello\*world"),
            ("test_under", r"test\_under"),
            ("test[bracket", r"test\[bracket"),
            ("test(paren", r"test\(paren"),
            ("test+plus", r"test\+plus"),
            ("multiple*special_chars[here]", r"multiple\*special\_chars\[here\]"),
        ],
    )
    def test_escapes_special_chars(self, text, expected):
        result = _escape_markdown(text)
        assert result == expected

    def test_handles_empty_string(self):
        result = _escape_markdown("")
        assert result == ""


class TestFormatVehicle:
    """Test vehicle formatting."""

    def test_formats_complete_vehicle(self):
        vehicle = VehicleResult(
            placa="BJV 123",
            categoria="Automóvil",
            marca="TOYOTA",
            estilo="COROLLA",
            año_fabricacion="2020",
            cilindrada_cc="1600",
            valor_contrato="5,000,000",
            propietario_id="110350386",
            propietario_nombre="JUAN MORA",
        )
        result = _format_vehicle(vehicle)
        assert "*BJV 123*" in result
        assert "Automóvil TOYOTA COROLLA" in result
        assert "(2020)" in result
        assert "1600 cc" in result
        assert "₡ 5,000,000" in result
        assert "(110350386) JUAN MORA" in result

    def test_formats_partial_vehicle(self):
        vehicle = VehicleResult(
            placa="ABC 456",
            categoria="",
            marca="HONDA",
            estilo="",
            año_fabricacion="2019",
        )
        result = _format_vehicle(vehicle)
        assert "*ABC 456*" in result
        assert "(2019)" in result
        # Missing categoria/estilo/marca combo should be skipped
        assert "Sin datos." not in result

    def test_empty_vehicle_returns_sin_datos(self):
        vehicle = VehicleResult()
        result = _format_vehicle(vehicle)
        assert result == "Sin datos."

    def test_propietario_without_nombre(self):
        vehicle = VehicleResult(
            placa="BJV 123",
            propietario_id="123456",
            propietario_nombre="",
        )
        result = _format_vehicle(vehicle)
        assert "*BJV 123*" in result
        assert "(123456)" in result

    def test_escapes_marca_with_special_chars(self):
        vehicle = VehicleResult(
            placa="AUX 001",
            categoria="Auto",
            marca="BMW (M-SERIES)",
            estilo="SEDAN",
        )
        result = _format_vehicle(vehicle)
        # Special chars should be escaped
        assert r"BMW \(M\-SERIES\)" in result

    def test_separators_in_output(self):
        vehicle = VehicleResult(
            placa="ABC 123",
            categoria="Auto",
            marca="FORD",
            estilo="FUSION",
            año_fabricacion="2021",
        )
        result = _format_vehicle(vehicle)
        # Should use · as separator
        assert " · " in result
