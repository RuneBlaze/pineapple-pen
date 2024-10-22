import re
from collections.abc import Mapping

import json5 as json
from genio.core.llm import aux_llm
from yaml import safe_load
from yaml.parser import ParserError
from yaml.scanner import ScannerError


def is_nested_dict(d):
    if not isinstance(d, dict):
        return False
    return any(isinstance(v, dict) for v in d.values())


def cleaning_parse(text, expected_keys: list[str] | None = None):
    if "{" not in text and "}" not in text:
        return json.loads("{\n" + text + "\n}")
    return json.loads(text)


def recursive_remove_comments_in_dict(d: dict) -> dict:
    # some strings have '#' in them, so we need to be careful
    # with the replacement
    res = {}
    for k, v in d.items():
        if isinstance(v, dict):
            res[k] = recursive_remove_comments_in_dict(v)
        else:
            if isinstance(v, str) and "#" in v:
                res[k] = v.split("#")[0]
            else:
                res[k] = v
    return res


pattern: re.Pattern = re.compile(
    r"^```(?:json)?(?P<json>[^`]*)", re.MULTILINE | re.DOTALL
)


def fix_invalid_yaml_string(s: str) -> str:
    try:
        x = safe_load(s)
        if not isinstance(x, Mapping):
            raise ParserError("Not a YAML dictionary: got " + str(type(x)))
        return s
    except (ParserError, ScannerError) as e:
        llm = aux_llm()
        result = llm.invoke(
            f"""The following was rejected because it is not a valid YAML dictionary.
        
        Specifically: {e}. Write your YAML entirely in JSON-compat mode if needed.
        ```yaml
        {s}
        ```
        Please fix it faithfully and return a valid YAML dict in code blocks.
        """
        )
        response = result.content
        if "```" in response:
            text = pattern.search(response).group("yaml")
        else:
            text = response
        return fix_invalid_yaml_string(text)
