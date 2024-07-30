from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

import numpy as np
import pyxel
from pyxelxl import layout

from genio.components import (
    cute_text,
    dithering,
    draw_rounded_rectangle,
    retro_text,
)


@dataclass
class ColorScheme:
    primary: int
    secondary: int


COLOR_SCHEME_PRIMARY = ColorScheme(3, 11)
COLOR_SCHEME_SECONDARY = ColorScheme(4, 8)


Vec2: TypeAlias = np.ndarray


def vec2(x: int, y: int) -> Vec2:
    return np.array([x, y], dtype=int)


def is_mouse_in_rect(xy: Vec2, wh: Vec2) -> bool:
    return (
        xy[0] <= pyxel.mouse_x
        and pyxel.mouse_x < xy[0] + wh[0]
        and xy[1] <= pyxel.mouse_y
        and pyxel.mouse_y < xy[1] + wh[1]
    )


@dataclass
class ButtonElement:
    text: str
    color_scheme: ColorScheme
    position: Vec2
    secondary_text: str | None = None

    hovering: bool = False
    btnp: bool = False

    def draw_at(self) -> Vec2:
        xy = self.position
        button_width = 55
        c1, c2 = self.color_scheme.primary, self.color_scheme.secondary
        if self.hovering:
            draw_rounded_rectangle(*(xy + vec2(0, 1)), button_width, 16, 4, c1)
            draw_rounded_rectangle(*xy, button_width, 16, 4, c1)
            if not pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
                with dithering(0.5):
                    draw_rounded_rectangle(*xy, button_width, 16, 4, c2)
            self.draw_text_centered(xy, button_width)
        else:
            draw_rounded_rectangle(*(xy + vec2(0, 1)), button_width, 16, 4, c1)
            draw_rounded_rectangle(*xy, button_width, 16, 4, c2)
            self.draw_text_centered(xy, button_width)
        return vec2(button_width + 2, 16)

    def draw_text_centered(self, xy, button_width):
        if self.secondary_text == "":
            x_offset = (55 - 4 * len(self.text)) // 2
            pyxel.text(xy[0] + x_offset, xy[1] + 4, self.text, 7)
        elif self.secondary_text is None:
            cute_text(*xy, self.text, 7, layout=layout(w=button_width, ha="center"))
        else:
            x_offset = (55 - 3 * len(self.text)) // 2
            pyxel.text(xy[0] + x_offset, xy[1] + 2, self.text, 7)
            retro_text(
                xy[0],
                xy[1] + 7,
                self.secondary_text,
                7,
                layout=layout(w=button_width, ha="center"),
            )

    def update(self) -> None:
        xy = self.position
        if is_mouse_in_rect(xy, vec2(55, 16)):
            self.hovering = True
            if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                self.btnp = True
                return
        else:
            self.hovering = False
        self.btnp = False
