import itertools

import pytweening
from pyxelxl import layout

from genio.components import CanAddAnim, capital_hill_text, dithering
from genio.gears.stroke import StrokeAnim
from genio.tween import Mutator, Tweener


class SignPost:
    strokes: list[StrokeAnim]

    def __init__(self, x: int, y: int, text: str, scene: CanAddAnim) -> None:
        self.strokes = []
        self.tweener = Tweener()
        self.scene = scene
        self.text = text
        self.x = x - 15
        self.y = y
        self.timer = 0
        self.opacity = 0.0

        self.tweener.append(
            itertools.zip_longest(
                Mutator(
                    20,
                    pytweening.easeInQuad,
                    self,
                    "opacity",
                    1.0,
                ),
                Mutator(
                    20,
                    pytweening.easeInQuad,
                    self,
                    "x",
                    x,
                ),
            )
        )

        self.tweener.append(
            range(30),
        )

        self.tweener.append(
            itertools.zip_longest(
                Mutator(
                    20,
                    pytweening.easeOutQuad,
                    self,
                    "opacity",
                    0.0,
                ),
                Mutator(
                    20,
                    pytweening.easeOutQuad,
                    self,
                    "x",
                    x + 15,
                ),
            )
        )

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
            capital_hill_text(
                self.x - 50, self.y, self.text, 7, layout=layout(w=100, ha="center")
            )

    def update(self) -> None:
        self.tweener.update()
        self.timer += 1
        for stroke in self.strokes:
            stroke.update()

    def is_dead(self) -> bool:
        return self.timer >= 180
