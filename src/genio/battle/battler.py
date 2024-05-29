from __future__ import annotations

import io
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass, field
from random import sample
from typing import Iterator

import numpy as np

from genio.core.base import render_text

VALUES = ["patk", "pdef", "matk", "mdef", "agi", "eva"]
CLAMPED_VALUES = ["hp", "mp"]
RULES = []


@dataclass
class ClampedValue:
    value: int
    min_value: int
    max_value: int

    def __post_init__(self):
        self.value = max(self.min_value, min(self.max_value, self.value))

    @staticmethod
    def capped(max_value: int) -> ClampedValue:
        return ClampedValue(max_value, 0, max_value)

    def map(self, func: Callable[[int], int]) -> ClampedValue:
        return ClampedValue(func(self.value), self.min_value, self.max_value)


@dataclass
class Mark:
    name: str
    effects: list[str]
    turns_left: int


class Battler:
    stats: MutableMapping[str, ClampedValue]
    name: str
    items: list[ItemLike]
    marks: list[Mark]

    def __init__(
        self, name: str, values: dict[str, int], items: list[ItemLike] | None = None
    ) -> None:
        stats = {}
        for key in CLAMPED_VALUES:
            stats[key] = ClampedValue.capped(values[key])
        for key in VALUES:
            stats[key] = values[key]
        self.items = items or []
        self.stats = stats
        self.name = name
        self.marks = []

    def mark(self, name: str, effects: list[str], duration: int) -> None:
        self.marks.append(Mark(name, effects, duration))

    def receive_damage(self, damage: int) -> None:
        damage = max(0, damage)
        self.stats["hp"] = self.stats["hp"].map(lambda x: x - damage)

    def receive_heal(self, heal: int) -> None:
        heal = max(0, heal)
        self.stats["hp"] = self.stats["hp"].map(lambda x: x + heal)

    def end_of_turn(self) -> None:
        for mark in self.marks:
            mark.turns_left -= 1
        self.marks = [mark for mark in self.marks if mark.turns_left > 0]


class BattlerIndex:
    players: list[Battler]  # A - Z
    enemies: list[Battler]  # a - z

    def __init__(self, players: list[Battler], enemies: list[Battler]) -> None:
        self.players = players
        self.enemies = enemies

    def from_char(self, ch: str) -> Battler:
        if ch.islower():
            return self.enemies[ord(ch) - ord("a")]
        else:
            return self.players[ord(ch) - ord("A")]

    def battlers(self) -> Iterator[Battler]:
        return iter(self.players + self.enemies)

    def battlers_with_abbreviations(self) -> Iterator[tuple[Battler, str]]:
        # the a-z and A-Z are the abbreviations for the battlers
        for ch, battler in zip("abcdefghijklmnopqrstuvwxyz", self.enemies):
            yield battler, ch
        for ch, battler in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", self.players):
            yield battler, ch

    def battlers_with_abbreviations_and_side(
        self,
    ) -> Iterator[tuple[Battler, str, str]]:
        for ch, battler in zip("abcdefghijklmnopqrstuvwxyz", self.enemies):
            yield battler, ch, "enemy"
        for ch, battler in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", self.players):
            yield battler, ch, "player"

    def search_battler(self, term: str) -> Battler:
        for battler in self.battlers():
            if battler.name.lower() == term.lower():
                return battler
        raise ValueError(f"No battler with name {term}")


@dataclass
class ItemLike:
    name: str
    effects: list[str]
    cost: int = 0
    marks: list[Mark] = field(default_factory=list)


class ASCIIBoard:
    def __init__(self, height: int, width: int) -> None:
        self.base = np.zeros((height, width), dtype=np.uint8)
        self.battler_positions = {}
        self.legends = {}

    def show_board(self, output: io.StringIO) -> None:
        to_fill = self.base.copy()
        for k, (y, x) in self.battler_positions.items():
            to_fill[y, x] = ord(k)

        for row in to_fill:
            output.write("".join(chr(c) if c else "." for c in row) + "\n")

        output.write("\nLegends:\n")
        for key, legend in self.legends.items():
            output.write(f"{key}: {legend}\n")

    @staticmethod
    def parse_board(board: str) -> ASCIIBoard:
        lines = board.strip().split("\n")
        height = len(lines)
        width = len(lines[0])

        # Create an empty ASCIIBoard with the determined dimensions
        ascii_board = ASCIIBoard(height, width)

        # Parse the board representation
        for y, line in enumerate(lines):
            if line.strip() == "Legends:":
                legend_start_index = y + 1
                break
            for x, char in enumerate(line):
                if char != ".":
                    ascii_board.battler_positions[char] = (y, x)
                    if char.isalpha():
                        continue
                    ascii_board.base[y, x] = ord(char)

        # Parse the legends
        for legend in lines[legend_start_index:]:
            if legend.strip():
                key, desc = legend.split(":", 1)
                key, desc = key.strip(), desc.strip()
                ascii_board.legends[key] = desc

        return ascii_board


