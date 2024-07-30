from __future__ import annotations

from dataclasses import dataclass, field

from genio.battle import BattleBundle, EnemyProfile, setup_battle_bundle


@dataclass
class World:
    name: str = "Mystic Wilds"


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
        self.battle_bundle.battle_logs = [
            "Turn 0: Celine, the Magical Swordswoman gained shield 1.0",
            "Turn 0: Celine, the Magical Swordswoman gained shield 1.0",
            "Turn 1: Celine, the Magical Swordswoman received damage 2.0",
            "Turn 1: Celine, the Magical Swordswoman received damage 2.0",
            "Turn 1: Evil Mask A received damage 2.0",
            "Turn 1: Evil Mask B received other effect...",
            "Turn 1: Evil Mask A received damage 2.0",
            "Battle Ended, Celine returned to World 1: Mystic Wilds",
        ]
        self.world = World()

    def gain_gold(self, amount: float) -> None:
        self.gold += amount

    def lose_gold(self, amount: float) -> None:
        self.gold -= amount
        self.gold = max(0, self.gold)


game_state = GameState()
"""Singleton instance of the game state."""
