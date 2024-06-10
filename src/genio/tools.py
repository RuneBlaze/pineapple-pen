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

def humanize_card_type(card_type: CardType) -> str:
    return {
        CardType.CONCEPT: "modifier",
        CardType.ACTION: "concrete",
    }[card_type].capitalize()

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
    hit_points: int

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
    user: PlayerBattler,
    enemies: list[EnemyBattler],
    battle_context: str,
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
    copy_number: int = 1

    @staticmethod
    def from_profile(profile: EnemyProfile, copy_number: int = 1) -> EnemyBattler:
        return EnemyBattler(
            profile=profile,
            hp=profile.hit_points,
            max_hp=profile.hit_points,
            shield_points=0,
            copy_number=copy_number,
        )

    @staticmethod
    def from_predef(key: str, copy_number: int = 1) -> EnemyBattler:
        return EnemyBattler.from_profile(EnemyProfile.from_predef(key), copy_number)

    def is_dead(self) -> bool:
        return self.hp <= 0

    def receive_damage(self, damage: int) -> None:
        self.hp -= damage
        if self.hp < 0:
            self.hp = 0

    @property
    def name(self) -> str:
        alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return f"{self.profile.name} {alpha[self.copy_number - 1]}"


predef = slurp_toml("assets/strings.toml")


def parse_card_description(description: str) -> tuple[str, str, int]:
    # Split on the '#' to separate the main part from the description
    parts = description.split("#")
    main_part = parts[0].strip()
    desc = parts[1].strip() if len(parts) > 1 else None

    # Check for the '*' to determine the number of copies
    if "*" in main_part:
        name, copies_str = main_part.split("*")
        name = name.strip()
        copies = int(copies_str.strip())
    else:
        name = main_part
        copies = 1

    return name, desc, copies


def determine_card_type(name: str) -> CardType:
    if name[0].islower():
        return CardType.CONCEPT
    elif name[0].isupper():
        return CardType.ACTION
    else:
        return CardType.SPECIAL


def create_deck(cards: list[str]) -> list[Card]:
    deck = []
    for card_description in cards:
        name, desc, copies = parse_card_description(card_description)
        card_type = determine_card_type(name)
        for _ in range(copies):
            deck.append(Card(card_type=card_type, name=name, description=desc))
    return deck

if __name__ == "__main__":
    # default_battle_context = """\
    # It's a brightly lit cave, with torches lining the walls.

    # Jon: "I'm so glad you could make it. I've been looking forward to this all week."
    # [FILL IN]
    # """

    deck = create_deck(predef["initial_deck"]["cards"])

    slash = [c for c in deck if c.name.lower() == "slash"][0]
    left = [c for c in deck if c.name.lower() == "left"][0]
    right = [c for c in deck if c.name.lower() == "right"][0]

    default_battle_context = []
    default_battle_context.append("It's a brightly lit cave, with torches lining the walls.")
    default_battle_context.append("")
    default_battle_context.append("Enemies' intents:")
    enemies = [EnemyBattler.from_predef("enemies.slime", i + 1) for i in range(2)]
    for e in enemies:
        default_battle_context.append(f"{e.name}: {e.profile.pattern[0]}")
    default_battle_context.append("The list of enemies on the battlefield:")
    default_battle_context.append("")
    for e in enemies:
        default_battle_context.append(f"{e.name} ({e.profile.description})")

    default_battle_context.append("[FILL IN]")

    # print(default_battle_context)

    # starter_enemy = PlayerProfile.from_predef("enemies.starter")
    starter_player = PlayerProfile.from_predef("players.starter")
    built_context = '\n'.join(default_battle_context)
    print(built_context)
    completed = _judge_results(
        played_cards=[slash, left, right],
        user=PlayerBattler.from_profile(starter_player),
        enemies=enemies,
        battle_context=built_context,
    )

    # print(completed)
