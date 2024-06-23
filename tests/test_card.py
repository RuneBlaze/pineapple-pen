from genio.card import Card


def test_card_parse_trivial():
    assert Card.parse("<test>")
    assert Card.parse("<test: description>")
    assert Card.parse("<test: description with more random stuff>")
