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
class PlayerProfile:
    name: str
    profile: str

    @staticmethod
    def from_predef(key: str) -> "PlayerProfile":
        return PlayerProfile(**access(predef, key))


@dataclass
class PlayerBattler:
    profile: PlayerProfile
    hp: int
    max_hp: int
    shield_points: int

    @staticmethod
    def from_profile(profile: PlayerProfile) -> "PlayerBattler":
        return PlayerBattler(
            profile=profile,
            hp=profile.hit_points,
            max_hp=profile.hit_points,
            shield_points=0,
        )

    @staticmethod
    def from_predef(key: str) -> "PlayerBattler":
        return PlayerBattler.from_profile(PlayerProfile.from_predef(key))

    def is_dead(self) -> bool:
        return self.hp <= 0

    def receive_damage(self, damage: int) -> None:
        self.hp -= damage
        if self.hp < 0:
            self.hp = 0


@promptly
def _complete_sentence(
    words: list[str],
    user: PlayerProfile,
    other: PlayerProfile,
    conversation_context: str,
) -> CompletedSentence:
    """\
    {% include('templates.form_sentence') %}

    {{ formatting_instructions }}
    """
    ...


@dataclass
class EnemyProfile:
    name: str
    hit_points: int
    description: str
    pattern: list[str]

    @staticmethod
    def from_predef(key: str) -> "EnemyProfile":
        return EnemyProfile(**access(predef, key))


@dataclass
class EnemyBattler:
    profile: EnemyProfile
    hp: int
    max_hp: int
    shield_points: int

    @staticmethod
    def from_profile(profile: EnemyProfile) -> "EnemyBattler":
        return EnemyBattler(
            profile=profile,
            hp=profile.hit_points,
            max_hp=profile.hit_points,
            shield_points=0,
        )

    @staticmethod
    def from_predef(key: str) -> "EnemyBattler":
        return EnemyBattler.from_profile(EnemyProfile.from_predef(key))

    def is_dead(self) -> bool:
        return self.hp <= 0

    def receive_damage(self, damage: int) -> None:
        self.hp -= damage
        if self.hp < 0:
            self.hp = 0


default_conversation_context = """\
It's a brightly lit restaurant, sparsely populated with a few patrons.

Jon: "I'm so glad you could make it. I've been looking forward to this all week."
[FILL IN]
"""

starter_enemy = PlayerProfile.from_predef("enemies.starter")
starter_player = PlayerProfile.from_predef("players.starter")

completed = _complete_sentence(
    words=["*talk about*", "'love'", "'money'"],
    user=starter_player,
    other=starter_enemy,
    conversation_context=default_conversation_context,
)

print(completed)
