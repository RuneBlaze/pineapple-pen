from __future__ import annotations

import contextlib
from functools import cache
import math
import random
from operator import gt, lt
from typing import Literal

import numpy as np
import pyxel
from pyxelxl import Font, LayoutOpts, layout

from genio.base import asset_path
from genio.battle import CardBundle
from scipy.ndimage import gaussian_filter
from pyxelxl.font import _image_as_ndarray

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


@contextlib.contextmanager
def pal_single_color(col: int):
    for i in range(16):
        pyxel.pal(i, col)
    yield
    pyxel.pal()


def blt_with_mask(
    x: int,
    y: int,
    image: pyxel.Image,
    u: int,
    v: int,
    w: int,
    h: int,
    colkey: int,
    mask: np.ndarray,
) -> None:
    if w != mask.shape[1] or h != mask.shape[0]:
        raise ValueError("Mask size does not match image size")
    for j in range(h):
        for i in range(w):
            if mask[j, i]:
                src = image.pget(u + i, v + j)
                if src != colkey:
                    pyxel.pset(x + i, y + j, src)


def blt_burning(
    x: int,
    y: int,
    image: pyxel.Image,
    noise: np.ndarray,
    timer: int,
    in_or_out: Literal["in", "out"] = "in",
):
    cmp_op = gt if in_or_out == "out" else lt
    delta = 4 if in_or_out == "in" else -4
    with pal_single_color(7):
        blt_with_mask(
            x,
            y,
            image,
            0,
            0,
            image.width,
            image.height,
            254,
            cmp_op(noise, (timer + delta) / 30),
        )
    blt_with_mask(
        x,
        y,
        image,
        0,
        0,
        image.width,
        image.height,
        254,
        cmp_op(noise, timer / 30),
    )


class DrawDeck:
    def __init__(self, card_bundle: CardBundle):
        self.deck_background = pyxel.Image.from_image(asset_path("card-back.png"))
        self.card_bundle = card_bundle

    def draw(self, x: int, y: int) -> None:
        num_shadow = max(1, len(self.card_bundle.deck) // 5)
        if len(self.card_bundle.deck) == 1:
            num_shadow = 0
        with pal_single_color(13):
            for i in range(num_shadow):
                pyxel.blt(
                    x - i - 1, y + i + 1, self.deck_background, 0, 0, 43, 60, colkey=0
                )
        pyxel.blt(x, y, self.deck_background, 0, 0, 43, 60, colkey=0)
        self.draw_card_label(x, y)

    def draw_card_label(self, x: int, y: int):
        width = 43
        label_width = 22
        label_x = x + (width - label_width) // 2
        label_y = y - 3
        pyxel.rect(label_x, label_y, label_width, 7, 7)
        retro_text(
            label_x,
            label_y,
            str(len(self.card_bundle.deck)),
            0,
            layout=layout(w=label_width, ha="center", h=7, va="center"),
        )




@cache
def perlin_noise(width: int, height: int, scale: float, replica: int = 0) -> np.ndarray:
    res = np.zeros((height, width), dtype=np.float32)
    for j in range(height):
        for i in range(width):
            res[j, i] = pyxel.noise(i * scale, j * scale, replica)
    # normalize it
    res -= res.min()
    res /= res.max()
    res = np.clip(res, 0, 1)
    return res



@cache
def perlin_noise_with_horizontal_gradient(
    width: int, height: int, scale: float, replica: int = 0
) -> np.ndarray:
    res = np.zeros((height, width), dtype=np.float32)
    for j in range(height):
        for i in range(width):
            n1 = pyxel.noise(i * scale, j * scale * 1, replica)
            n2 = pyxel.noise(i * scale, j * scale * 1, replica + 17)
            n3 = pyxel.noise(0.1 * math.atan2(n1, n2), 0.1 * np.sqrt(n1 ** 2 + n2 ** 2) * scale, replica)
            res[j, i] = 0.5 * n3 + 2 * i / height - j / height
    res -= res.min()
    res /= res.max()
    res = gaussian_filter(res, sigma=20, radius=200)
    res = spherize(res)
    res = np.clip(res, 0, 1)
    return res

def spherize(a: np.ndarray) -> np.ndarray:
    h, w = a.shape
    center = np.array([h, w]) / 2
    res = np.zeros((h, w), dtype=np.float32)
    for j in range(h):
        for i in range(w):
            u, v = i - center[1], j - center[0]
            u, v = u / center[1], v / center[0]
            r = np.sqrt(u ** 2 + v ** 2)
            if r == 0:
                res[j, i] = 0
            else:
                theta = np.arctan2(v, u)
                x = r * np.cos(theta)
                y = r * np.sin(theta)
                x = (x + 1) / 2
                y = (y + 1) / 2
                x = int(x * w)
                y = int(y * h)
                if x >= w:
                    x = w - 1
                if y >= h:
                    y = h - 1
                res[j, i] = a[y, x]
    return res

def mask_screen(
    mask: np.ndarray,
    threshold: float,
    fill_color: int,
) -> None:
    if threshold >= 1.5:
        return
    threshold = threshold ** 0.8
    screen = np.full_like(_image_as_ndarray(pyxel.screen), 254, dtype=np.uint8)
    dither_matrix = np.zeros((pyxel.height, pyxel.width), dtype=bool)
    # only true when x + y is 3 mod 4
    dither_matrix[::4, 3::4] = True
    screen[(mask > threshold - 0.1) & dither_matrix] = fill_color
    dither_matrix[::2, ::2] = True
    screen[(mask > threshold - 0.05) & dither_matrix] = fill_color
    screen[(mask > threshold)] = fill_color
    new_image = pyxel.Image(*screen.shape[::-1])
    _image_as_ndarray(new_image)[:] = screen
    pyxel.blt(0, 0, new_image, 0, 0, new_image.width, new_image.height, 254)

def mask_screen_out(
    mask: np.ndarray,
    threshold: float,
    fill_color: int,
) -> None:
    if threshold >= 1.5:
        pyxel.cls(fill_color)
        return
    threshold = threshold ** 0.8
    screen = np.full_like(_image_as_ndarray(pyxel.screen), 254, dtype=np.uint8)
    dither_matrix = np.zeros((pyxel.height, pyxel.width), dtype=bool)
    dither_matrix[::4, 3::4] = True
    screen[(mask < threshold + 0.1) & dither_matrix] = fill_color
    dither_matrix[::2, ::2] = True
    screen[(mask < threshold + 0.05) & dither_matrix] = fill_color
    screen[(mask < threshold)] = fill_color
    new_image = pyxel.Image(*screen.shape[::-1])
    _image_as_ndarray(new_image)[:] = screen
    pyxel.blt(0, 0, new_image, 0, 0, new_image.width, new_image.height, 254)