from __future__ import annotations

import uuid
import weakref
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from enum import Enum
from heapq import heappop, heappush
from typing import Annotated, Generic, Literal, TypeVar
from base64 import b32encode

import numpy as np
from smallperm import shuffle
from structlog import get_logger

from genio.core.base import access, promptly, slurp_toml
from genio.effect import (
    CreateCardEffect,
    DiscardCardsEffect,
    DrawCardsEffect,
    GlobalEffect,
    SinglePointEffect,
    StatusDefinition,
    parse_effect,
)
from genio.subst import Subst

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
            return f"<{self.name} {self.short_id()}: {self.description}>"
        return f"<{self.name} {self.short_id()}>"

    def short_id(self) -> str:
        return b32encode(bytes.fromhex(self.id[:8])).decode().lower()[:4]


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
    name: str = ""
    hit_points: int = 0


@dataclass(eq=True)
class PlayerProfile(Profile):
    profile: str = ""
    mp: int = 1

    @staticmethod
    def from_predef(key: str) -> PlayerProfile:
        return PlayerProfile(**access(predef, key))


@dataclass(eq=True)
class EnemyProfile(Profile):
    description: str = ""
    pattern: list[str] = field(default_factory=list)

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
    profile: Profile = field(default_factory=Profile)
    hp: int = 0
    max_hp: int = 0
    shield_points: int = 0
    status_effects: list[StatusEffect] = field(default_factory=list)

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
    
    @property
    def name_stem(self) -> str:
        return self.name.split(',')[0]

    def is_dead(self) -> bool:
        return self.hp <= 0

    def receive_damage(self, damage: int, pierce: bool = False) -> DamageResult:
        damage = int(damage)
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
        heal = int(heal)
        if heal < 0:
            raise ValueError("Heal must be a positive integer")
        actual_heal = min(self.max_hp - self.hp, heal)
        self.hp += actual_heal
        return HealResult(actual_heal)

    def on_turn_start(self) -> None:
        self.shield_points = 0

    def on_turn_end(self) -> None:
        for effect in self.status_effects:
            if effect.counter_type == "turns":
                effect.counter -= 1
        self.remove_dead_status_effects()

    def remove_dead_status_effects(self) -> None:
        self.status_effects = [
            effect for effect in self.status_effects if not effect.is_expired()
        ]

    def __hash__(self) -> int:
        return hash(self.uuid)


@dataclass
class PlayerBattler(Battler):
    profile: PlayerProfile = field(default_factory=PlayerProfile)
    mp: int = 0
    max_mp: int = 0

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
            mp=profile.mp,
            max_mp=profile.mp,
        )

    def __hash__(self) -> int:
        return hash(self.uuid)


@dataclass
class EnemyBattler(Battler):
    profile: EnemyProfile = field(default_factory=EnemyProfile)
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


@dataclass
class EffectGroup:
    parent: BattleBundle
    inner: list[tuple[Battler | None, SinglePointEffect | GlobalEffect, int]] = field(
        default_factory=list
    )
    enqueued = False

    def enqueue(self) -> None:
        if self.enqueued:
            raise ValueError("EffectGroup already enqueued")
        for effect in self.inner:
            self.parent.effects.append(key=effect[2], item=(effect[0], effect[1]))
            logger.info(
                "Effect queued",
                target=effect[0],
                effect=effect[1],
                queued_turn=effect[2],
            )
        self.enqueued = True

    def append(
        self, element: tuple[Battler | None, SinglePointEffect | GlobalEffect, int]
    ) -> None:
        if self.enqueued:
            raise ValueError("Cannot append to enqueued EffectGroup")
        self.inner.append(element)

    def __add__(self, other: EffectGroup) -> EffectGroup:
        if self.parent != other.parent:
            raise ValueError("Cannot add EffectGroups from different BattleBundles")
        if self.enqueued or other.enqueued:
            raise ValueError("Cannot add enqueued EffectGroups")
        return EffectGroup(self.parent, self.inner + other.inner)


