from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated

from genio.core.base import access, promptly, slurp_toml

predef = slurp_toml("assets/strings.toml")


class CardType(Enum):
    CONCEPT = "concept"
    ACTION = "action"
    SPECIAL = "special"


@dataclass
class Card:
    card_type: CardType
    name: str
    description: str | None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_record(self) -> dict:
        return {
            "id": self.id,
            "card_type": self.card_type.value,
            "name": self.name,
            "description": self.description,
        }

    def to_plaintext(self) -> str:
        if self.description:
            return f"{self.name} ({self.description})"
        return self.name


@dataclass
class ResolvedResults:
    """A completed sentence in the game. An occurrence, a line, of the game's narrative."""

    reason: Annotated[
        str,
        "Justification for the completion. How the *action* connects the concepts serially.",
    ]
    results: Annotated[
        str,
        (
            "The results of the actions taken by both the player and the enemies, and the consequences of those actions. "
            "The nuemrical deltas should be given in square brackets like [Slime: receive 5 damage]. "
        ),
    ]


@dataclass
class PlayerProfile:
    name: str
    profile: str

    @staticmethod
    def from_predef(key: str) -> PlayerProfile:
        return PlayerProfile(**access(predef, key))


@dataclass
class PlayerBattler:
    profile: PlayerProfile
    hp: int
    max_hp: int
    shield_points: int

    @staticmethod
    def from_profile(profile: PlayerProfile) -> PlayerBattler:
        return PlayerBattler(
            profile=profile,
            hp=profile.hit_points,
            max_hp=profile.hit_points,
            shield_points=0,
        )

    @staticmethod
    def from_predef(key: str) -> PlayerBattler:
        return PlayerBattler.from_profile(PlayerProfile.from_predef(key))

    def is_dead(self) -> bool:
        return self.hp <= 0

    def receive_damage(self, damage: int) -> None:
        self.hp -= damage
        if self.hp < 0:
            self.hp = 0


@promptly
def _judge_results(
    played_cards: list[Card],
    player: PlayerBattler,
    enemies: list[EnemyBattler],
    conversation_context: str,
) -> ResolvedResults:
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
    def from_predef(key: str) -> EnemyProfile:
        return EnemyProfile(**access(predef, key))


@dataclass
class EnemyBattler:
    profile: EnemyProfile
    hp: int
    max_hp: int
    shield_points: int

    @staticmethod
    def from_profile(profile: EnemyProfile) -> EnemyBattler:
        return EnemyBattler(
            profile=profile,
            hp=profile.hit_points,
            max_hp=profile.hit_points,
            shield_points=0,
        )

    @staticmethod
    def from_predef(key: str) -> EnemyBattler:
        return EnemyBattler.from_profile(EnemyProfile.from_predef(key))

    def is_dead(self) -> bool:
        return self.hp <= 0

    def receive_damage(self, damage: int) -> None:
        self.hp -= damage
        if self.hp < 0:
            self.hp = 0


if __name__ == "__main__":
    default_conversation_context = """\
    It's a brightly lit restaurant, sparsely populated with a few patrons.

    Jon: "I'm so glad you could make it. I've been looking forward to this all week."
    [FILL IN]
    """

    starter_enemy = PlayerProfile.from_predef("enemies.starter")
    starter_player = PlayerProfile.from_predef("players.starter")

    completed = _judge_results(
        words=["*talk about*", "'love'", "'money'"],
        user=starter_player,
        other=starter_enemy,
        conversation_context=default_conversation_context,
    )

    print(completed)
