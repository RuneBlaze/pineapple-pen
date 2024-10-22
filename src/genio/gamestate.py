from __future__ import annotations

from dataclasses import dataclass, field

from genio.battle import BattleBundle, EnemyProfile, setup_battle_bundle


@dataclass
class World:
    name: str = "Mystic Wilds"


@dataclass
class GameConfig:
    larger_font: bool = False
    music_volume: int = 3
    sfx_volume: int = 3

    def reset(self) -> None:
        self.larger_font = False
        self.music_volume = 3
        self.sfx_volume = 3


@dataclass(frozen=True, eq=True)
class StageDescription:
    name: str
    subtitle: str
    lore: str
    danger_level: int
    enemies: list[EnemyProfile] = field(default_factory=list)

    @staticmethod
    def default() -> StageDescription:
        return StageDescription(
            "1-1",
            "Beneath the Soil",
            "Beneath the sturdy bamboo, even sturdier roots spread out. Only foolish humans and youkai can see nothing but the surface.",
            1,
        )

    def generate_base_money(self) -> int:
        return 10 + 5 * self.danger_level


class GameState:
    battle_bundle: BattleBundle
    gold: float

    def __init__(self) -> None:
        self.stage = StageDescription.default()
        self.battle_bundle = setup_battle_bundle(
            "initial_deck", "players.starter", ["enemies.evil_mask"] * 2
        )
        self.gold = 10
        self.battle_bundle.battle_logs = []
        self.world = World()
        self.config = GameConfig()

    def gain_gold(self, amount: float) -> None:
        self.gold += amount

    def lose_gold(self, amount: float) -> None:
        self.gold -= amount
        self.gold = max(0, self.gold)

    def should_use_large_font(self) -> bool:
        return self.config.larger_font


game_state = GameState()
"""Singleton instance of the game state."""
