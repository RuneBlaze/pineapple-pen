from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Protocol

import numpy as np
from boltons.queueutils import HeapPriorityQueue
from smallperm import shuffle

from genio.core.base import access, promptly, slurp_toml
from genio.effect import (
    CreateCardEffect,
    DamageEffect,
    DiscardCardsEffect,
    DrawCardsEffect,
    GlobalEffect,
    parse_global_effect,
    parse_targeted_effect,
)


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
    resolve_player_actions: bool = True,
) -> ResolvedResults:
    """\
    {% include('judge.md') %}

    {{ formatting_instructions }}

    Let's think step by step.
    """
    ...

predef = slurp_toml("assets/strings.toml")


@dataclass(eq=True)
class Profile:
    name: str
    hit_points: int


@dataclass(eq=True)
class PlayerProfile(Profile):
    profile: str

    @staticmethod
    def from_predef(key: str) -> PlayerProfile:
        return PlayerProfile(**access(predef, key))


@dataclass(eq=True)
class EnemyProfile(Profile):
    description: str
    pattern: list[str]

    @staticmethod
    def from_predef(key: str) -> EnemyProfile:
        return EnemyProfile(**access(predef, key))


class BattlerLike(Protocol):
    def is_dead(self) -> bool:
        ...

    def receive_damage(self, damage: int) -> None:
        ...


@dataclass(eq=True)
class Battler:
    profile: Profile
    hp: int
    max_hp: int
    shield_points: int

    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))

    @staticmethod
    def from_profile(profile: Profile) -> Battler:
        return Battler(
            profile=profile,
            hp=profile.hit_points,
            max_hp=profile.hit_points,
            shield_points=0,
        )

    @property
    def name(self) -> str:
        return self.profile.name

    def is_dead(self) -> bool:
        return self.hp <= 0

    def receive_damage(self, damage: int) -> None:
        self.hp -= damage
        if self.hp < 0:
            self.hp = 0

    def __hash__(self) -> int:
        return hash(self.uuid)


@dataclass
class PlayerBattler(Battler):
    profile: PlayerProfile

    @staticmethod
    def from_predef(key: str) -> PlayerBattler:
        return PlayerBattler.from_profile(PlayerProfile.from_predef(key))

    @staticmethod
    def from_profile(profile: PlayerProfile) -> PlayerBattler:
        return PlayerBattler(
            profile=profile,
            hp=profile.hit_points,
            max_hp=profile.hit_points,
            shield_points=0,
        )

    def __hash__(self) -> int:
        return hash(self.uuid)


@dataclass
class EnemyBattler(Battler):
    profile: EnemyProfile
    copy_number: int = 1
    current_intent: str = field(init=False)

    def __post_init__(self):
        self.current_intent = self.profile.pattern[0]

    @staticmethod
    def from_predef(key: str, copy_number: int = 1) -> EnemyBattler:
        return EnemyBattler.from_profile(EnemyProfile.from_predef(key), copy_number)

    @staticmethod
    def from_profile(profile: EnemyProfile, copy_number: int = 1) -> EnemyBattler:
        return EnemyBattler(
            profile=profile,
            hp=profile.hit_points,
            max_hp=profile.hit_points,
            shield_points=0,
            copy_number=copy_number,
        )

    @property
    def name(self) -> str:
        alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return f"{self.profile.name} {alpha[self.copy_number - 1]}"

    @property
    def description(self) -> str:
        return self.profile.description

    def __hash__(self) -> int:
        return hash(self.uuid)


@dataclass
class BattlePrelude:
    description: str

    @staticmethod
    def default() -> BattlePrelude:
        return BattlePrelude("It's a brightly lit cave, with torches lining the walls.")


class CardBundle:
    def __init__(self, deck: list[Card], hand_limit: int = 6) -> None:
        self.deck = shuffle(deck)
        self.hand = []
        self.graveyard = []
        self.hand_limit = hand_limit

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

    def draw_to_hand(self, count: int | None = None) -> None:
        if count is None:
            count = self.hand_limit - len(self.hand)
        self.hand.extend(self.draw(count))


