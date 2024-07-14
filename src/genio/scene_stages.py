from __future__ import annotations

import contextlib
import itertools
import textwrap
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum

import pytweening
import pyxel
from pyxelxl import layout

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, load_image
from genio.components import (
    arcade_text,
    retro_text,
)
from genio.layout import pingpong
from genio.ps import Anim
from genio.scene import Scene
from genio.tween import Mutator, Tweener


def draw_tiled(img: pyxel.Image) -> None:
    w, h = img.width, img.height
    for x, y in itertools.product(
        range(0, WINDOW_WIDTH, w), range(0, WINDOW_HEIGHT, h)
    ):
        pyxel.blt(x, y, img, 0, 0, w, h, 0)


class Camera:
    def __init__(self, follow: MapMarker | None = None) -> None:
        self.tweener = Tweener()
        self.x = 0
        self.y = 0
        self.follow = follow
        self.memory_y = None
        self.memory_x = None

    def update(self):
        self.tweener.update()
        if self.follow is None:
            return
        target_x = self.follow.x - WINDOW_WIDTH // 2
        target_y = self.follow.y - WINDOW_HEIGHT // 2
        if self.x == target_x and self.y == target_y:
            return
        if self.memory_y != target_y or self.memory_x != target_x:
            self.memory_y = target_y
            self.memory_x = target_x
            self.tweener.append(
                itertools.zip_longest(
                    Mutator(50, pytweening.easeInBounce, self, "y", target_y),
                    Mutator(50, pytweening.easeInBounce, self, "x", target_x),
                )
            )

        self.tweener.keep_at_most(3)

    @contextlib.contextmanager
    def focus(self):
        pyxel.camera(self.x, self.y)
        yield
        pyxel.camera(0, 0)


@dataclass
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


def draw_rounded_rectangle(x: int, y: int, w: int, h: int, r: int, col: int) -> None:
    pyxel.rect(x + r, y, w - 2 * r + 1, h + 1, col)
    pyxel.rect(x, y + r, r, h - 2 * r, col)
    pyxel.rect(x + w - r + 1, y + r, r, h - 2 * r, col)
    pyxel.circ(x + r, y + r, r, col)
    pyxel.circ(x + w - r, y + r, r, col)
    pyxel.circ(x + r, y + h - r, r, col)
    pyxel.circ(x + w - r, y + h - r, r, col)


class MapMarkerState(Enum):
    IDLE = 0
    SELECTED = 1
    INACTIVE = 2


class MapMarker:
    def __init__(self, x: int, y: int, camera: Camera) -> None:
        self.x = x
        self.y = y
        self.state = MapMarkerState.IDLE
        self.camera = camera

        self.timer = 0
        self.pingpong = pingpong(3)
        self.t = next(self.pingpong)

        self.hovering = False

    def draw(self) -> None:
        if self.hovering:
            return
        c1 = 15
        pyxel.dither(0.5 + ((self.timer // 10) % 3) / 3)
        pyxel.tri(self.x, self.y, self.x + 6, self.y, self.x + 3, self.y - 3, c1)
        pyxel.tri(self.x, self.y, self.x + 6, self.y, self.x + 3, self.y + 3, c1)

        pyxel.dither(1.0)
        self.draw_border(c1, self.t)
        pyxel.dither(1.0)

    def draw_border(self, c1: int, t: int) -> None:
        pyxel.line(self.x - 2 - t, self.y, self.x + 3, self.y - 5 - t, c1)
        pyxel.line(self.x + 3, self.y - 5 - t, self.x + 8 + t, self.y, c1)
        pyxel.line(self.x - 2 - t, self.y, self.x + 3, self.y + 5 + t, c1)
        pyxel.line(self.x + 3, self.y + 5 + t, self.x + 8 + t, self.y, c1)

    def update(self) -> None:
        self.timer += 1

        if self.timer % 10 == 0:
            self.t = next(self.pingpong)

        screen_x = self.x - self.camera.x
        screen_y = self.y - self.camera.y

        if (
            screen_x - 6 < pyxel.mouse_x < screen_x + 6
            and screen_y - 6 < pyxel.mouse_y < screen_y + 6
        ):
            if not self.hovering:
                self.hovering = True
        else:
            self.hovering = False

        if self.hovering and pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.camera.follow = self


def draw_lush_background() -> None:
    pyxel.cls(0)
    pyxel.clip(0 + 30, 0 + 30, WINDOW_WIDTH - 60, WINDOW_HEIGHT - 60)
    draw_tiled(load_image("tiles-black.png"))
    pyxel.dither(0.5)
    pyxel.blt(100, 60, img := load_image("flowers.png"), 0, 0, 427, 240, 254)
    pyxel.clip(100 + 10, 60 + 10, 427, 240)
    pyxel.dither(1)
    pyxel.blt(100, 60, img, 0, 0, img.width - 10, img.height - 10, 254)
    pyxel.clip()
    pyxel.dither(0.5)
    pyxel.dither(1.0)


class StageSelectScene(Scene):
    def __init__(self) -> None:
        super().__init__()
        self.executor = ThreadPoolExecutor(2)
        self.camera = cam = Camera()

        self.map_markers = [
            MapMarker(100, 50, cam),
            MapMarker(0, 100, cam),
            MapMarker(150, 150, cam),
        ]
        self.camera.follow = self.map_markers[0]

    def update(self) -> None:
        for marker in self.map_markers:
            marker.update()
        self.camera.update()

    def draw(self) -> None:
        pyxel.cls(0)
        with self.camera.focus():
            draw_lush_background()

            for marker in self.map_markers:
                marker.draw()

        self.draw_stage_description()

        Anim.draw()
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def draw_stage_description(self):
        description = StageDescription.default()
        w = 100
        x = 270
        y = 40
        pyxel.dither(0.5)
        draw_rounded_rectangle(x, y, w, 100, 2, 0)
        pyxel.dither(1.0)
        c1 = 7
        arcade_text(x, y + 5, "1-2", c1, layout=layout(w=w, ha="center"))
        retro_text(x, y + 20, "Beneath the Soil", c1, layout=layout(w=w, ha="center"))

        for i, l in enumerate(textwrap.wrap(description.lore, 32)):
            pyxel.text(x, y + 80 + i * 7, l, 7)

    def draw_crosshair(self, x, y):
        pyxel.line(x - 5, y, x + 5, y, 7)
        pyxel.line(x, y - 5, x, y + 5, 7)


def gen_scene() -> Scene:
    return StageSelectScene()
