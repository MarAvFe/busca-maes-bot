"""Unit tests for RNP HTML parser."""

import pytest

from buscamaes.sources.rnp.parser import (
    extract_argus,
    extract_form_id,
    extract_viewstate,
    parse_vehicle,
)


class TestExtractViewstate:
    def test_extracts_viewstate_token(self):
        html = """
        <input type="hidden" name="javax.faces.ViewState" value="abc123xyz">
        """
        result = extract_viewstate(html)
        assert result == "abc123xyz"

    def test_raises_when_viewstate_missing(self):
        html = "<html><body>No ViewState here</body></html>"
        with pytest.raises(ValueError, match="ViewState not found"):
            extract_viewstate(html)


class TestExtractFormId:
    def test_finds_form_by_anchor(self):
        html = """
        <form id="params_form">
            <input name="test">
        </form>
        """
        result = extract_form_id(html, anchor="params")
        assert result == "params_form"

    def test_raises_when_anchor_not_found(self):
        html = """
        <form id="other_form">
            <input name="test">
        </form>
        """
        with pytest.raises(ValueError, match="Form with anchor"):
            extract_form_id(html, anchor="params")

    def test_case_insensitive_anchor_match(self):
        html = """
        <form id="PARAMS_form">
            <input name="test">
        </form>
        """
        result = extract_form_id(html, anchor="params")
        assert result == "PARAMS_form"


class TestExtractArgus:
    def test_extracts_argus_token(self):
        html = """
        <input type="hidden" name="params:argus" value="token123">
        """
        result = extract_argus(html)
        assert result == "token123"

    def test_raises_when_argus_missing(self):
        html = "<html><body>No argus here</body></html>"
        with pytest.raises(ValueError, match="argus token not found"):
            extract_argus(html)


class TestParseVehicle:
    def test_parses_vehicle_with_all_fields(self):
        html = """
        <table>
        <tr>
            <td>Placa</td>
            <td>BJV 123</td>
        </tr>
        <tr>
            <td>Marca</td>
            <td>TOYOTA</td>
        </tr>
        <tr>
            <td>Estilo</td>
            <td>COROLLA</td>
        </tr>
        <tr>
            <td>Categoría</td>
            <td>Automóvil Particular</td>
        </tr>
        <tr>
            <td>Año Fabricación</td>
            <td>2020</td>
        </tr>
        <tr>
            <td>Motor</td>
            <td>1600 c.c.</td>
        </tr>
        <tr>
            <td>Valor Contrato</td>
            <td>5,000,000</td>
        </tr>
        <tr>
            <td>Propietario</td>
            <td>CEDULA 110350386 — JUAN MORA</td>
        </tr>
        </table>
        """
        result = parse_vehicle(html)
        assert result.placa == "BJV 123"
        assert result.marca == "TOYOTA"
        assert result.estilo == "COROLLA"
        assert result.categoria == "Automóvil Particular"
        assert result.año_fabricacion == "2020"
        assert result.cilindrada_cc == "1600"
        assert result.valor_contrato == "5,000,000"
        assert result.propietario_id == "110350386"
        assert result.propietario_nombre == "JUAN MORA"

    def test_parses_vehicle_with_partial_fields(self):
        html = """
        <table>
        <tr>
            <td>Placa</td>
            <td>ABC 123</td>
        </tr>
        <tr>
            <td>Marca</td>
            <td>HONDA</td>
        </tr>
        </table>
        """
        result = parse_vehicle(html)
        assert result.placa == "ABC 123"
        assert result.marca == "HONDA"
        assert result.estilo == ""
        assert result.cilindrada_cc == ""

    def test_handles_propietario_without_cedula_format(self):
        html = """
        <table>
        <tr>
            <td>Propietario</td>
            <td>UNKNOWN OWNER</td>
        </tr>
        </table>
        """
        result = parse_vehicle(html)
        assert result.propietario_id == "UNKNOWN OWNER"
        assert result.propietario_nombre == ""

    def test_handles_empty_html(self):
        html = "<html><body></body></html>"
        result = parse_vehicle(html)
        assert result.placa == ""
        assert result.marca == ""
