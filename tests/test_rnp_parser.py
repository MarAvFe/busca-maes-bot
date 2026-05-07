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

    def test_finds_form_by_contains(self):
        html = """
        <form id="form1">
            <input name="field1">
        </form>
        <form id="form2">
            <input name="jid7e05f2:correo">
            <input name="jid7e05f2:pass">
        </form>
        """
        result = extract_form_id(html, contains=":correo")
        assert result == "form2"

    def test_raises_when_contains_not_found(self):
        html = """
        <form id="form1">
            <input name="field1">
        </form>
        """
        with pytest.raises(ValueError, match="Form containing input"):
            extract_form_id(html, contains=":correo")


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
    @pytest.fixture
    def mot621335_html(self):
        """Real MOT 621335 vehicle result structure (mashed-text format)."""
        return (
            "<html><body><table><tr><td>Tomo: 2018 Asiento: 00001206 "
            "Secuencia: 001 Fecha: 12-ene-2018 Marca: HONDA Estilo: XR 150 L "
            "Categoría: MOTOCICLETA Capacidad: 2 personas # de Serie: "
            "LTMKD0799J5202247 Peso Vacio: 0.00 KG Carroceria: MOTOCICLETA "
            "Peso Neto: 118.00 KG Tracción: 2X2 PBV (Fabricante): 153.00 KG "
            "# de Chasis: LTMKD0799J5202247 Valor Hacienda (verificar "
            "actualización en el marchamo): 470,000.00 Año Fabricación: 2018 "
            "Estado Actual: INSCRITO Longitud: 0.00 mts. Estado Tributario: "
            "PAGO DERECHOS DE ADUANA Cabina: NO APLICA Clase Tributaria: "
            "2879304 Techo: NO APLICA Uso: PARTICULAR Peso Remolque: 0.00 KG "
            "Valor Contrato: 1,100,000.00 Color: ROJO Numero registral: 0 "
            "Convertido: N Moneda: COLONES # de VIN: LTMKD0799J5202247 "
            "N.Motor:KD07E2210361 Marca:HONDA # de Serie:NO INDICADO "
            "Modelo:XR 150 L Cilindrada:149 C.C Cilindros:1 Potencia:9 KW "
            "Combustible:GASOLINA Fabricante:NO INDICADO Procedencia:DESCONOCIDA "
            "N.Motor: KD07E2210361 Marca: HONDA # de Serie: NO INDICADO "
            "Modelo: XR 150 L Cilindrada: 149 C.C Cilindros: 1 Potencia: 9 KW "
            "Combustible: GASOLINA Fabricante: NO INDICADO Procedencia: "
            "DESCONOCIDA Ver Persona CEDULA DE IDENTIDAD 110350386 ABARCA "
            "MORALES JUAN ELIAS Tomo: 2018 Asiento: 00001206 Secuencia: 001"
            "</td></tr></table></body></html>"
        )

    def test_parses_mot621335_correctly(self, mot621335_html):
        """Test parsing of real MOT 621335 plate with mashed-text structure."""
        result = parse_vehicle(mot621335_html)
        assert result.marca == "HONDA", f"Expected 'HONDA', got '{result.marca}'"
        assert result.estilo == "XR 150 L", f"Expected 'XR 150 L', got '{result.estilo}'"
        assert result.categoria == "MOTOCICLETA", (
            f"Expected 'MOTOCICLETA', got '{result.categoria}'"
        )
        assert result.año_fabricacion == "2018", f"Expected '2018', got '{result.año_fabricacion}'"
        assert result.cilindrada_cc == "149", f"Expected '149', got '{result.cilindrada_cc}'"
        assert result.valor_contrato == "1,100,000.00", (
            f"Expected '1,100,000.00', got '{result.valor_contrato}'"
        )
        assert result.propietario_id == "110350386", (
            f"Expected '110350386', got '{result.propietario_id}'"
        )
        assert result.propietario_nombre == "ABARCA MORALES JUAN ELIAS", (
            f"Expected 'ABARCA MORALES JUAN ELIAS', got '{result.propietario_nombre}'"
        )

    def test_skips_no_indicado_fields(self):
        """Test that NO INDICADO values are skipped (empty string)."""
        html = """
        <html><body>
        <table><tr><td>
        Marca: NO INDICADO Estilo: Honda Civic Categoría: NO INDICADO
        Año Fabricación: 2020 Valor Contrato: NO INDICADO
        </td></tr></table>
        </body></html>
        """
        result = parse_vehicle(html)
        assert result.marca == "", "Marca should be empty for NO INDICADO"
        assert result.estilo == "Honda Civic", "Estilo should be extracted"
        assert result.categoria == "", "Categoría should be empty for NO INDICADO"
        assert result.año_fabricacion == "2020", "Año Fabricación should be extracted"
        assert result.valor_contrato == "", "Valor Contrato should be empty for NO INDICADO"

    def test_extracts_cilindrada_from_cilindrada_field(self):
        """Test cilindrada extraction when N.Motor is not available."""
        html = """
        <html><body>
        <table><tr><td>
        Marca: TOYOTA Cilindrada: 1600 C.C
        </td></tr></table>
        </body></html>
        """
        result = parse_vehicle(html)
        assert result.cilindrada_cc == "1600"

    def test_handles_propietario_format(self):
        """Test propietario cedula + name parsing from CEDULA DE IDENTIDAD format."""
        html = """
        <html><body>
        <table><tr><td>
        Marca: FORD Ver Persona CEDULA DE IDENTIDAD 987654321 LUIS GOMEZ SANTOS
        Tomo: 2019
        </td></tr></table>
        </body></html>
        """
        result = parse_vehicle(html)
        assert result.propietario_id == "987654321"
        assert result.propietario_nombre == "LUIS GOMEZ SANTOS"

    def test_handles_cedula_juridica_owner(self):
        """Test propietario parsing when owner is a corporate entity (CEDULA JURIDICA)."""
        html = (
            "<html><body><table><tr><td>"
            "Marca: VOLVO Estilo: S40 2.4 Categoría: AUTOMOVIL Año Fabricación: 2007 "
            "CEDULA JURIDICA 3102901366 DESARROLLOS MAVIF SOCIEDAD DE RESPONSABILIDAD LIMITADA "
            "No Posee Gravamen(es)"
            "</td></tr></table></body></html>"
        )
        result = parse_vehicle(html)
        assert result.propietario_id == "3102901366"
        assert result.propietario_nombre == "DESARROLLOS MAVIF SOCIEDAD DE RESPONSABILIDAD LIMITADA"

    def test_handles_empty_html(self):
        """Test that empty HTML returns empty VehicleResult."""
        html = "<html><body></body></html>"
        result = parse_vehicle(html)
        assert result.marca == ""
        assert result.estilo == ""
        assert result.categoria == ""
        assert result.año_fabricacion == ""
        assert result.cilindrada_cc == ""
        assert result.valor_contrato == ""
        assert result.propietario_id == ""
        assert result.propietario_nombre == ""

    def test_propietario_stops_at_wall_text(self):
        """Test that propietario_nombre stops at RNP footer markers (wall-text issue)."""
        html = """
        <html><body><table><tr><td>
        CEDULA DE IDENTIDAD 115320866 REYES CARRANZA JOSE HUMBERTO
        No Posee Gravamen(es) No Posee Anotación(es) No Posee Infracción(es) / Colisión(es)
        Se aclara que las consultas de las infracciones...
        Emitido: 06-May-2026
        </td></tr></table></body></html>
        """
        result = parse_vehicle(html)
        assert result.propietario_id == "115320866"
        assert result.propietario_nombre == "REYES CARRANZA JOSE HUMBERTO"
        assert "No Posee" not in result.propietario_nombre
        assert "Emitido" not in result.propietario_nombre

    def test_propietario_name_capped_at_80_chars(self):
        """Test that propietario_nombre is capped at 80 characters."""
        html = """
        <html><body><table><tr><td>
        CEDULA DE IDENTIDAD 123456789 VERY LONG NAME WITH MANY WORDS THAT
        EXCEEDS EIGHTY CHARACTERS AND SHOULD BE TRUNCATED AUTOMATICALLY
        Emitido: 2026
        </td></tr></table></body></html>
        """
        result = parse_vehicle(html)
        assert result.propietario_id == "123456789"
        assert len(result.propietario_nombre) <= 80
