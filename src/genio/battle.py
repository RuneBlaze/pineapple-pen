from __future__ import annotations

import math
import uuid
import weakref
from collections import Counter, deque
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import cache, cached_property
from heapq import heappop, heappush
from itertools import chain
from random import randint
from typing import Annotated, Generic, Literal

import numpy as np
import tiktoken
from parse import parse
from smallperm import sample, shuffle
from structlog import get_logger
from typing_extensions import (
    Any,
    Protocol,
    TypeVar,
)

from genio.artifacts import parse_stylize
from genio.card import Card
from genio.components import CanAddAnim
from genio.core.base import access, promptly
from genio.effect import (
    CreateCardEffect,
    DestroyCardEffect,
    DestroyRuleEffect,
    DiscardCardsEffect,
    DrawCardsEffect,
    DuplicateCardEffect,
    GlobalEffect,
    SinglePointEffect,
    SinglePointEffectType,
    StatusDefinition,
    TransformCardEffect,
    parse_effect,
)
from genio.gears.card_printer import CardPrinter
from genio.gears.sentence_embed import Corpus
from genio.predef import access_predef, predef
from genio.subst import Subst

logger = get_logger()


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


from parse import search


def create_deck(cards: list[str]) -> list[Card]:
    deck = []
    for card_description in cards:
        name, desc, copies = parse_card_description(card_description)
        effective_name = None
        if "[" in name:
            main_part, bracket_part = search("{}[{}]", name).fixed
            name = main_part
            effective_name = bracket_part

        for _ in range(copies):
            deck.append(Card(name=name, description=desc, card_art_name=effective_name))
    return deck


@dataclass
class ResolvedResults:
    """A completed sentence in the game. An occurrence, a line, of the game's narrative."""

    reason: Annotated[
        str,
        "Justification for the completion. How the *action* connects the concepts serially. If we are resolving a player's action, connect the cards that the player has played in sequence almost like a literary game. Do not include results in reason. Note that this is only the natural language justification.",
    ]
    results: Annotated[
        str,
        (
            "The results of the actions taken by either the player or the enemies, and the consequences of those actions. "
            "The nuemrical deltas should be given in square brackets like [Slime: damaged 5], or like [transform mplx to <mplify: enhance the power of one card for one turn.>]. If transforming, remember to give new and creative descriptions (after the colon) to the transformed cards. For example, if you are doing [transform 5yij to <lash: Deal 2 damage to a target.>;]\n[transform euxh to <ight: located on the right side.>;] then you are doing it wrong, as the descriptions are not new or not creative. Unleash your inner game designer."
        ),
    ]
    significance: Annotated[
        int,
        "The significance of the action, on a scale of 1 - 3 inclusive. 1 means the action is run-of-the-mill, 2 mean that it is a good play and relatively rare (e.g., two times per battle), and 3 means that it is a game-changing play and very rare (e.g., once per several battles).",
    ]


@promptly()
def _judge_results(
    cards: list[Card],
    user: PlayerBattler,
    enemies: list[EnemyBattler],
    battle_context: str,
    player_hand: list[Card],
    resolve_player_actions: bool = True,
    additional_guidance: list[str] | None = None,
    rules: list[str] | None = None,
) -> ResolvedResults:
    """\
    {% include('judge.md') %}

    {{ formatting_instructions }}

    Let's think step by step.
    """
    ...


executor = ThreadPoolExecutor(2)


@dataclass
class StatusDefinitionInterpretation:
    interpretation: Annotated[
        str,
        "The description of the status effect. Don't include the name of the status effect itself -- no extra formatting. Just explain it plainly in one sentence. For example: 'takes 1 damage at the end of each turn.'",
    ]


