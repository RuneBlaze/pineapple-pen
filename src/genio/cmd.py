import shlex


def parse_command(cmd: str) -> list[str]:
    for line in cmd.splitlines():
        line = line.strip()
        if line.startswith(">") or line.startswith("$"):
            return shlex.split(line[1:])
    return []


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
