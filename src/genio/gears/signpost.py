import itertools
from typing import Literal

import pytweening
from pyxelxl import layout

from genio.components import CanAddAnim, capital_hill_text, dithering, willow_branch
from genio.gears.stroke import StrokeAnim
from genio.tween import Mutator, Tweener


class SignPost:
    strokes: list[StrokeAnim]

    def __init__(
        self,
        x: int,
        y: int,
        text: str,
        scene: CanAddAnim,
        font: Literal["capital", "willow"] = "capital",
    ) -> None:
        self.strokes = []
        self.tweener = Tweener()
        self.scene = scene
        self.text = text
        self.x = x - 15
        self.y = y
        self.timer = 0
        self.opacity = 0.0
        self.font = font

        t = 20

        if font == "willow":
            t = 60

        self.tweener.append(
            itertools.zip_longest(
                Mutator(
                    t,
                    pytweening.easeInQuad,
                    self,
                    "opacity",
                    1.0,
                ),
                Mutator(
                    t,
                    pytweening.easeInQuad,
                    self,
                    "x",
                    x,
                ),
            )
        )

        wait_time = 30
        if font == "willow":
            wait_time = 90

        self.tweener.append(
            range(wait_time),
        )

        self.tweener.append(
            itertools.zip_longest(
                Mutator(
                    t,
                    pytweening.easeOutQuad,
                    self,
                    "opacity",
                    0.0,
                ),
                Mutator(
                    t,
                    pytweening.easeOutQuad,
                    self,
                    "x",
                    x + 15,
                ),
            )
        )
        if font == "willow":
            self.strokes.append(
                StrokeAnim(
                    x - 50,
                    y + 8,
                    150,
                    scene,
                )
            )
        else:
            self.strokes.append(
                StrokeAnim(
                    x - 50,
                    y + 4,
                    100,
                    scene,
                )
            )

    def draw(self) -> None:
        with dithering(self.opacity):
            font_func = willow_branch if self.font == "willow" else capital_hill_text
            if self.font == "willow":
                font_func(
                    self.x - 50, self.y, self.text, 7, layout=layout(w=200, ha="center")
                )
            else:
                font_func(
                    self.x - 50, self.y, self.text, 7, layout=layout(w=100, ha="center")
                )

    def update(self) -> None:
        self.tweener.update()
        self.timer += 1
        for stroke in self.strokes:
            stroke.update()

    def is_dead(self) -> bool:
        return self.timer >= 180
