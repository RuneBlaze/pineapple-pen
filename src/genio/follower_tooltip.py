import textwrap
from dataclasses import dataclass

from genio.components import (
    HasPos,
    dithering,
    draw_mixed_rounded_rect_left_aligned,
    retro_text,
)
from genio.gears.text_layout import pyxel_text


@dataclass(eq=True, frozen=True)
class FollowerTooltipInner:
    title: str
    description: str


@dataclass
class FollowerTooltip:
    energy: float
    inner: FollowerTooltipInner | None

    def __init__(self, following: HasPos):
        self.energy = 0.0
        self.inner = None
        self.following = following

    def draw(self) -> None:
        bx, by = self.following.screen_pos()
        bx += 8
        by += 8

        if self.inner:
            wrapped_description = textwrap.wrap(self.inner.description, width=25)
            num_lines = len(wrapped_description)
            draw_mixed_rounded_rect_left_aligned(
                self.dither_amount(), bx, by, w=110, h=10 + num_lines * 9
            )
            with dithering(self.dither_amount()):
                retro_text(bx + 3, by + 2, self.inner.title, 7)
                for i, line in enumerate(wrapped_description):
                    pyxel_text(bx + 3, by + 11 + i * 9, line, 7)

    def dither_amount(self) -> float:
        return min(1.0, self.energy)

    def update(self) -> None:
        self.energy -= 0.1
        self.energy = max(self.energy, 0.0)

    def pump(self, inner: FollowerTooltipInner) -> None:
        self.inner = inner
        self.energy += 0.2
        self.energy = min(self.energy, 1.2)

    def pump2(self, title: str, description: str) -> None:
        self.pump(FollowerTooltipInner(title, description))
