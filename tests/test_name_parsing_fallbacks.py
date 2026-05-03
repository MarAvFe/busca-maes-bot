from buscamaes.bot.formatting import _parse_name_input_with_fallbacks


def test_single_word_no_fallback():
    """Single word has only one decomposition."""
    decomps = _parse_name_input_with_fallbacks("juan")
    assert len(decomps) == 1
    assert decomps[0] == ("juan", "", "")


def test_two_words_no_fallback():
    """Two words have only one decomposition."""
    decomps = _parse_name_input_with_fallbacks("juan mora")
    assert len(decomps) == 1
    assert decomps[0] == ("juan", "mora", "")


def test_three_words_with_fallback():
    """Three words produce primary + one fallback decomposition."""
    decomps = _parse_name_input_with_fallbacks("maria jose mora")
    assert len(decomps) == 2
    # Primary: nome="maria", apel1="jose", apel2="mora"
    assert decomps[0] == ("maria", "jose", "mora")
    # Fallback: nome="maria jose", apel1="mora", apel2=""
    assert decomps[1] == ("maria jose", "mora", "")


def test_four_words_with_fallback():
    """Four words produce primary + one fallback decomposition."""
    decomps = _parse_name_input_with_fallbacks("maria jose mora fernandez")
    assert len(decomps) == 2
    # Primary: nome="maria jose", apel1="mora", apel2="fernandez"
    assert decomps[0] == ("maria jose", "mora", "fernandez")
    # Fallback: nome="maria jose mora", apel1="fernandez", apel2=""
    assert decomps[1] == ("maria jose mora", "fernandez", "")


def test_whitespace_stripped():
    """Leading/trailing/extra whitespace is handled."""
    decomps = _parse_name_input_with_fallbacks("  maria  jose  mora  ")
    expected = _parse_name_input_with_fallbacks("maria jose mora")
    assert decomps == expected
