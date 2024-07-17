from dataclasses import dataclass
from typing import TypeAlias

import numpy as np
import pyxel

Point: TypeAlias = np.ndarray


@dataclass
class QuadBezier:
    p0: Point
    c: Point
    p1: Point

    def evaluate(self, t: float) -> Point:
        u = 1 - t
        return u**2 * self.p0 + 2 * t * u * self.c + t**2 * self.p1

    def rasterize(
        self, num_segements: int = 7, t0: float = 0, t1: float = 1
    ) -> list[Point]:
        return [self.evaluate(t) for t in np.linspace(t0, t1, num_segements)]

    def draw(self, t0: float = 0, t1: float = 1, col: int = 7) -> None:
        points = self.rasterize(t0=t0, t1=t1)
        for i in range(len(points) - 1):
            p0, p1 = points[i], points[i + 1]
            pyxel.line(*p0, *p1, col)
