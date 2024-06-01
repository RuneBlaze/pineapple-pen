from __future__ import annotations

import io
import re
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass, field
from random import random, sample
from typing import Iterator, Protocol

import numpy as np

from genio.core.base import render_text
from genio.core.llm import default_llm

from rich.prompt import Prompt

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


for key in VALUES:
    setattr(
        Battler,
        key,
        property(lambda self, k=key: self.stats[k]),
    )

for key in CLAMPED_VALUES:
    setattr(
        Battler,
        key,
        property(lambda self, k=key: self.stats[k].value),
    )

    setattr(
        Battler,
        "m" + key,
        property(lambda self, k=key: self.stats[k].max_value),
    )


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


class Briefable(Protocol):
    def briefs(self) -> list[str]:
        ...

    @property
    def name(self) -> str:
        ...


@dataclass
class ItemLike:
    name: str
    effects: list[str]
    cost: int = 0
    marks: list[Mark] = field(default_factory=list)

    def briefs(self) -> list[str]:
        return self.effects


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

    @staticmethod
    def parse_board(board: str) -> ASCIIBoard:
        lines = board.strip().split("\n")
        height = len(lines)
        width = len(lines[0])

        # Create an empty ASCIIBoard with the determined dimensions
        ascii_board = ASCIIBoard(height, width)

        legend_start_index = None

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

        if legend_start_index is not None:
            # Parse the legends
            for legend in lines[legend_start_index:]:
                if legend.strip():
                    key, desc = legend.split(":", 1)
                    key, desc = key.strip(), desc.strip()
                    ascii_board.legends[key] = desc

        return ascii_board


@dataclass
class Tile:
    glyph: str
    description: str


class BriefCase:
    inner: dict[str, Briefable]

    def __init__(self) -> None:
        self.inner = {}

    def add(self, key: str, value: Briefable) -> None:
        key = key.strip().lower()
        if key in self.inner:
            raise ValueError(f"Key {key} already exists in the briefcase")
        self.inner[key] = value

    def search(self, key: str) -> Briefable:
        key = key.strip().lower()
        if key not in self.inner:
            raise ValueError(f"No brief with key {key}")
        return self.inner[key]


def svo_sentence(attacker: Battler, target: Battler, item: ItemLike) -> str:
    return f'{attacker.name} uses "{item.name}" on {target.name}.'


def extract_double_quoted_words(s: str) -> list[str]:
    return re.findall(r'"([^"]*)"', s)


class BattleManager:
    def __init__(
        self,
        allies: list[Battler],
        enemies: list[Battler],
        breifcase: BriefCase | None = None,
    ) -> None:
        self.index = BattlerIndex(allies, enemies)
        self.board = ASCIIBoard(6, 6)
        self.briefcase = breifcase or BriefCase()

        # Randomly place battlers on the board
        positions = sample(
            [(y, x) for y in range(6) for x in range(6)], len(allies) + len(enemies)
        )
        for (battler, abbrev), (y, x) in zip(
            self.index.battlers_with_abbreviations(), positions
        ):
            self.board.battler_positions[abbrev] = (y, x)

    def perform_action(self, sentence: str) -> None:
        briefable_words = extract_double_quoted_words(sentence)
        briefables = [self.briefcase.search(word) for word in briefable_words]

        buf = io.StringIO()
        self.board.show_board(buf)
        board_repr = buf.getvalue()

        allies = zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", self.index.players)
        enemies = zip("abcdefghijklmnopqrstuvwxyz", self.index.enemies)

        tiles = [Tile(".", "Empty space")]

        for battler, abbrev, side in self.index.battlers_with_abbreviations_and_side():
            tiles.append(Tile(abbrev, f"{battler.name} ({side})"))

        rendered_prompt = render_text(
            "{% include('main_prompt.md') %}",
            context={
                "battlefield": board_repr,
                "allies": allies,
                "enemies": enemies,
                "tiles": tiles,
                "briefables": briefables,
                "sentence": sentence.strip("."),
            },
            consolidate=False,
        )
        print(rendered_prompt)

        llm = default_llm()
        result_content = llm.invoke(rendered_prompt).content

        # Extract the Python code from the result content
        pattern: re.Pattern = re.compile(
            r"^```(?:python)?(?P<code>[^`]*)", re.MULTILINE | re.DOTALL
        )

        match = pattern.search(result_content)
        if match is None:
            raise ValueError("No Python code found in the result content")
        python_code = match.group("code").strip()
        print(python_code)
        # print(python_code)
        # effects = self.evaluate_effects(python_code)
        # print(effects)

    def evaluate_effects(
        self, s: str, active_battler: Battler | None = None
    ) -> list[str]:
        tools = DMTools(battle_manager=self, active_battler=active_battler)
        exposed_api = {
            m: getattr(tools, m) for m in dir(tools) if not m.startswith("__")
        }
        exec(s, globals(), exposed_api)
        return tools.logs


class DMTools:
    def __init__(
        self, battle_manager: BattleManager, active_battler: Battler | None = None
    ) -> None:
        self.battle_manager = battle_manager
        self.logs = []
        self._active_battler = active_battler

    def active_battler(self) -> Battler:
        if self._active_battler is None:
            raise ValueError("No active battler set")
        return self._active_battler

    def prob_check(self, prob: float) -> bool:
        return random() < prob

    def battler(self, name: str) -> Battler:
        return self.battle_manager.index.search_battler(name)

    def log(self, message: str) -> None:
        self.logs.append(message)

    def repaint(self, board: str, legends: dict[str, str] | None = None) -> None:
        board = re.sub(r"\s*", "", board)
        legends = legends or {}
        old_legends = self.battle_manager.board.legends
        self.battle_manager.board = ASCIIBoard.parse_board(board)
        self.battle_manager.board.legends = {**old_legends, **legends}


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
            "This skill if hit deals one block of knockback.",
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

    briefcase = BriefCase()
    for item in [fireball, heal, slash, shield, normal_attack]:
        briefcase.add(item.name, item)

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
    battle_manager = BattleManager(allies, enemies, briefcase)
    while True:
        action = Prompt.ask("Enter action")
        battle_manager.perform_action(action)