def parse_top_level_brackets(s: str) -> list[str]:
    result = []
    stack = []
    start_idx = -1

    for i, char in enumerate(s):
        if char == "[":
            stack.append(char)
            if len(stack) == 1:
                start_idx = i
        elif char == "]":
            if stack:
                stack.pop()
                if len(stack) == 0 and start_idx != -1:
                    result.append(s[start_idx : i + 1])
                    start_idx = -1

    return result

@dataclass
class StatusEffect:
    defn: StatusDefinition
    counter: int
    owner: Battler

    _subst: Subst = field(init=False)

    def __post_init__(self):
        self._subst = self.defn.subst.replace("me", self.owner.name_stem)

    def apply(self, results: str) -> str:
        if self.is_expired():
            return results
        matches, modified = self._subst.apply(
            results, {"counter": self.counter}, allow_zero_matches=True
        )
        if self.counter_type == "times":
            self.counter -= matches
        return modified

    @property
    def counter_type(self) -> Literal["turns", "times"]:
        return self.defn.counter_type

    def is_expired(self) -> bool:
        return self.counter <= 0


T = TypeVar("T")


@dataclass(frozen=True)
class SortedListItem(Generic[T]):
    key: float | int
    item: T

    def __lt__(self, other: SortedListItem) -> bool:
        return self.key < other.key


class SortedList(Generic[T]):
    def __init__(self):
        self.data = []

    def append(self, key: float | int, item: T) -> None:
        heappush(self.data, SortedListItem(key, item))

    def peek(self) -> T | None:
        if self.data:
            return self.data[0].item
        return None

    def pop(self) -> T:
        return heappop(self.data).item

    def peek_with_key(self) -> tuple[float | int, T] | None:
        if self.data:
            return self.data[0].key, self.data[0].item
        return None

    def pop_with_key(self) -> tuple[float | int, T]:
        return heappop(self.data).key, self.data[0].item

    def __len__(self) -> int:
        return len(self.data)


@dataclass
class ResolvedEffects(
    Sequence[tuple[Battler | None, SinglePointEffect | GlobalEffect]]
):
    inner: list[tuple[Battler | None, SinglePointEffect | GlobalEffect]]

    def __getitem__(
        self, index: int
    ) -> tuple[Battler | None, SinglePointEffect | GlobalEffect]:
        return self.inner[index]

    def __len__(self) -> int:
        return len(self.inner)

    def effects(self) -> Iterator[SinglePointEffect | GlobalEffect]:
        for _, effect in self:
            yield effect

    def _total_attribute(self, attribute: str) -> int:
        return sum(
            getattr(effect, attribute)
            for effect in self.effects()
            if isinstance(effect, SinglePointEffect)
        )

    def total_damage(self) -> int:
        return self._total_attribute("damage")

    def total_heal(self) -> int:
        return self._total_attribute("heal")

    def total_shield_gain(self) -> int:
        return self._total_attribute("shield_gain")

    def total_shield_loss(self) -> int:
        return self._total_attribute("shield_loss")


