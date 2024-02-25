from genio.architect import sample_literature, sample_architectural_keywords
import pytest


@pytest.mark.skip("takes too long")
def test_can_generate():
    assert sample_literature() is not None
    assert sample_architectural_keywords() is not None