@promptly()
def _interpret_status_effect(
    status_effect_name: str,
    status_effect_subst: str,
) -> StatusDefinitionInterpretation:
    """\
    {% include('interpret_status_effects.md') %}

    {{ formatting_instructions }}
    """
    ...


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
    description: Annotated[str, ""] = ""
    pattern: Annotated[list[str], ""] = field(default_factory=list)
    chara: Annotated[str, ""] = "enemy_killer_flower.png"

    @staticmethod
    def from_predef(key: str) -> EnemyProfile:
        return EnemyProfile(**access(predef, key))


@dataclass
class GeneratableEnemyProfile:
    name: Annotated[str, "The name of the enemy."]
    hit_points: Annotated[int, "The hit points of the enemy."]
    description: Annotated[str, "The description of the enemy."]
    pattern: Annotated[
        list[str],
        "The pattern of the enemy, as like a list of actions the enemy will take. Take inspiration from slay-the-spire. Be precise and concise, e.g., actions should come with the precise numerics.",
    ]

    def to_enemy_profile(self) -> EnemyProfile:
        return EnemyProfile(
            name=self.name,
            hit_points=self.hit_points,
            description=self.description,
            pattern=self.pattern,
            chara=self.name.lower(),
        )


@promptly()
def _generate_enemy_profile(
    idea: str,
) -> GeneratableEnemyProfile:
    """\
    Act as an excellent game designer and create an enemy profile that is inspired by the given inspiration.

    For context, normal enemies normally have between 3 to 7 hit points, and their patterns are a list of strings that represent their actions. The description is a short description of the enemy from a lore perspective.

    Your should adhere to this idea for your generation:

    {{ idea }}

    Here is the syntax for the types of "moves" you might consider. Note that this is only an example
    for style guidance.

    ```json5
    // Example for one pattern of enemy
    ["attack player for 2 damage", "block for 1 shield points"]
    ```

    {{ formatting_instructions }}
    """


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
        return self.name.split(",")[0]

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
    mp: int = 10
    max_mp: int = 10

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

    @property
    def chara(self) -> str:
        return self.profile.chara

    def __hash__(self) -> int:
        return hash(self.uuid)


@dataclass
class BattlePrelude:
    description: str

    @staticmethod
    def default() -> BattlePrelude:
        return BattlePrelude("It's a brightly lit cave, with torches lining the walls.")


class EventBusListener(Protocol):
    def __call__(self, topic: str, *userdata: Any) -> None:
        ...


class EventBus:
    def __init__(self):
        self.events = deque()
        self._listener = None

    def append(self, topic: str, *userdata: Any) -> None:
        if not self._listener:
            self.events.append((topic, *userdata))
        else:
            self._listener(topic, *userdata)

    def register_listener(self, listener: EventBusListener) -> None:
        if self._listener:
            raise ValueError("Listener already registered")
        self._listener = listener
        while self.events:
            topic, *userdata = self.events.popleft()
            listener(topic, *userdata)


