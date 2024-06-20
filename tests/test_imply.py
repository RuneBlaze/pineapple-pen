from genio.imply import Subst


def test_subt_trivial():
    subst = Subst.parse("[foo: {:d}] -> [foo: {{m[0] + 2}}];")
    assert subst.apply("[foo: 5]") == "[foo: 7]"
