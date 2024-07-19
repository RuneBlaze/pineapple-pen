from __future__ import annotations

from collections import Counter
from enum import Enum

import numpy as np
import pyxel

from genio.bezier import QuadBezier
from genio.card_utils import CanAddAnim
from genio.gamestate import StageDescription
from genio.layout import pingpong
from genio.ps import Anim, HasPos
from genio.scene import Scene
from genio.scene_booster import draw_rounded_rectangle
from genio.scene_stages import Camera
from genio.tween import Tweener
from genio.vector import Vec2Int, vec2


class MapMarkerState(Enum):
    IDLE = 0
    SELECTED = 1
    INACTIVE = 2
    APPEARING = 3


class MapMarker:
    def __init__(
        self,
        x: int,
        y: int,
        camera: Camera,
        stage_description: StageDescription,
        scene: CanAddAnim,
        appearing: bool = False,
    ) -> None:
        self.x = x
        self.y = y
        self.state = MapMarkerState.IDLE
        self.camera = camera
        self.stage_description = stage_description

        self.timer = 0
        self.pingpong = pingpong(3)
        self.t = next(self.pingpong)

        self.state_timers = Counter()
        self.hovering = False
        self.scene = scene
        if appearing:
            self.scene.add_anim("anims.map_marker_appear", x, y)
            self.state = MapMarkerState.APPEARING

    def draw(self) -> None:
        if self.state == MapMarkerState.APPEARING:
            return

        c1 = 15
        pyxel.dither(0.5 + ((self.timer // 10) % 3) / 3)
        pyxel.tri(self.x, self.y, self.x + 6, self.y, self.x + 3, self.y - 3, c1)
        pyxel.tri(self.x, self.y, self.x + 6, self.y, self.x + 3, self.y + 3, c1)

        pyxel.dither(1.0)
        self.draw_border(c1, self.t)
        pyxel.dither(1.0)

        if self.state == MapMarkerState.SELECTED:
            t = self.state_timers[MapMarkerState.SELECTED]
            # a vertical line first
            pyxel.line(self.x + 4, self.y, self.x + 4, self.y + 6, c1)
            l = 8
            pyxel.line(self.x + 4, self.y + l, self.x + 4 + 10, self.y + l, c1)
            draw_rounded_rectangle(self.x + 3 + 10, self.y + l - 4, 22, 8, 2, c1)
            pyxel.text(self.x + 3 + 15, self.y + l - 2, self.stage_description.name, 0)

    def draw_border(self, c1: int, t: int) -> None:
        pyxel.line(self.x - 2 - t, self.y, self.x + 3, self.y - 5 - t, c1)
        pyxel.line(self.x + 3, self.y - 5 - t, self.x + 8 + t, self.y, c1)
        pyxel.line(self.x - 2 - t, self.y, self.x + 3, self.y + 5 + t, c1)
        pyxel.line(self.x + 3, self.y + 5 + t, self.x + 8 + t, self.y, c1)

    def set_state(self, state: MapMarkerState) -> None:
        self.state = state
        self.state_timers[state] = 0

    def update(self) -> None:
        self.timer += 1
        self.state_timers[self.state] += 1

        if (
            self.state == MapMarkerState.APPEARING
            and self.state_timers[self.state] > 10
        ):
            self.set_state(MapMarkerState.IDLE)

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
            self.set_state(MapMarkerState.SELECTED)


class BezierAnimation:
    def __init__(
        self, p0: Vec2Int, p1: Vec2Int, sign: bool = True, col: int = 7
    ) -> None:
        midpoint = (p0 + p1) / 2
        dir = (p1 - midpoint) / np.linalg.norm(p1 - midpoint)
        dir = np.array([-dir[1], dir[0]])
        mult = 1 if sign else -1
        c = midpoint + np.linalg.norm(p1 - p0) * mult * 0.3 * dir
        self.curve = QuadBezier(p0, c, p1)
        self.tween = Tweener()
        self.t0 = 0.0
        self.t1 = 0.0
        self.col = col

    def play(self) -> None:
        self.tween.append_mutate(
            self,
            "t1",
            30,
            1.0,
            "ease_in_quad",
        )
        self.tween.append_mutate(
            self,
            "t0",
            30,
            1.0,
            "ease_in_quad",
        )

    def draw(self) -> None:
        self.curve.draw(t0=self.t0, t1=self.t1, col=self.col)

    def update(self) -> None:
        self.tween.update()


class ScenePlayground(Scene):
    anims: list[Anim]

    def __init__(self) -> None:
        self.bezier = BezierAnimation(
            vec2(0, 0),
            vec2(100, 100),
            col=15,
        )
        self.anims = []
        self.map_marker = MapMarker(
            100, 100, Camera(), StageDescription.default(), self, True
        )
        self.bezier.play()

    def update(self):
        self.bezier.update()
        self.map_marker.update()
        for anim in self.anims:
            anim.update()
        self.anims = [anim for anim in self.anims if not anim.dead]

    def draw(self):
        pyxel.cls(0)
        self.bezier.draw()
        self.map_marker.draw()
        Anim.draw()

    def add_anim(
        self,
        name: str,
        x: int,
        y: int,
        play_speed: float = 1.0,
        attached_to: HasPos | None = None,
    ) -> Anim:
        self.anims.append(
            result := Anim.from_predef(name, x, y, play_speed, attached_to)
        )
        return result


def gen_scene() -> Scene:
    return ScenePlayground()
