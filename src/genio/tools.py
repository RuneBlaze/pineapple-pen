from dataclasses import dataclass
from typing import Annotated

from genio.core.base import access, promptly, slurp_toml

predef = slurp_toml("assets/strings.toml")

@dataclass
class CompletedSentence:
    """A completed sentence in the game. An occurrence, a line, of the game's narrative."""

    reason: Annotated[
        str,
        "Justification for the completion. How the *action* connects the concepts serially.",
    ]
    sentence: Annotated[
        str,
        "A sentence or two that continues the current scenario, uses the action, and connects the concepts.",
    ]


@dataclass
class TalkingProfile:
    name: str
    profile: str

    @staticmethod
    def from_predef(key: str) -> "TalkingProfile":
        return TalkingProfile(**access(predef, key))


@promptly
def _complete_sentence(
    words: list[str],
    user: TalkingProfile,
    other: TalkingProfile,
    conversation_context: str,
) -> CompletedSentence:
    """\
    {% include('templates.form_sentence') %}

    {{ formatting_instructions }}
    """
    ...


default_conversation_context = """\
It's a brightly lit restaurant, sparsely populated with a few patrons.

Jon: "I'm so glad you could make it. I've been looking forward to this all week."
[FILL IN]
"""

starter_enemy = TalkingProfile.from_predef("enemies.starter")
starter_player = TalkingProfile.from_predef("players.starter")

completed = _complete_sentence(
    words=["*talk about*", "'love'", "'money'"],
    user=starter_player,
    other=starter_enemy,
    conversation_context=default_conversation_context,
)

print(completed)
