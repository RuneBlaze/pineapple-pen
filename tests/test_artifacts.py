from genio.artifacts import parse_stylize


def test_parse_stylize():
    # Test case 1: Single stylize tag
    s1 = "This is a (Stylize:sample) text."
    expected1 = ["sample"]
    assert parse_stylize(s1) == expected1

    # Test case 2: Multiple stylize tags
    s2 = "This (Stylize:is) a (Stylize:sample) (Stylize:text)."
    expected2 = ["is", "sample", "text"]
    assert parse_stylize(s2) == expected2

    # Test case 3: No stylize tags
    s3 = "This is a sample text."
    expected3 = []
    assert parse_stylize(s3) == expected3

    # Test case 4: Empty string
    s4 = ""
    expected4 = []
    assert parse_stylize(s4) == expected4

    # Test case 5: Stylize tags with special characters
    s5 = "(Stylize:sample1) (Stylize:sample2!@#$%) (Stylize:sample3)"
    expected5 = ["sample1", "sample2!@#$%", "sample3"]
    assert parse_stylize(s5) == expected5