class CardBundle:
    def __init__(self, deck: list[Card], hand_limit: int = 10) -> None:
        self.hand_limit = hand_limit
        self.default_draw_count = 6

        seed = access_predef("system.seed", randint(0, 2**32 - 1))
        logger.info("CardBundle created", seed=seed)

        self.deck = shuffle(deck, seed=seed)
        self.hand = []
        self.graveyard = []
        self.resolving = []

        self.events = EventBus()

    def seek_card(self, expr: str) -> Card:
        if match := parse(expr, "#{:d}"):
            card_number = match.fixed[0]
            return self.deck[card_number]
        for card in chain(self.deck, self.hand, self.graveyard, self.resolving):
            if card.name.lower() == expr.lower():
                return card
            if card.short_id() == expr.lower():
                return card
        raise ValueError(f"No card found with name '{expr}'")

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
            count = self.default_draw_count - len(self.hand)
        self.hand.extend(self.draw(count))
        self.events.append("draw_to_hand")

    def hand_to_graveyard(self, cards: list[Card]) -> None:
        remove_card_uuids = {card.id for card in cards}
        self.graveyard.extend(cards)
        self.hand = [card for card in self.hand if card.id not in remove_card_uuids]
        self.events.append("hand_to_graveyard")

    def destroy_cards(self, cards: list[Card]) -> None:
        remove_card_uuids = {card.id for card in cards}
        self.hand = [card for card in self.hand if card.id not in remove_card_uuids]
        self.deck = [card for card in self.deck if card.id not in remove_card_uuids]
        self.graveyard = [
            card for card in self.graveyard if card.id not in remove_card_uuids
        ]
        self.resolving = [
            card for card in self.resolving if card.id not in remove_card_uuids
        ]
        self.events.append("destroy_cards", cards)

    def hand_to_resolving(self, cards: list[Card]) -> None:
        remove_card_uuids = {card.id for card in cards}
        self.resolving.extend(cards)
        self.hand = [card for card in self.hand if card.id not in remove_card_uuids]
        self.events.append("hand_to_resolving")

    def flush_hand_resolving_to_graveyard(self) -> None:
        self.graveyard.extend(self.hand)
        self.graveyard.extend(self.resolving)
        self.hand = []
        self.resolving = []
        self.events.append("flush_hand_resolving_to_graveyard")

    def add_to_hand(self, card: Card | list[Card]) -> None:
        if isinstance(card, Sequence):
            for c in card:
                self.add_to_hand(c)
            return
        if len(self.hand) >= self.hand_limit:
            self.graveyard.append(card)
        else:
            self.hand.append(card)
        self.events.append("add_to_hand")

    def add_to_graveyard(self, card: Card | list[Card]) -> None:
        if isinstance(card, Sequence):
            for c in card:
                self.add_to_graveyard(c)
            return
        self.graveyard.append(card)
        self.events.append("add_to_graveyard")

    def shuffle_into_deck(self, card: Card | list[Card]) -> None:
        if isinstance(card, Sequence):
            for c in card:
                self.shuffle_into_deck(c)
            return
        ix = self.rng.integers(len(self.deck) + 1)
        self.deck.insert(ix, card)

    def add_into_deck_top(self, card: Card | list[Card]) -> None:
        if isinstance(card, Sequence):
            for c in card:
                self.add_into_deck_top(c)
            return
        self.deck.append(card)

    def has_card(self, card_name: str) -> Literal["deck", "hand", "graveyard"] | None:
        for card in self.deck:
            if card.name.lower() == card_name.lower():
                return "deck"
        for card in self.hand:
            if card.name.lower() == card_name.lower():
                return "hand"
        for card in self.graveyard:
            if card.name.lower() == card_name.lower():
                return "graveyard"
        return None

    def count_cards(self, card_name: str, granular: bool = False) -> Counter[str] | int:
        counter = Counter(
            [
                card.name.lower()
                for card in self.deck + self.hand + self.graveyard
                if card.name.lower() == card_name.lower()
            ]
        )
        if not granular:
            return sum(counter.values())
        return counter

    def transform_card(self, from_card: Card, to_card: Card) -> None:
        from_card.name = to_card.name
        from_card.description = to_card.description
        self.events.append("transform_card", from_card.id)


@dataclass
class Artifact:
    name: str
    description: str


class HasDescription(Protocol):
    description: str


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


def postprocess_common_mistake(s: str) -> list[str]:
    num_semicolons = s.count(";")
    if num_semicolons <= 1:
        return [s]
    # split by semicolon
    segs = s.split(";")
    processed_segs = []
    for seg in segs:
        seg = seg.strip()
        if not seg.endswith("]"):
            seg += "]"
        if not seg.startswith("["):
            seg = "[" + seg
        processed_segs.append(seg)
    logger.info("Common mistake detected", s=s, processed_segs=processed_segs)
    return processed_segs


def flat_map(fn, iterable):
    return chain.from_iterable(map(fn, iterable))


