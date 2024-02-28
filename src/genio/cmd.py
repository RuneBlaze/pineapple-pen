import ast
import re
from typing import Any

pattern: re.Pattern = re.compile(
    r"^```(?:python)?(?P<python>[^`]*)", re.MULTILINE | re.DOTALL
)


def grab_python_code(response: str) -> str:
    if "```" in response:
        text = pattern.search(response).group("python")
    else:
        text = response
    return text


def parse_command(cmd: str) -> list[Any]:
    pycode = grab_python_code(cmd)
    pycode = pycode.strip()
    try:
        expr = ast.parse(pycode, mode="eval").body
    except SyntaxError:
        toks = pycode.split(":")
        toks.pop(0)
        pycode = ":".join(toks)
        expr = ast.parse(pycode, mode="eval").body
    fn_name = expr.func.id
    fn_args = [arg.s if hasattr(arg, "s") else arg.id for arg in expr.args]
    return [fn_name] + fn_args


class CommandTarget:
    identifier: str | None
    description: str
    available_actions: list[str]


class ResolvedCommand:
    command_target: CommandTarget | None
    action: str
    arguments: list[str]


def resolve_command(
    parsed: list[str], potential_targets: list[CommandTarget]
) -> ResolvedCommand:
    ...