ACTION_TEMPLATE = """\
Respond in the form of "judgements", in the form of a Python program,
deciding the outcome of the following action:

> {{ caster.name }} uses the skill "{{ action.name }}" on "{{ target.name }}".
> {{ action.name }}:
{% for effect in action.effects %}
> - {{ effect }}
{% endfor %}

Fill out the following Python function as your judgement:

```python
ralph = battler("ralph")
slime1 = battler("slime 1")

slime1.receive_damage(ralph.atk - slime1.pdef * 2)
```

Also fill out a new board. Mark the new board with the board tag:

```board
# NEW BOARD
```

Omit all type annotations in your output to save space. Return a single Python code-block with a program that decides the outcome of the action, and a new board.
"""


class BattleManager:
    def __init__(self, allies: list[Battler], enemies: list[Battler]) -> None:
        self.index = BattlerIndex(allies, enemies)
        self.board = ASCIIBoard(6, 6)

        # Randomly place battlers on the board
        positions = sample(
            [(y, x) for y in range(6) for x in range(6)], len(allies) + len(enemies)
        )
        for (battler, abbrev), (y, x) in zip(
            self.index.battlers_with_abbreviations(), positions
        ):
            self.board.battler_positions[abbrev] = (y, x)

    def perform_action(
        self, attacker: Battler, target: Battler, item: ItemLike
    ) -> None:
        buf = io.StringIO()
        buf.write(f"{attacker.name} uses {item} on {target.name}\n")
        buf.write("Abbreviations used on the board:\n")
        for battler, abbrev, side in self.index.battlers_with_abbreviations_and_side():
            side_vocab = "player" if side == "player" else "enemy"
            buf.write(f"- {abbrev}: {battler.name} [team {side_vocab}]\n")
        buf.write("\n")
        buf.write("Current board:\n")
        self.board.show_board(buf)
        addendum = render_text(
            ACTION_TEMPLATE, {"caster": attacker, "target": target, "action": item}
        )
        buf.write(addendum)
        print(buf.getvalue())


if __name__ == "__main__":
    # Define some skills for testing using the ItemLike class
    fireball = ItemLike(
        name="Fireball",
        cost=10,
        effects=[
            "A powerful fire spell that engulfs the target in flames.",
            "Damage formula: 2 * Attacker.matk - Defender.mdef",
            "Accuracy: 90%",
            "This skill has a 20% chance to inflict 'Burn' status on the target.",
        ],
        marks=[],
    )

    heal = ItemLike(
        name="Heal",
        cost=8,
        effects=[
            "A healing spell that restores health to a single ally.",
            "Healing formula: 3 * Attacker.matk",
            "Accuracy: 100%",
            "This skill removes 'Poison' and 'Burn' status effects from the target.",
        ],
        marks=[],
    )

    slash = ItemLike(
        name="Slash",
        cost=5,
        effects=[
            "A quick physical attack with a sharp blade.",
            "Damage formula: Attacker.patk - Defender.pdef",
            "Accuracy: 95%",
            "This skill has a 10% chance to cause 'Bleed' status on the target.",
        ],
        marks=[],
    )

    shield = ItemLike(
        name="Shield",
        cost=12,
        effects=[
            "A protective spell that increases defense.",
            "Effect formula: Increase pdef by 50",
            "Duration: 3 turns",
            "This skill has a 100% chance to succeed.",
        ],
        marks=[],
    )

    # Define a normal "Attack" ItemLike for Slime and Goblin
    normal_attack = ItemLike(
        name="Attack",
        cost=0,
        effects=[
            "A basic physical attack.",
            "Damage formula: Attacker.patk - Defender.pdef",
            "Accuracy: 100%",
        ],
        marks=[],
    )

    # Define some allies and enemies for testing
    allies = [
        Battler(
            "Ralph",
            {
                "hp": 1500,
                "mp": 200,
                "patk": 250,
                "pdef": 150,
                "matk": 100,
                "mdef": 100,
                "agi": 80,
                "eva": 10,
            },
            items=[slash, shield],
        ),
        Battler(
            "Lucy",
            {
                "hp": 1200,
                "mp": 300,
                "patk": 200,
                "pdef": 120,
                "matk": 150,
                "mdef": 130,
                "agi": 90,
                "eva": 20,
            },
            items=[fireball, heal],
        ),
    ]

    enemies = [
        Battler(
            "Slime 1",
            {
                "hp": 500,
                "mp": 50,
                "patk": 50,
                "pdef": 20,
                "matk": 30,
                "mdef": 20,
                "agi": 30,
                "eva": 5,
            },
            items=[normal_attack],
        ),
        Battler(
            "Goblin",
            {
                "hp": 800,
                "mp": 80,
                "patk": 80,
                "pdef": 40,
                "matk": 40,
                "mdef": 40,
                "agi": 40,
                "eva": 10,
            },
            items=[normal_attack],
        ),
    ]

    # Initialize the BattleManager with the created allies and enemies
    battle_manager = BattleManager(allies, enemies)
    battle_manager.perform_action(allies[0], enemies[0], slash)
    # # Display the initial board setup
    # output = io.StringIO()
    # battle_manager.board.show_board(output)
    # print(output.getvalue())
