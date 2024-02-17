from genio.base import Mythical, generate_using_docstring
from dataclasses import dataclass


@dataclass
class Chocolate(Mythical):
    "A chocolate with a specific flavor."

    flavor: str


def test_gen_from_docstring():
    choco = generate_using_docstring(Chocolate, {})
    assert choco.flavor
