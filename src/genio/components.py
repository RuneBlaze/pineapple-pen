from __future__ import annotations

import random

import pyxel
from pyxelxl import Font, LayoutOpts, layout

from genio.base import asset_path

retro_font = Font(asset_path("retro-pixel-petty-5h.ttf"))
retro_text = retro_font.specialize(font_size=5)
display_text = Font(asset_path("DMSerifDisplay-Regular.ttf")).specialize(
    font_size=18, threshold=100
)
cute_text = Font(asset_path("retro-pixel-cute-prop.ttf")).specialize(font_size=11)


def shadowed_text(
    x, y, text, color, layout_opts: LayoutOpts | None = None, dither_mult: float = 1.0
):
    pyxel.dither(0.5 * dither_mult)
    retro_text(x + 1, y + 1, text, 0, layout=layout_opts)
    pyxel.dither(1.0 * dither_mult)
    retro_text(x, y, text, color, layout=layout_opts)
    pyxel.dither(1.0)


class Popup:
    def __init__(self, text: str, x: int, y: int, color: int):
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.counter = 60
        self.dx = random.randint(-10, 10)
        self.dy = random.randint(-65, -55)

    def draw(self):
        if self.counter <= 0:
            return
        t = 1 - self.counter / 60
        t = t**0.8
        if self.counter >= 45:
            if self.counter % 10 <= 5:
                pyxel.pal(self.color, 10)
        shadowed_text(
            self.x + self.dx * t - 15,
            self.y + self.dy * t,
            self.text,
            self.color,
            layout_opts=layout(w=30, h=20, ha="center", va="center"),
            dither_mult=(1 - t) if self.counter <= 30 else 1.0,
        )
        pyxel.pal()

    def update(self):
        self.counter -= 1


def gauge(x, y, w, h, c0, c1, value, max_value, label=None):
    pyxel.rect(x, y, w, h, c0)
    pyxel.rect(x, y, min(w * value // max_value, w), h, c1)
    pyxel.dither(0.5)
    pyxel.rectb(x, y, w, h, 0)
    pyxel.dither(1.0)
    text = f"{value}/{max_value}"
    if label:
        text = f"{label} {text}"
    shadowed_text(x + 2, y + 2, text, 7, layout_opts=layout(w=w, ha="left"))
