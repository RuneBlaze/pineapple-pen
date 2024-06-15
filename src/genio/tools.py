from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated

from smallperm import shuffle

from genio.battler import EnemyBattler, PlayerBattler, PlayerProfile
from genio.core.base import promptly, slurp_toml

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
            return f"{self.name} ({self.description}) [{humanize_card_type(self.card_type)}]"
        return f"{self.name} [{humanize_card_type(self.card_type)}]"


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


@promptly
def _judge_results(
    cards: list[Card],
    user: PlayerBattler,
    enemies: list[EnemyBattler],
    battle_context: str,
) -> ResolvedResults:
    """\
    {% include('judge.md') %}

    {{ formatting_instructions }}

    Let's think step by step.
    """
    ...


predef = slurp_toml("assets/strings.toml")


def parse_card_description(description: str) -> tuple[str, str, int]:
    parts = description.split("#")
    main_part = parts[0].strip()
    desc = parts[1].strip() if len(parts) > 1 else None

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


class CardBundle:
    def __init__(self, deck: list[Card]) -> None:
        self.deck = shuffle(deck)
        self.hand = []
        self.graveyard = []

    @staticmethod
    def from_predef(key: str) -> CardBundle:
        return CardBundle(create_deck(predef[key]["cards"]))

    def draw(self, count: int) -> Iterator[Card]:
        while count > 0:
            if len(self.deck) == 0:
                self.deck = shuffle(self.graveyard)
                self.graveyard = []
            card = self.deck.pop()
            yield card
            count -= 1

    def draw_to_hand(self, count: int) -> None:
        self.hand.extend(self.draw(count))


if __name__ == "__main__":
    deck = create_deck(predef["initial_deck"]["cards"])

    slash = [c for c in deck if c.name.lower() == "slash"][0]
    left = [c for c in deck if c.name.lower() == "left"][0]
    right = [c for c in deck if c.name.lower() == "right"][0]
    repeat = [c for c in deck if c.name.lower() == "repeat all previous"][0]

    default_battle_context = []
    default_battle_context.append(
        "It's a brightly lit cave, with torches lining the walls."
    )
    # default_battle_context.append("")
    # default_battle_context.append("Enemies' intents:")
    enemies = [EnemyBattler.from_predef("enemies.slime", i + 1) for i in range(2)]
    # for e in enemies:
    #     default_battle_context.append(f"{e.name}: {e.profile.pattern[0]}")
    # default_battle_context.append("The list of enemies on the battlefield:")
    # default_battle_context.append("")
    # for e in enemies:
    #     default_battle_context.append(f"{e.name} ({e.profile.description})")

    # default_battle_context.append("[FILL IN]")

    # print(default_battle_context)

    # starter_enemy = PlayerProfile.from_predef("enemies.starter")
    starter_player = PlayerProfile.from_predef("players.starter")
    built_context = "\n".join(default_battle_context)
    # print(built_context)

    completed = _judge_results(
        cards=[slash, left, right, repeat, left, right],
        user=PlayerBattler.from_profile(starter_player),
        enemies=enemies,
        battle_context=built_context,
    )

    # print(completed)
