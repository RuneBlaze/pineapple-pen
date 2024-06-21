import pytest
from genio.imply import Subst


def test_subst_trivial():
    subst = Subst.parse("[foo: {:d}] -> [foo: {{m[0] + 2}}];")
    assert subst.apply("[foo: 5]")[1] == "[foo: 7]"


def test_subst_multiple():
    subst = Subst.parse("[foo: {:d}] -> [foo: {{m[0] + 2}}];")
    assert subst.apply("[foo: 5][foo: 6]") == (2, "[foo: 7][foo: 8]")


def test_subst_condition():
    subst = Subst.parse("[foo: {:d}] if m[0] > 5 -> [foo: {{m[0] + 2}}];")
    assert subst.apply("[foo: 5]")[1] == "[foo: 5]"
    assert subst.apply("[foo: 6]")[1] == "[foo: 8]"


def test_subst_apply_no_match():
    subst = Subst("[foo: {:d}]", "[foo: {{m[0] + 2}}]")

    with pytest.raises(ValueError) as e:
        subst.apply("[bar: 5]")
