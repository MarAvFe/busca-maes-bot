from buscamaes.bot.formatting import _parse_name_input


def test_single_word():
    assert _parse_name_input("juan") == ("juan", "", "")


def test_two_words():
    assert _parse_name_input("juan mora") == ("juan", "mora", "")


def test_three_words():
    assert _parse_name_input("juan mora fernandez") == ("juan", "mora", "fernandez")


def test_four_words_compound_nombre():
    assert _parse_name_input("maria jose mora fernandez") == ("maria jose", "mora", "fernandez")


def test_strips_whitespace():
    assert _parse_name_input("  juan  mora  fernandez  ") == ("juan", "mora", "fernandez")
