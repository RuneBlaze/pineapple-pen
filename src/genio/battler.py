from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
from boltons.queueutils import HeapPriorityQueue

from genio.core.base import access, slurp_toml
from genio.effect import DamageEffect, parse_targeted_effect

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


class BattleBundle:
    def __init__(
        self,
        player: PlayerBattler,
        enemies: list[EnemyBattler],
        battle_prelude: BattlePrelude,
    ) -> None:
        self.player = player
        self.enemies = enemies
        self.turn_counter = 0
        self.effects = HeapPriorityQueue(priority_key=lambda x: -x)
        self.battle_prelude = battle_prelude

    def battlers(self) -> Iterator[BattlerLike]:
        yield self.player
        yield from self.enemies

    def search(self, name: str) -> BattlerLike:
        for battler in self.battlers():
            if name.lower() in battler.name.lower():
                return battler
        raise ValueError(f"No battler found with name '{name}'")

    def resolve_result(self, result: str) -> None:
        pattern = r"(\[.*?\])"
        substrings = re.findall(pattern, result)
        for substring in substrings:
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

    def apply_effect(
        self,
        caster: Battler | None,
        target: Battler,
        effect: DamageEffect,
        rng: np.random.Generator,
    ) -> None:
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
