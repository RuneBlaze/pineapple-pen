from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, TypeAlias
from uuid import uuid4

from parse import search

from genio.card import Card
from genio.subst import Subst


@dataclass(eq=True, frozen=True)
class BaseEffect:
    delay: int = 0
    critical_chance: float = 0.0
    pierce: bool = False
    drain: bool = False
    accuracy: float = 1.0
    noop: bool = False
    _uuid: str = field(default_factory=lambda: uuid4().hex)

    def equals_except_uuid(self, other: BaseEffect) -> bool:
        return self.__dict__ | {"_uuid": None} == other.__dict__ | {"_uuid": None}


@dataclass
class StatusDefinition:
    name: str
    subst: Subst
    counter_type: Literal["turns", "times"]


@dataclass(eq=True, frozen=True)
class SinglePointEffect(BaseEffect):
    delta_shield: int = 0
    delta_hp: int = 0
    add_status: tuple[StatusDefinition, int] | None = None
    remove_status: str | None = None

    @staticmethod
    def from_damage(damage: int, pierce: bool = False) -> SinglePointEffect:
        return SinglePointEffect(delta_hp=-damage, pierce=pierce)

    @staticmethod
    def from_heal(heal: int) -> SinglePointEffect:
        return SinglePointEffect(delta_hp=heal)

    @staticmethod
    def noop_effect() -> SinglePointEffect:
        return SinglePointEffect(noop=True)

    @property
    def damage(self) -> int:
        return max(-self.delta_hp, 0)

    @property
    def heal(self) -> int:
        return max(self.delta_hp, 0)

    @property
    def shield_gain(self) -> int:
        return max(self.delta_shield, 0)

    @property
    def shield_loss(self) -> int:
        return max(-self.delta_shield, 0)


@dataclass(eq=True, frozen=True)
class GlobalEffect(BaseEffect):
    pass


@dataclass(eq=True, frozen=True)
class DrawCardsEffect(GlobalEffect):
    count: int = 1


@dataclass(eq=True, frozen=True)
class DiscardCardsEffect(GlobalEffect):
    count: int = 0
    specifics: list[str] = field(default_factory=list)


@dataclass(eq=True, frozen=True)
class CreateCardEffect(GlobalEffect):
    card: Card = field(default_factory=Card)
    where: Literal["deck_top", "deck", "hand", "graveyard"] = "hand"
    copies: int = 1


TargetedEffect: TypeAlias = tuple[str, SinglePointEffect]
Effect: TypeAlias = GlobalEffect | TargetedEffect


def parse_global_effect(modifier: str) -> GlobalEffect:
    match = re.match(r"\[(.*)\]", modifier)
    if not match:
        raise ValueError("Invalid format")
    effect = match.group(1).strip()

    tokens = effect.split("|")
    common_modifiers = parse_common_modifiers(tokens)

    if "draw" in effect:
        count = int(tokens[0].split(" ")[1])
        return DrawCardsEffect(count=count, **common_modifiers)
    elif "discard" in effect:
        count = int(tokens[0].split(" ")[1])
        return DiscardCardsEffect(count=count, **common_modifiers)
    elif "create" in effect:
        card_desc, postfix, where = search("[create <{}>{}in {:w}", modifier).fixed
        card_desc = f"<{card_desc}>"
        mult = 1
        if mult_expr := postfix.replace(" ", ""):
            mult = search("*{:d}", mult_expr).fixed[0]
        card = Card.parse(card_desc)
        return CreateCardEffect(card=card, where=where, copies=mult, **common_modifiers)
    else:
        raise ValueError(f"Invalid format: {effect}")


def parse_targeted_effect(modifier: str) -> TargetedEffect:
    status_effect_pat = "[{}: +{} [{:d} {:w}] {};]"
    if match := search(status_effect_pat, modifier):
        entity, name, counter, counter_type, effects = match.fixed
        tokens = effects.split("|")
        common_modifiers = parse_common_modifiers(tokens[1:])
        subst = tokens[0]
        status_def = StatusDefinition(name, Subst.parse(subst + ";"), counter_type)
        return entity, SinglePointEffect(
            add_status=(status_def, counter), **common_modifiers
        )
    match = re.match(r"\[(.*): (.*)\]", modifier)
    if not match:
        raise ValueError("Invalid format")

    entity = match.group(1).strip()
    effects = match.group(2).split("|")

    if "end of turn" in effects:
        return entity, SinglePointEffect.noop_effect()

    delta_shield = 0
    delta_hp = 0

    for effect in effects:
        effect = effect.strip()
        if "shield" in effect:
            delta_shield = float(effect.split(" ")[1])
        elif "damaged" in effect or "healed" in effect:
            delta_hp = float(effect.split(" ")[1])
            if "damaged" in effect:
                delta_hp *= -1

    common_modifiers = parse_common_modifiers(effects)
    return entity, SinglePointEffect(
        delta_shield=delta_shield, delta_hp=delta_hp, **common_modifiers
    )


def parse_common_modifiers(tokens: list[str]) -> dict:
    modifiers = {
        "delay": 0,
        "critical_chance": 0.0,
        "pierce": False,
        "drain": False,
        "accuracy": 1.0,
    }

    for token in tokens:
        token = token.strip()
        if "crit" in token:
            modifiers["critical_chance"] = float(token.split(" ")[1])
        elif "acc" in token:
            modifiers["accuracy"] = float(token.split(" ")[1])
        elif "delay" in token:
            modifiers["delay"] = int(token.split(" ")[1])
        elif "pierce" in token:
            modifiers["pierce"] = True
        elif "drain" in token:
            modifiers["drain"] = True

    return modifiers


def parse_effect(bracket_expr: str) -> Effect:
    if re.match(r"^\[[\w\s,]*:", bracket_expr):
        return parse_targeted_effect(bracket_expr)
    return parse_global_effect(bracket_expr)