class BattleBundle:
    effects: SortedList[tuple[Battler | None, SinglePointEffect | GlobalEffect]]
    postprocessors: list[weakref.WeakMethod]

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
        self.effects = SortedList()
        self.battle_prelude = battle_prelude
        self.card_bundle = card_bundle
        self.rng = np.random.default_rng()
        self.postprocessors = []
        self.event_listeners = []  # remember to use weakrefs

    def battlers(self) -> Iterator[Battler]:
        yield self.player
        yield from self.enemies

    def search(self, name: str) -> Battler:
        for battler in self.battlers():
            if name.lower() in battler.name.lower():
                return battler
        raise ValueError(f"No battler found with name '{name}'")

    def process_effects(
        self, result: str, autoenqueue: bool = True, aggregate_mode: bool = False
    ) -> EffectGroup:
        result = self.postprocess_result(result, aggregate_mode=aggregate_mode)
        substrings = parse_top_level_brackets(result)
        group = EffectGroup(self)
        for substring in substrings:
            parsed = parse_effect(substring)
            match parsed:
                case (target, effect):
                    if effect.noop:
                        continue
                    battler = self.search(target)
                    queued_turn = effect.delay + self.turn_counter
                    group.append((battler, effect, queued_turn))
                case effect:
                    queued_turn = effect.delay + self.turn_counter
                    group.append((None, effect, queued_turn))
        if autoenqueue:
            group.enqueue()
        return group

    def flush_expired_effects(
        self, rng: np.random.Generator | None = None
    ) -> ResolvedEffects:
        flushed = []
        if rng is None:
            rng = np.random.default_rng()
        while self.effects and self.effects.peek_with_key()[0] <= self.turn_counter:
            battler, effect = self.effects.pop()
            canceled = False
            new_effects = EffectGroup(self)
            for listener in self.event_listeners:
                response = listener(effect)
                if response == "cancel":
                    canceled = True
                    break
                elif response:
                    new_effects += self.process_effects(response, autoenqueue=False)
            if canceled:
                continue
            self.apply_effect(None, battler, effect, rng)
            flushed.append((battler, effect))
            logger.info(
                "Effect applied",
                battler=battler,
                effect=effect,
                turn_counter=self.turn_counter,
            )
            new_effects.enqueue()
        self.clear_dead()
        return ResolvedEffects(flushed)

    def process_and_flush_effects(self, result: str) -> ResolvedEffects:
        self.process_effects(result)
        return self.flush_expired_effects(self.rng)

    def _on_turn_start(self) -> None:
        for enemy in self.enemies:
            enemy.current_intent = enemy.profile.pattern[
                self.turn_counter % len(enemy.profile.pattern)
            ]

    def emit_battler_event(self, battler: Battler, event: str) -> None:
        self.process_effects(f"[{battler.name}: {event}]", aggregate_mode=True)
        self.flush_expired_effects(self.rng)

    def on_turn_end(self) -> None:
        self.turn_counter += 1
        for battler in self.battlers():
            self.emit_battler_event(battler, "end of turn")

    def resolve_player_cards(self, cards: list[Card]) -> None:
        resolved_results: ResolvedResults = _judge_results(
            cards,
            self.player,
            self.enemies,
            self.battle_prelude.description,
            resolve_player_actions=True,
        )
        self.process_effects(resolved_results.results)
        self.flush_expired_effects(self.rng)

    def resolve_enemy_actions(self) -> None:
        resolved_results: ResolvedResults = _judge_results(
            [],
            self.player,
            self.enemies,
            self.battle_prelude.description,
            resolve_player_actions=False,
        )
        self.process_effects(resolved_results.results)
        self.flush_expired_effects(self.rng)

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
            case DrawCardsEffect(_):
                self.card_bundle.draw_to_hand(effect.count)
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

        if effect.add_status:
            self._apply_add_status(target, effect.add_status)

    def _apply_add_status(
        self,
        target: Battler,
        status: tuple[StatusDefinition, int],
    ) -> None:
        realized = StatusEffect(status[0], status[1], target)
        target.status_effects.append(realized)
        self.postprocessors.append(weakref.WeakMethod(realized.apply))

    def postprocess_result(self, result: str, aggregate_mode: bool = False) -> str:
        self.postprocessors = [fn for fn in self.postprocessors if fn()]
        if aggregate_mode:
            return "\n".join([fn()(result) for fn in self.postprocessors])
        for fn in self.postprocessors:
            result = fn()(result)
        return result

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
        for enemy in self.enemies:
            enemy.on_turn_start()
        self.resolve_enemy_actions()
        self.on_turn_end()
        self.card_bundle.draw_to_hand()
        self._on_turn_start()
        self.player.on_turn_start()

    def clear_dead(self) -> None:
        if self.player.is_dead():
            raise ValueError("Player is dead")
        self.enemies = [enemy for enemy in self.enemies if not enemy.is_dead()]
        if not self.enemies:
            raise ValueError("All enemies are dead")


def setup_battle_bundle(
    deck: str,
    player: str,
    enemies: list[str],
) -> BattleBundle:
    card_bundle = CardBundle.from_predef(deck)
    card_bundle.draw_to_hand()
    player_instance = PlayerBattler.from_predef(player)
    enemy_instances = []
    enemies_with_count = Counter(enemies)
    for e, e_count in enemies_with_count.items():
        for i in range(e_count):
            enemy_instances.append(EnemyBattler.from_predef(e, i + 1))
    return BattleBundle(
        player_instance, enemy_instances, BattlePrelude.default(), card_bundle
    )
