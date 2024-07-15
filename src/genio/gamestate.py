from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, eq=True)
class StageDescription:
    name: str
    subtitle: str
    lore: str
    danger_level: int

    @staticmethod
    def default() -> StageDescription:
        return StageDescription(
            "1-2",
            "Beneath the Soil",
            "Beneath the sturdy bamboo, even sturdier roots spread out. Only foolish humans and youkai can see nothing but the surface.",
            3,
        )

class GameState:
    def __init__(self) -> None:
        self.stage = StageDescription.default()

game_state = GameState()