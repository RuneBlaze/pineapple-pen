from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated

import numpy as np
from boltons.queueutils import HeapPriorityQueue
from smallperm import shuffle
from structlog import get_logger

from genio.core.base import access, promptly, slurp_toml
from genio.effect import (
    CreateCardEffect,
    DiscardCardsEffect,
    DrawCardsEffect,
    GlobalEffect,
    SinglePointEffect,
    parse_global_effect,
    parse_targeted_effect,
)

logger = get_logger()


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
        "Justification for the completion. How the *action* connects the concepts serially. If we are resolving a player's action, connect the cards that the player has played in sequence almost like a literary game. Do not include results in reason.",
    ]
    results: Annotated[
        str,
        (
            "The results of the actions taken by either the player or the enemies, and the consequences of those actions. "
            "The nuemrical deltas should be given in square brackets like [Slime: damaged 5]. "
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


@dataclass(frozen=True, eq=True)
class DamageResult:
    damage_dealt: int

    @staticmethod
    def default() -> DamageResult:
        return DamageResult(0)


@dataclass(frozen=True, eq=True)
class HealResult:
    heal_done: int

    @staticmethod
    def default() -> HealResult:
        return HealResult(0)


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

    def receive_damage(self, damage: int, pierce: bool = False) -> DamageResult:
        if damage < 0:
            raise ValueError("Damage must be a positive integer")
        if pierce:
            self.hp -= damage
            return DamageResult.default()
        shield_damage = min(self.shield_points, damage)
        rest_damage = max(damage - shield_damage, 0)
        self.shield_points -= shield_damage
        self.hp -= rest_damage
        if self.hp < 0:
            self.hp = 0
        return DamageResult(rest_damage)

    def receive_heal(self, heal: int) -> HealResult:
        if heal < 0:
            raise ValueError("Heal must be a positive integer")
        actual_heal = min(self.max_hp - self.hp, heal)
        self.hp += actual_heal
        return HealResult(actual_heal)

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
        self.events = []

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
        self.events.append("draw")

    def draw_to_hand(self, count: int | None = None) -> None:
        if count is None:
            count = self.hand_limit - len(self.hand)
        self.hand.extend(self.draw(count))
        self.events.append("draw_to_hand")

    def hand_to_graveyard(self, cards: list[Card]) -> None:
        remove_card_uuids = {card.id for card in cards}
        self.graveyard.extend(cards)
        self.hand = [card for card in self.hand if card.id not in remove_card_uuids]
        self.events.append("hand_to_graveyard")

    def flush_hand_to_graveyard(self) -> None:
        self.graveyard.extend(self.hand)
        self.hand = []
        self.events.append("flush_hand_to_graveyard")


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

    def battlers(self) -> Iterator[Battler]:
        yield self.player
        yield from self.enemies

    def search(self, name: str) -> Battler:
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
            logger.info(
                "Effect queued",
                target=target,
                effect=effect,
                queued_turn=queued_turn,
            )

    def flush_effects(self, rng: np.random.Generator | None = None) -> None:
        if rng is None:
            rng = np.random.default_rng()
        while self.effects and self.effects.peek()[0] <= self.turn_counter:
            _, battler, effect = self.effects.pop()
            self.apply_effect(None, battler, effect, rng)
            logger.info(
                "Effect applied",
                battler=battler,
                effect=effect,
                turn_counter=self.turn_counter,
            )
        self.clear_dead()

    def _on_turn_start(self) -> None:
        for enemy in self.enemies:
            enemy.current_intent = enemy.profile.pattern[
                self.turn_counter % len(enemy.profile.pattern)
            ]

    def _on_turn_end(self) -> None:
        self.turn_counter += 1

    def resolve_player_cards(self, cards: list[Card]) -> None:
        resolved_results: ResolvedResults = _judge_results(
            cards,
            self.player,
            self.enemies,
            self.battle_prelude.description,
            resolve_player_actions=True,
        )
        self.resolve_result(resolved_results.results)
        self.flush_effects(self.rng)

    def resolve_enemy_actions(self) -> None:
        resolved_results: ResolvedResults = _judge_results(
            [],
            self.player,
            self.enemies,
            self.battle_prelude.description,
            resolve_player_actions=False,
        )
        self.resolve_result(resolved_results.results)
        self.flush_effects(self.rng)

    def apply_effect(
        self,
        caster: Battler | None,
        target: Battler,
        effect: SinglePointEffect | GlobalEffect,
        rng: np.random.Generator,
    ) -> None:
        if isinstance(effect, GlobalEffect):
            self._apply_global_effect(effect)
        else:
            self._apply_targeted_effect(caster, target, effect, rng)

    def _apply_global_effect(self, effect: GlobalEffect) -> None:
        match effect:
            case DrawCardsEffect(count, _):
                self.card_bundle.draw_to_hand(count)
            case DiscardCardsEffect(count, _):
                pass
            case CreateCardEffect(card, _):
                pass

    def _apply_targeted_effect(
        self,
        caster: Battler | None,
        target: Battler,
        effect: SinglePointEffect,
        rng: np.random.Generator,
    ) -> None:
        if rng.random() > effect.accuracy:
            return

        is_critical = rng.random() < effect.critical_chance
        multiplier = 2 if is_critical else 1

        delta_hp = effect.delta_hp * multiplier
        delta_shield = effect.delta_shield * multiplier

        target.shield_points += delta_shield

        if delta_hp < 0:
            self._apply_damage(caster, target, effect, delta_hp)
        else:
            self._apply_healing(target, delta_hp)

    def _apply_damage(
        self,
        caster: Battler | None,
        target: Battler,
        effect: SinglePointEffect,
        delta_hp: float,
    ) -> None:
        if delta_hp > 0:
            raise ValueError("delta_hp for damage must be a negative number")
        damage = -delta_hp
        damage_result = target.receive_damage(damage, effect.pierce)
        if effect.drain and caster:
            caster.receive_heal(damage_result.damage_dealt)

    def _apply_healing(self, target: Battler, delta_hp: float) -> None:
        target.receive_heal(delta_hp)

    def end_player_turn(self) -> None:
        self.card_bundle.flush_hand_to_graveyard()
        self.resolve_enemy_actions()
        self._on_turn_end()
        self.card_bundle.draw_to_hand()
        self._on_turn_start()

    def clear_dead(self) -> None:
        if self.player.is_dead():
            raise ValueError("Player is dead")
        self.enemies = [enemy for enemy in self.enemies if not enemy.is_dead()]
        if not self.enemies:
            raise ValueError("All enemies are dead")
