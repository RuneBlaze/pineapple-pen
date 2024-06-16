from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias
from uuid import uuid4


@dataclass(eq=True, frozen=True)
class DamageEffect:
    delta_shield: int  # How are we changing the shield points
    delta_hp: int
    critical_chance: float = 0.0  # If critical, we multiply the effect by 2
    delay: int = 0  # How many turns to wait
    pierce: bool = False  # Do we ignore shield points
    drain: bool = False  # Do we heal from the damage
    accuracy: float = 1.0  # How likely are we to hit the target. if acc check failed, the effect is ignored

    _uuid: str = field(default_factory=lambda: uuid4().hex)


TargetedEffect: TypeAlias = tuple[str, DamageEffect]


class GlobalEffect:
    pass


@dataclass(eq=True, frozen=True)
class DrawCardsEffect(GlobalEffect):
    count: int
    delay: int = 0


@dataclass(eq=True, frozen=True)
class DiscardCardsEffect(GlobalEffect):
    count: int
    delay: int = 0


@dataclass(eq=True, frozen=True)
class CreateCardEffect(GlobalEffect):
    card: str
    delay: int = 0


def parse_global_effect(modifier: str) -> GlobalEffect:
    # Global effects are double-bracketed, e.g. `[[draw 2 | delay 1]]`
    import re

    match = re.match(r"\[\[(.*)\]\]", modifier)
    if not match:
        raise ValueError("Invalid format")
    effect = match.group(1).strip()

    tokens = effect.split("|")
    if "draw" in effect:
        count = int(tokens[0].split(" ")[1])
        delay = 0
        for token in tokens[1:]:
            if "delay" in token:
                delay = int(token.split(" ")[1])
        return DrawCardsEffect(count, delay)
    elif "discard" in effect:
        count = int(tokens[0].split(" ")[1])
        delay = 0
        for token in tokens[1:]:
            if "delay" in token:
                delay = int(token.split(" ")[1])
        return DiscardCardsEffect(count, delay)
    elif "create" in effect:
        card = tokens[0].split(" ")[1]
        delay = 0
        for token in tokens[1:]:
            if "delay" in token:
                delay = int(token.split(" ")[1])
        return CreateCardEffect(card, delay)
    else:
        raise ValueError("Invalid format")


def parse_targeted_effect(modifier: str) -> TargetedEffect:
    # Example input: `[entity: shield X | crit 0.5 | delay 1]`
    import re

    # Remove brackets and split the entity and effects
    match = re.match(r"\[(.*): (.*)\]", modifier)
    if not match:
        raise ValueError("Invalid format")

    entity = match.group(1).strip()
    effects = match.group(2).split("|")

    # Initialize default values
    delta_shield = 0
    delta_hp = 0
    critical_chance = 0.0
    delay = 0
    pierce = False
    accuracy = 1.0
    drain = False

    # Parse each effect
    for effect in effects:
        effect = effect.strip()
        if "shield" in effect:
            value = int(effect.split(" ")[1])
            delta_shield = value
        elif "damaged" in effect or "healed" in effect:
            delta_hp = int(effect.split(" ")[1])
            if "damaged" in effect:
                delta_hp *= -1
        elif "crit" in effect:
            critical_chance = float(effect.split(" ")[1])
        elif "acc" in effect:
            accuracy = float(effect.split(" ")[1])
        elif "delay" in effect:
            delay = int(effect.split(" ")[1])
        elif "pierce" in effect:
            pierce = True
        elif "drain" in effect:
            drain = True

    return entity, DamageEffect(
        delta_shield, delta_hp, critical_chance, delay, pierce, drain, accuracy
    )


def parse_effect(modifier: str) -> GlobalEffect | TargetedEffect:
    if modifier.startswith("[["):
        return parse_global_effect(modifier)
    else:
        return parse_targeted_effect(modifier)
