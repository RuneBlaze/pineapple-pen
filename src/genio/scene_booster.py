import itertools
import math
from collections import defaultdict
from enum import Enum
from functools import cache
from operator import sub, gt, lt
from typing import Literal

import numpy as np
import pytweening
import pyxel
from pyxelxl import blt_rot

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, load_image
from genio.battle import setup_battle_bundle
from genio.card import Card
from genio.constants import CARD_HEIGHT, CARD_WIDTH
from genio.gui import (
    CardSprite,
    CardState,
    ResolvingFraming,
    camera_shift,
    pal_single_color,
)
from genio.layout import layout_center_for_n
from genio.ps import Anim, HasPos
from genio.scene import Scene
from genio.tween import Instant, Mutator, Tweener


class BoosterPackType(Enum):
    SPY_THEMED = 0
    STANDARDIZED_TEST_THEMED = 1


class BoosterPackState(Enum):
    CLOSED = 0
    OPENING = 1
    OPENED = 2


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


def blt_burning(x: int, y: int, image: pyxel.Image, noise: np.ndarray, timer: int, in_or_out: Literal["in", "out"] = "in"):
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


class BoosterPack:
    def __init__(self, x: int, y: int, pack_type: BoosterPackType) -> None:
        self.x = x
        self.y = y
        self.pack_type = pack_type
        self.image = load_image("ui", "card-spy.png")
        self.tweener = Tweener()
        self.state = BoosterPackState.CLOSED
        self.angle = 0
        self.hovering = False
        self.noise = perlin_noise(self.image.width, self.image.height, 0.1)
        self.events = []
        self.timer = 0
        self.state_timers = defaultdict(int)

    def draw(self):
        match self.state:
            case BoosterPackState.CLOSED:
                blt_rot(
                    self.x,
                    self.y,
                    self.image,
                    0,
                    0,
                    self.image.width,
                    self.image.height,
                    colkey=254,
                    rot=self.angle,
                )
            case BoosterPackState.OPENING:
                blt_rot(
                    self.x,
                    self.y,
                    self.image,
                    0,
                    0,
                    self.image.width,
                    self.image.height,
                    colkey=254,
                    rot=self.angle,
                )
            case BoosterPackState.OPENED:
                blt_burning(self.x, self.y, self.image, self.noise, self.timer, "out")

    def update(self):
        self.tweener.update()
        self.timer += 1
        self.state_timers[self.state] += 1

        if self.state == BoosterPackState.CLOSED:
            mx, my = pyxel.mouse_x, pyxel.mouse_y
            if (
                self.x < mx < self.x + self.image.width
                and self.y < my < self.y + self.image.height
            ):
                if not self.hovering:
                    self.tweener.append(
                        Mutator(5, pytweening.easeInOutBounce, self, "angle", 5)
                    )
                    self.tweener.append(
                        Mutator(5, pytweening.easeInOutBounce, self, "angle", -5)
                    )
                    self.tweener.append(
                        Mutator(5, pytweening.easeInOutBounce, self, "angle", 0)
                    )
                self.hovering = True
            else:
                if self.hovering:
                    self.tweener.append(Mutator(5, pytweening.easeInCirc, self, "angle", 0))
                self.hovering = False

        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and self.state == BoosterPackState.CLOSED:
            self.state = BoosterPackState.OPENING
            tx, ty = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
            tx, ty = tx - self.image.width // 2, ty - self.image.height // 2
            self.tweener.append(
                itertools.zip_longest(
                    Mutator(30, pytweening.easeInCirc, self, "x", tx),
                    Mutator(30, pytweening.easeInCirc, self, "y", ty),
                    itertools.chain(
                        range(30),
                        Instant(self.on_explode),
                    ),
                )
            )

            self.events.append("open_pack")

    def on_explode(self) -> None:
        self.events.append("explode")

    def generate_cards(self) -> list[Card]:
        return [Card("OK", "good") for i in range(5)]


class BoosterPackScene(Scene):
    card_sprites: list[CardSprite]

    def __init__(self) -> None:
        super().__init__()

        self.framing = ResolvingFraming(self)

        self.booster_packs = []
        self.booster_packs.append(BoosterPack(10, 10, BoosterPackType.SPY_THEMED))

        self.card_sprites = []
        self.bundle = setup_battle_bundle(
            "initial_deck", "players.starter", ["enemies.evil_mask"] * 2
        )
        self.timer = 0

    def update(self):
        self.framing.update()
        for spr in self.card_sprites:
            spr.update()
        for pack in self.booster_packs:
            pack.update()
            while pack.events:
                event = pack.events.pop()
                if event == "open_pack":
                    self.framing.putup()
                elif event == "explode":
                    cards = pack.generate_cards()
                    self.show_cards(cards)
        self.timer += 1

    def draw(self):
        pyxel.cls(9)
        for pack in self.booster_packs:
            pack.draw()
        for i, spr in enumerate(self.card_sprites):
            shift = math.sin((self.timer + 103 * i) / 10) * 3
            with camera_shift(0, shift):
                spr.draw()
        self.framing.draw()
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def show_cards(self, cards: list[Card]) -> None:
        for i, card in enumerate(cards):
            target_x = layout_center_for_n(len(cards), 400)[i] - CARD_WIDTH // 2
            target_y = WINDOW_HEIGHT // 2 - CARD_HEIGHT // 2
            spr = CardSprite(i, card, self, False)
            self.card_sprites.append(spr)
            spr.x = target_x
            spr.y = target_y
            spr.tweens.clear()
            spr.state = CardState.RESOLVING

    def draw_crosshair(self, x, y):
        pyxel.line(x - 5, y, x + 5, y, 7)
        pyxel.line(x, y - 5, x, y + 5, 7)

    def add_anim(
        self,
        name: str,
        x: int,
        y: int,
        play_speed: float = 1.0,
        attached_to: HasPos | None = None,
    ) -> Anim:
        ...


def gen_scene() -> Scene:
    return BoosterPackScene()
