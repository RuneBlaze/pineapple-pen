from dataclasses import dataclass

import pytest
from genio.base import Mythical, generate_using_docstring, paragraph_consolidate


@dataclass
class Chocolate(Mythical):
    "A chocolate with a specific flavor."

    flavor: str


@pytest.mark.skip("takes too long")
def test_gen_from_docstring():
    choco = generate_using_docstring(Chocolate, {})
    assert choco.flavor


def test_paragraph_consolidate_with_multiple_paragraphs():
    text = """
    This is the first line of the first paragraph.
    This is the second line of the first paragraph.

    This is the first line of the second paragraph.
    This is the second line of the second paragraph.
    """
    expected = "This is the first line of the first paragraph. This is the second line of the first paragraph.\n\nThis is the first line of the second paragraph. This is the second line of the second paragraph."
    assert paragraph_consolidate(text) == expected


def test_paragraph_consolidate_with_single_paragraph():
    text = """
    This is the first line of the paragraph.
    This is the second line of the paragraph.
    """
    expected = "This is the first line of the paragraph. This is the second line of the paragraph."
    assert paragraph_consolidate(text) == expected


def test_paragraph_consolidate_with_no_paragraphs():
    text = ""
    expected = ""
    assert paragraph_consolidate(text) == expected


def test_paragraph_consolidate_list():
    input_text = """\
        This is a paragraph
        continuing the same paragraph.

        * This is a list item
        - Another list item

        And this is a new paragraph.
    """

    expected_output = """\
This is a paragraph continuing the same paragraph.

* This is a list item

- Another list item

And this is a new paragraph."""

    assert paragraph_consolidate(input_text) == expected_output