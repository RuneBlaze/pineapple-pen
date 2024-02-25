from dataclasses import dataclass

from genio.base import Mythical, generate_using_docstring

import pytest


@dataclass
class Chocolate(Mythical):
    "A chocolate with a specific flavor."

    flavor: str


@pytest.mark.skip("takes too long")
def test_gen_from_docstring():
    choco = generate_using_docstring(Chocolate, {})
    assert choco.flavor
