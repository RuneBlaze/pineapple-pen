from yaml import safe_load
from yaml.parser import ParserError
import re

from yaml.scanner import ScannerError

from .llm import default_llm


def is_nested_dict(d):
    if not isinstance(d, dict):
        return False
    return any(isinstance(v, dict) for v in d.values())


def cleaning_parse(text, expected_keys: list[str] | None = None):
    # try:
    #     result = safe_load(text)
    #     if is_nested_dict(result) and len(result) == 1:
    #         return result[list(result.keys())[0]]
    #     return result
    # except Exception:
    #     pass
    lines = text.split("\n")
    processed = []

    # First Pass: Append isolated strings to the previous line
    for i in range(len(lines)):
        if not lines[i].strip():
            continue
        if (
            lines[i].strip()
            and ":" not in lines[i]
            and not lines[i].strip().startswith(("*", "-"))
        ):
            if processed:
                # Append to previous line
                processed[-1] = processed[-1] + " " + lines[i].strip()
        else:
            processed.append(lines[i])

    # Second Pass: Convert '*' to '-' in list items
    processed = [
        l.replace("*", "-") if l.strip().startswith("*") else l for l in processed
    ]

    # Third Pass: Further clean up and format adjustments
    cleaned = []
    for l in processed:
        stripped_line = l.strip()

        # Skip YAML document separators
        if stripped_line == "---":
            continue

        # Handle colon followed by newline
        if ":" in stripped_line:
            key, value = stripped_line.split(":", 1)
            if not value.strip():
                cleaned.append(f"{key.strip()}:")
                continue
            escaped = value.strip().replace("'", "''")
            cleaned.append(f"{key.strip()}: '{escaped}'")
        else:
            cleaned.append(stripped_line)

    # Final processing
    cleaned_text = "\n".join(cleaned)
    cleaned_text = cleaned_text.replace(":\n", ": ")
    cleaned_text = cleaned_text.replace(": -", ":\n-")
    cleaned_text = cleaned_text.replace("\\_", "_")
    cleaned_text = fix_invalid_yaml_string(cleaned_text)
    if expected_keys:
        return fix_yaml_for_keys(cleaned_text, expected_keys)
    return safe_load(cleaned_text)


pattern: re.Pattern = re.compile(
    r"^```(?:ya?ml)?(?P<yaml>[^`]*)", re.MULTILINE | re.DOTALL
)

from collections.abc import Mapping


def fix_invalid_yaml_string(s: str) -> str:
    try:
        x = safe_load(s)
        if not isinstance(x, Mapping):
            raise ParserError("Not a YAML dictionary: got " + str(type(x)))
        return s
    except (ParserError, ScannerError) as e:
        llm = default_llm()
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


def fix_yaml_for_keys(s: str, ks: list[str]) -> dict:
    # Parse the YAML string
    try:
        d = safe_load(s)

        # Check if the keys match, return the dictionary if they do
        if set(ks) == set(d.keys()):
            return d
    except ParserError:
        pass

    # Iterate over the keys and replace incorrect format
    for k in ks:
        # Create a pattern that matches '- k:' with any leading spaces
        pattern = re.compile(rf"^\s*-\s+{k}:", re.MULTILINE)

        # Replace the incorrect format with the correct one
        s = re.sub(pattern, rf"{k}:", s)

    # Parse and return the corrected YAML
    return safe_load(s)
