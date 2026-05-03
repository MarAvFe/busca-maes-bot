"""Unit tests for TSE HTML parsers using synthetic fixtures.

These exercise the parsing functions without hitting the network.
The HTML samples are minimal — just enough to exercise each branch.
Real TSE HTML is much larger; if the parser breaks on real responses
that pass these tests, capture the failing real fixture and add a test.
"""

from bs4 import BeautifulSoup

from buscamaes.sources.tse.parser import (
    _extract_viewstate,
    _parse_delta,
    _parse_resultado,
    _parse_results_list,
)

# ---------------------------------------------------------------------------
# _extract_viewstate
# ---------------------------------------------------------------------------


def test_extract_viewstate_pulls_three_fields():
    html = """
    <form>
      <input name="__VIEWSTATE" value="vs-token-abc" />
      <input name="__VIEWSTATEGENERATOR" value="gen-xyz" />
      <input name="__EVENTVALIDATION" value="ev-123" />
    </form>
    """
    soup = BeautifulSoup(html, "lxml")
    vs = _extract_viewstate(soup)
    assert vs["__VIEWSTATE"] == "vs-token-abc"
    assert vs["__VIEWSTATEGENERATOR"] == "gen-xyz"
    assert vs["__EVENTVALIDATION"] == "ev-123"
    assert vs["__LASTFOCUS"] == ""
    assert vs["__EVENTTARGET"] == ""
    assert vs["__EVENTARGUMENT"] == ""


def test_extract_viewstate_returns_empty_when_missing():
    soup = BeautifulSoup("<form></form>", "lxml")
    vs = _extract_viewstate(soup)
    assert vs["__VIEWSTATE"] == ""
    assert vs["__VIEWSTATEGENERATOR"] == ""


# ---------------------------------------------------------------------------
# _parse_delta
# ---------------------------------------------------------------------------


def test_parse_delta_extracts_redirect():
    # Format: length|type|id|content|
    redirect_path = "/chc/muestra_nombres.aspx?id=foo"
    delta = f"{len(redirect_path)}|pageRedirect||{redirect_path}|"
    result = _parse_delta(delta)
    assert result["pageRedirect:"] == redirect_path


def test_parse_delta_handles_multiple_segments():
    seg1 = "AAA"
    seg2 = "BBBB"
    delta_fmt = (
        f"{len(seg1)}|updatePanel|UpdatePanel1|{seg1}|{len(seg2)}|hiddenField|__VIEWSTATE|{seg2}|"
    )
    result = _parse_delta(delta_fmt)
    assert result["updatePanel:UpdatePanel1"] == seg1
    assert result["hiddenField:__VIEWSTATE"] == seg2


def test_parse_delta_returns_empty_on_garbage():
    assert _parse_delta("not a delta") == {}


# ---------------------------------------------------------------------------
# _parse_results_list  (regression test for commit 0b62237 \\d → \d bug)
# ---------------------------------------------------------------------------


def test_parse_results_list_filters_fallecidos_and_extracts_indices():
    html = """
    <table>
      <tr><td>
        <input type="radio" name="chk1$0" id="chk1_0" />
        <label for="chk1_0">1- 101110111   JUAN MORA FERNANDEZ</label>
      </td></tr>
      <tr><td>
        <input type="radio" name="chk1$1" id="chk1_1" />
        <label for="chk1_1">2- 202220222   MARIA LOPEZ ROJAS (FALLECIDA)</label>
      </td></tr>
      <tr><td>
        <input type="radio" name="chk1$2" id="chk1_2" />
        <label for="chk1_2">3- 303330333   PEDRO MORA SOLIS</label>
      </td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "lxml")
    results, total_raw = _parse_results_list(soup)
    assert total_raw == 3
    assert len(results) == 3  # function returns ALL, fallecido filter happens in caller
    by_idx = {r.index: r for r in results}
    assert by_idx[0].cedula == "101110111"
    assert by_idx[0].nombre == "JUAN MORA FERNANDEZ"
    assert by_idx[0].fallecido is False
    assert by_idx[1].fallecido is True
    assert "FALLECIDA" not in by_idx[1].nombre  # stripped from display name
    assert by_idx[2].cedula == "303330333"
    assert by_idx[2].fallecido is False


def test_parse_results_list_skips_non_matching_inputs():
    html = """
    <table>
      <tr><td>
        <input type="text" name="txtnombre" id="txt1" />
        <label for="txt1">not a result</label>
      </td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "lxml")
    results, total_raw = _parse_results_list(soup)
    assert results == []
    assert total_raw == 0


# ---------------------------------------------------------------------------
# _parse_resultado
# ---------------------------------------------------------------------------


def test_parse_resultado_extracts_all_fields():
    html = """
    <table>
      <tr>
        <td>Número de cédula:</td><td>101110111</td>
        <td>Nombre completo:</td><td>JUAN MORA FERNANDEZ</td>
      </tr>
      <tr>
        <td>Conocido/a como:</td><td>Juancho</td>
        <td>Fecha nacimiento:</td><td>01/01/1980</td>
      </tr>
      <tr>
        <td>Edad:</td><td>45</td>
        <td>Nacionalidad:</td><td>COSTARRICENSE</td>
      </tr>
      <tr>
        <td>Hijo/a de:</td><td>PADRE NAME</td>
        <td>y:</td><td>MADRE NAME</td>
      </tr>
    </table>
    """
    soup = BeautifulSoup(html, "lxml")
    person = _parse_resultado(soup)
    assert person is not None
    assert person.cedula == "101110111"
    assert person.nombre == "JUAN MORA FERNANDEZ"
    assert person.conocido_como == "Juancho"
    assert person.fecha_nacimiento == "01/01/1980"
    assert person.edad == "45"
    assert person.nacionalidad == "COSTARRICENSE"
    assert person.padre == "PADRE NAME"
    assert person.madre == "MADRE NAME"


def test_parse_resultado_returns_none_on_empty_table():
    soup = BeautifulSoup("<table></table>", "lxml")
    assert _parse_resultado(soup) is None
