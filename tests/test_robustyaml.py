from genio.robustyaml import cleaning_parse
import os


def test_robust_yaml_can_parse_erronous_yaml():
    with open(
        os.path.join(os.path.dirname(__file__), "test_robustyaml.erryaml.yaml")
    ) as f:
        text = f.read()
    result = cleaning_parse(text, ["furniture_ideas", "decors"])
    assert "furniture_ideas" in result
    assert "decors" in result
