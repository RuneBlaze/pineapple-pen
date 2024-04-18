import pytest
from genio.concepts.architect import sample_architectural_keywords, sample_literature


@pytest.mark.skip("takes too long")
def test_can_generate():
    assert sample_literature() is not None
    assert sample_architectural_keywords() is not None
