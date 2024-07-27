import itertools
import math
from collections import deque
from dataclasses import dataclass, field
from functools import cache
from threading import Lock

import pytweening
import pyxel
from atomicx import AtomicInt
from pyxelxl import blt_rot

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, load_image
from genio.components import CanAddAnim, dithering
from genio.gears.paperlike import paper_cut_effect
from genio.gears.stroke import StrokeAnim
from genio.tween import Instant, Mutator, Tweener


@cache
def icon_image() -> pyxel.Image:
    return paper_cut_effect(load_image("gemini_icon.png"), bg_color=254, fill_color=7)


class WavingText:
    def __init__(self, text: str) -> None:
        self.opacity = 0.0
        self.timer = 0
        self.text = text

    def y_offset_for_ix(self, i: int) -> float:
        return math.sin(self.timer * 0.1 + i * 1.2) * 1

    def draw(self, x: int, y: int) -> None:
        for i, char in enumerate(self.text):
            with dithering(self.opacity):
                pyxel.text(x + i * 4, y + self.y_offset_for_ix(i), char, 7)

    def update(self) -> None:
        self.timer += 1


@dataclass
class IndividualAnimation:
    x: int
    y: int
    opacity: float = 0  # 0-1

    timer: int = 0
    tweener: Tweener = field(default_factory=Tweener)
    tweener2: Tweener = field(default_factory=Tweener)
    dead: bool = False
    rotation: float = 0.0

    def update(self) -> None:
        self.timer += 1
        self.tweener.update()
        self.tweener2.update()

    def mark_dead(self) -> None:
        self.dead = True

    def draw(self) -> None:
        with dithering(self.opacity):
            blt_rot(
                self.x - 8,
                self.y - 8,
                icon_image(),
                0,
                0,
                16,
                16,
                colkey=254,
                rot=self.rotation,
            )

    def on_start(self) -> None:
        self.tweener.append_mutate(self, "opacity", 10, 1.0, "ease_in_quad")
        for i in range(1000):
            wait_frame = 30 if i % 2 == 0 else 20
            self.tweener2.append_mutate(
                self, "rotation", wait_frame, 180 * (i + 1) + 0.1, "ease_in_out_quad"
            )
            self.tweener2.append(range(wait_frame // 3))

    def on_end(self) -> None:
        self.tweener.append_mutate(self, "opacity", 10, 0.0, "ease_out_quad")
        self.tweener.append(Instant(self.mark_dead))


DEFAULT_ASYNC_TEXT = "Gemini Flashing"


class AsyncVisualizer:
    def __init__(self, scene: CanAddAnim, text: str = DEFAULT_ASYNC_TEXT) -> None:
        self.tweener = Tweener(variable_play_speed=True)
        self.tweener2 = Tweener(variable_play_speed=False)
        self.animations = deque()
        self.target_number = AtomicInt(0)
        self.phasing_out_animations = []
        self.text = text
        self.waver = WavingText(self.text)
        self.strokes = []
        self.scene = scene
        self.lock = Lock()
        icon_image()

    def ping(self) -> None:
        next_count = self.target_number.load() + 1
        x, y = self.calculate_position(len(self.animations), next_count)
        with self.lock:
            self.animations.appendleft(anim := IndividualAnimation(x, y))
        anim.on_start()
        old_number = self.target_number.inc()
        if old_number == 0:
            self.tweener2.append_mutate(self.waver, "opacity", 10, 1.0, "ease_in_quad")
            stroke_x, stroke_y = (
                WINDOW_WIDTH - len(self.text) * 4 - 10,
                WINDOW_HEIGHT - 15,
            )
            stroke_width = len(self.text) * 4
            self.strokes.append(
                StrokeAnim(
                    stroke_x,
                    stroke_y,
                    stroke_width,
                    self.scene,
                )
            )
        self.refresh_animation_positions()

    def draw(self) -> None:
        with self.lock:
            for anim in self.animations:
                anim.draw()
        for anim in self.phasing_out_animations:
            anim.draw()
        self.waver.draw(WINDOW_WIDTH - len(self.text) * 4 - 10, WINDOW_HEIGHT - 15)

    def refresh_animation_positions(self):
        tweens = []
        for i, anim in enumerate(self.animations):
            x, y = self.calculate_position(i, len(self.animations))
            tweens.append(Mutator(10, pytweening.easeInOutQuad, anim, "x", x))
            tweens.append(Mutator(10, pytweening.easeInOutQuad, anim, "y", y))
        simutaneous_tween = itertools.zip_longest(*tweens)
        self.tweener.append(simutaneous_tween)

    def pong(self) -> None:
        if self.target_number.load() == 0:
            return
        with self.lock:
            first_anim = self.animations.popleft()
        first_anim.on_end()
        self.phasing_out_animations.append(first_anim)
        old_number = self.target_number.dec()
        if old_number == 1:
            self.tweener2.append_mutate(self.waver, "opacity", 10, 0.0, "ease_out_quad")
        self.refresh_animation_positions()

    def update(self) -> None:
        with self.lock:
            for anim in self.animations:
                anim.update()
        for anim in self.phasing_out_animations:
            anim.update()
        self.phasing_out_animations = [
            anim for anim in self.phasing_out_animations if not anim.dead
        ]
        self.waver.update()
        self.tweener.update()
        self.tweener2.update()
        for stroke in self.strokes:
            stroke.update()

    def calculate_position(self, i: int, total_number: int) -> tuple[int, int]:
        each_width = 16
        x = WINDOW_WIDTH - each_width * (i + 1)
        y = WINDOW_HEIGHT - 24
        return x, y