class BattleBundle:
    def __init__(
        self,
        player: PlayerBattler,
        enemies: list[EnemyBattler],
        battle_prelude: BattlePrelude,
        card_bundle: CardBundle,
    ) -> None:
        self.player = player
        self.enemies = enemies
        self.turn_counter = 0
        self.effects = HeapPriorityQueue(priority_key=lambda x: -x)
        self.battle_prelude = battle_prelude
        self.card_bundle = card_bundle
        self.rng = np.random.default_rng()

    def battlers(self) -> Iterator[BattlerLike]:
        yield self.player
        yield from self.enemies

    def search(self, name: str) -> BattlerLike:
        for battler in self.battlers():
            if name.lower() in battler.name.lower():
                return battler
        raise ValueError(f"No battler found with name '{name}'")

    def resolve_result(self, result: str) -> None:
        global_pattern = r"\[\[.*?\]\]"
        substrings = re.findall(global_pattern, result)
        for substring in substrings:
            effect = parse_global_effect(substring)
            queued_turn = effect.delay + self.turn_counter
            self.effects.add((queued_turn, None, effect), queued_turn)
        targeted_pattern = r"(\[.*?\])"
        substrings = re.findall(targeted_pattern, result)
        for substring in substrings:
            if "[[" in substring:
                continue
            target, effect = parse_targeted_effect(substring)
            battler = self.search(target)
            queued_turn = effect.delay + self.turn_counter
            self.effects.add((queued_turn, battler, effect), queued_turn)

    def flush_effects(self, rng: np.random.Generator) -> None:
        while self.effects and self.effects.peek()[0] <= self.turn_counter:
            _, battler, effect = self.effects.pop()
            self.apply_effect(None, battler, effect, rng)

    def _on_turn_start(self) -> None:
        for enemy in self.enemies:
            enemy.current_intent = enemy.profile.pattern[
                self.turn_counter % len(enemy.profile.pattern)
            ]

    def _on_turn_end(self) -> None:
        self.turn_counter += 1
    
    def resolve_player_cards(self, cards: list[Card]) -> None:
        resolved_results: ResolvedResults = _judge_results(cards, self.player, self.enemies, self.battle_prelude.description, resolve_player_actions=True)
        self.resolve_result(resolved_results.results)
        self.flush_effects(self.rng)

    def resolve_enemy_actions(self) -> None:
        resolved_results: ResolvedResults = _judge_results([], self.player, self.enemies, self.battle_prelude.description, resolve_player_actions=False)
        self.resolve_result(resolved_results.results)
        self.flush_effects(self.rng)

    def apply_effect(
        self,
        caster: Battler | None,
        target: Battler,
        effect: DamageEffect | GlobalEffect,
        rng: np.random.Generator,
    ) -> None:
        if isinstance(effect, GlobalEffect):
            match effect:
                case DrawCardsEffect(count, _):
                    self.card_bundle.draw_to_hand(count)
                case DiscardCardsEffect(count, _):
                    pass
                case CreateCardEffect(card, _):
                    pass
            return
        # Check accuracy
        if rng.random() > effect.accuracy:
            return

        # Calculate if critical hit
        is_critical = rng.random() < effect.critical_chance
        multiplier = 2 if is_critical else 1

        # Calculate actual damage and shield reduction
        delta_hp = effect.delta_hp * multiplier
        delta_shield = effect.delta_shield * multiplier

        if delta_hp < 0:
            if effect.pierce:
                # Ignore shield, apply all damage to HP
                target.hp += delta_hp
            else:
                # Reduce shield points first
                remaining_damage = delta_hp + target.shield_points
                target.shield_points += delta_shield
                if target.shield_points < 0:
                    target.shield_points = 0

                # Apply remaining damage to HP
                if remaining_damage < 0:
                    target.hp += remaining_damage
        else:
            # Healing effect
            target.hp += delta_hp
            if target.hp > target.max_hp:
                target.hp = target.max_hp

        if target.hp < 0:
            target.hp = 0

        # Drain effect: heal the caster if applicable
        if effect.drain and caster:
            caster.hp -= delta_hp
            if caster.hp > caster.max_hp:
                caster.hp = caster.max_hp