@cache
def iconset() -> Corpus[int]:
    strings = []
    ids = []
    for k, v in predef["icons"].items():
        strings.append(v)
        ids.append(int(k))
    return Corpus(strings, ids)


iconset()


@dataclass
class StatusEffect:
    defn: StatusDefinition
    counter: int
    owner: Battler

    _subst: Subst = field(init=False)

    description: str = ""

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

    @property
    def name(self) -> str:
        return self.defn.name

    @cached_property
    def icon_id(self) -> int:
        return iconset().search(self.defn.name)[1]

    def is_expired(self) -> bool:
        return self.counter <= 0

    def _describe_myself(self) -> None:
        subst = self.defn.subst.show()
        name = self.defn.name
        interpreted = _interpret_status_effect(name, subst)
        self.description = interpreted.interpretation

    def describe_myself(self) -> str:
        # TODO: cache this and also for consistency keep only one way of getting description
        if not self.description:
            executor.submit(self._describe_myself)
        return self.description


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
    rarity: int = -1

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


@cache
def _calculate_total_cost(cards: tuple[Card, ...]) -> int:
    return calculate_energy_cost(cards)


def calculate_total_cost(cards: list[Card]) -> int:
    sorted_cards = sorted(cards, key=lambda card: card.name)
    return _calculate_total_cost(tuple(sorted_cards))


