from yaml import safe_load


def is_nested_dict(d):
    if not isinstance(d, dict):
        return False
    return any(isinstance(v, dict) for v in d.values())


def clean_yaml(text):
    try:
        result = safe_load(text)
        if is_nested_dict(result) and len(result) == 1:
            return result[list(result.keys())[0]]
        return result
    except Exception:
        pass
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
    return safe_load(cleaned_text.replace("\\_", "_"))
