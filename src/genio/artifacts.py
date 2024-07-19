import re


def parse_stylize(s: str | None) -> list[str]:
    if not s:
        return []
    pat = re.compile(r"\(Stylize:(.*?)\)")
    results = []
    for r in pat.findall(s):
        results.append(r.strip())
    return results