class BattleBundle:
    effects: SortedList[tuple[Battler | None, SinglePointEffect | GlobalEffect]]
    postprocessors: list[weakref.WeakMethod]
    proposed_cards: list[Card]
    player_artifacts: list[Artifact]
    rules: list[str | None]

    def __init__(
        self,
        player: PlayerBattler,
        enemies: list[EnemyBattler],
        battle_prelude: BattlePrelude,
        card_bundle: CardBundle,
    ) -> None:
        self.player = player
        self.player_artifacts = []
        self.enemies = enemies
        self.turn_counter = 0
        self.effects = SortedList()
        self.battle_prelude = battle_prelude
        self.card_bundle = card_bundle
        self.rng = np.random.default_rng()
        self.postprocessors = []
        self.event_listeners = []  # remember to use weakrefs
        self.default_energy = 2
        self.energy = self.default_energy
        self.proposed_cards = []
        self.battle_logs = []
        self.rules = [None] + access_predef("rules.default")

    def active_items_with_description(self) -> Iterator[HasDescription]:
        for card in self.card_bundle.hand:
            yield card
        for card in self.card_bundle.resolving:
            yield card
        yield from self.player_artifacts

    def prompt_injections(self) -> Iterator[str]:
        for has_description in self.active_items_with_description():
            yield from parse_stylize(has_description.description)

    def tentative_energy_cost(self) -> int:
        return calculate_total_cost(self.proposed_cards)

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
        substrings = flat_map(
            postprocess_common_mistake, parse_top_level_brackets(result)
        )
        group = EffectGroup(self)
        for substring in substrings:
            try:
                parsed = parse_effect(substring, self.card_bundle)
            except ValueError:
                logger.exception("Error parsing effect", substring=substring)
                continue
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
        self.turn_counter += 1
        for enemy in self.enemies:
            enemy.current_intent = enemy.profile.pattern[
                self.turn_counter % len(enemy.profile.pattern)
            ]

    def emit_battler_event(self, battler: Battler, event: str) -> None:
        self.process_effects(f"[{battler.name}: {event}]", aggregate_mode=True)
        self.flush_expired_effects(self.rng)

    def on_turn_end(self) -> None:
        for battler in self.battlers():
            self.emit_battler_event(battler, "end of turn")

    def resolve_player_cards(self, cards: list[Card]) -> ResolvedEffects:
        self.deduct_energy(calculate_total_cost(cards))
        resolved_results: ResolvedResults = _judge_results(
            cards,
            self.player,
            self.enemies,
            self.battle_prelude.description,
            player_hand=self.card_bundle.hand,
            resolve_player_actions=True,
            additional_guidance=list(self.prompt_injections()),
            rules=self.formatted_rules(),
        )
        self.process_effects(resolved_results.results)
        expired_effects = self.flush_expired_effects(self.rng)
        expired_effects.rarity = resolved_results.significance
        return expired_effects

    def resolve_enemy_actions(self) -> ResolvedEffects:
        resolved_results: ResolvedResults = _judge_results(
            [],
            self.player,
            self.enemies,
            self.battle_prelude.description,
            player_hand=self.card_bundle.hand,
            resolve_player_actions=False,
            rules=self.formatted_rules(),
        )
        self.process_effects(resolved_results.results)
        expired_effects = self.flush_expired_effects(self.rng)
        return expired_effects

    def record_to_battle_logs(self, effects: ResolvedEffects) -> None:
        logs = self._transform_to_battle_logs(effects)
        self.battle_logs.extend(logs)

    def _transform_to_battle_logs(self, effects: ResolvedEffects) -> list[str]:
        logs = []

        def append_log(msg: str) -> None:
            logs.append(f"Turn {self.turn_counter}: {msg}")

        def humanize_cards(cards: list[Card]) -> str:
            return ", ".join([card.name for card in cards])

        for effect in effects:
            match effect:
                case (None, global_effect) if isinstance(global_effect, GlobalEffect):
                    match global_effect:
                        case DrawCardsEffect(_) as draw:
                            append_log(f"Draw {draw.count} cards")
                        case DiscardCardsEffect(_) as discard:
                            append_log(
                                f"Discard {discard.count} cards: specifically {humanize_cards(discard.specifics)}"
                            )
                        case CreateCardEffect(_) as create_card:
                            append_log(
                                f"Create {create_card.copies} {create_card.card.name}"
                            )
                        case DuplicateCardEffect(_) as duplicate:
                            append_log(
                                f"Duplicate {duplicate.copies} {duplicate.card.name}"
                            )
                        case TransformCardEffect(_) as transform:
                            append_log(
                                f"Transform {transform.from_card.name} to {transform.to_card.name}"
                            )
                        case other:
                            ...
                case (battler, single_effect) if isinstance(
                    single_effect, SinglePointEffect
                ):
                    match single_effect.classify_type():
                        case SinglePointEffectType.DAMAGE:
                            append_log(
                                f"{battler.name} received damage {single_effect.damage}"
                            )
                        case SinglePointEffectType.HEAL:
                            append_log(
                                f"{battler.name} received healing {single_effect.heal}"
                            )
                        case SinglePointEffectType.SHIELD_GAIN:
                            append_log(
                                f"{battler.name} gained shield {single_effect.shield_gain}"
                            )
                        case SinglePointEffectType.SHIELD_LOSS:
                            append_log(
                                f"{battler.name} lost shield {single_effect.shield_loss}"
                            )
                        case SinglePointEffectType.STATUS:
                            append_log(
                                f"{battler.name} received status {single_effect.add_status[0].name}"
                            )
                        case SinglePointEffectType.OTHER:
                            append_log(f"{battler.name} received other effect...")
                case _:
                    raise ValueError("Invalid effect type")
        return logs

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

    def deduct_energy(self, cost: int) -> None:
        self.energy = max(0, self.energy - cost)

    def _next_seed(self) -> int:
        return self.rng.integers(2**32)

    def _apply_global_effect(self, effect: GlobalEffect) -> None:
        match effect:
            case DrawCardsEffect(_):
                self.card_bundle.draw_to_hand(effect.count)
            case DiscardCardsEffect(_) as discard:
                if discard.count:
                    to_be_discarded_count = min(
                        discard.count, len(self.card_bundle.hand)
                    )
                    to_be_discarded = sample(
                        self.card_bundle.hand,
                        to_be_discarded_count,
                        seed=self._next_seed(),
                    )
                elif discard.specifics:
                    to_be_discarded = discard.specifics
                else:
                    to_be_discarded = []
                self.card_bundle.hand_to_graveyard(to_be_discarded)
            case CreateCardEffect(_) as create_card:
                cards = [
                    create_card.card.duplicate() for _ in range(create_card.copies)
                ]
                match create_card.where:
                    case "deck_top":
                        self.card_bundle.add_into_deck_top(cards)
                    case "deck":
                        self.card_bundle.shuffle_into_deck(cards)
                    case "hand":
                        self.card_bundle.add_to_hand(cards)
                    case "graveyard":
                        self.card_bundle.add_to_graveyard(cards)
            case DuplicateCardEffect(_) as duplicate:
                cards = [duplicate.card.duplicate() for _ in range(duplicate.copies)]
                match duplicate.where:
                    case "deck_top":
                        self.card_bundle.add_into_deck_top(cards)
                    case "deck":
                        self.card_bundle.shuffle_into_deck(cards)
                    case "hand":
                        self.card_bundle.add_to_hand(cards)
                    case "graveyard":
                        self.card_bundle.add_to_graveyard(cards)
            case TransformCardEffect(_) as transform:
                self.card_bundle.transform_card(transform.from_card, transform.to_card)
            case DestroyCardEffect(_) as destroy:
                to_destroy = destroy.cards
                self.card_bundle.destroy_cards(to_destroy)
            case DestroyRuleEffect(_) as destroy_rule:
                rule_id = destroy_rule.rule_id
                if rule_id < 1 or rule_id >= len(self.rules):
                    logger.error("Invalid rule ID", rule_id=rule_id)
                    return
                self.rules[rule_id] = None

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
        realized.describe_myself()
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
        for enemy in self.enemies:
            enemy.on_turn_start()
        self.on_turn_end()

    def start_new_turn(self) -> None:
        self.card_bundle.flush_hand_resolving_to_graveyard()
        self.card_bundle.draw_to_hand()
        self.replenish_energy()
        self._on_turn_start()
        self.player.on_turn_start()

    def replenish_energy(self) -> None:
        self.energy = max(self.default_energy, self.energy)

    def clear_dead(self) -> None:
        if self.player.is_dead():
            # TODO: actually provide game over.
            raise ValueError("Player is dead. The bar explodes, game over.")
        for enemy in self.enemies:
            if enemy.is_dead():
                self.battle_logs.append(
                    f"Turn {self.turn_counter}: {enemy.name} has fallen."
                )
        self.enemies = [enemy for enemy in self.enemies if not enemy.is_dead()]

    def is_player_victory(self) -> bool:
        return not self.enemies

    def formatted_rules(self) -> list[str]:
        def f(ix: int, rule: str | None) -> list[str]:
            if not rule:
                return []
            ix_fmt = str(ix).zfill(2)
            return [f"{rule} (R{ix_fmt})"]

        def g(t: tuple[int, str | None]) -> list[str]:
            return f(*t)

        return list(flat_map(g, enumerate(self.rules)))


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


class MainSceneLike(CanAddAnim, Protocol):
    bundle: BattleBundle
    card_printer: CardPrinter

    def should_all_cards_disabled(self) -> bool:
        ...

    def should_wait_until_animation(self) -> bool:
        ...


enc = tiktoken.get_encoding("o200k_base")


def num_tokens(s: str | None) -> int:
    if not s:
        return 0
    return len(enc.encode(s, allowed_special="all"))


def calculate_energy_cost(cards: Sequence[Card]) -> int:
    if not cards:
        return 0
    cost = 1
    num_effective_tokens = 0
    for card in cards:
        num_effective_tokens += math.sqrt(max(num_tokens(card.description) - 5, 0))
        num_effective_tokens += math.sqrt(max(num_tokens(card.name) - 5, 0))
    if num_effective_tokens > 20:
        cost += 1
    if num_effective_tokens > 10:
        cost += 1
    return cost
