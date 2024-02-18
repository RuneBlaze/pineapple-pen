from genio.student import Archetype


def test_archetype_can_sample():
    assert Archetype.choice() is not None
