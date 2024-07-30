from __future__ import annotations

import contextlib
import itertools
import textwrap
from collections import Counter, deque
from concurrent.futures import Future
from concurrent.futures.thread import ThreadPoolExecutor
from enum import Enum

import numpy as np
import pytweening
import pyxel
from pyxelxl import layout

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, load_image
from genio.battle import _generate_enemy_profile
from genio.bezier import QuadBezier
from genio.components import (
    CanAddAnim,
    HasPos,
    arcade_text,
    retro_text,
)
from genio.gamestate import StageDescription, game_state
from genio.gears.map_pin import MapPin
from genio.gears.signpost import SignPost
from genio.gears.weather import WeatherEffect, WeatherType
from genio.gui import dithering
from genio.layout import pingpong
from genio.ps import Anim
from genio.scene import Scene
from genio.stagegen import (
    generate_stage_description as generate_stage_description_low_level,
)
from genio.tween import Instant, Mutator, Tweener
from genio.vector import Vec2Int

executor = ThreadPoolExecutor(4)


def generate_stage_description(stage_name: str) -> StageDescription:
    results = generate_stage_description_low_level(
        stage_name, game_state.battle_bundle.battle_logs
    )
    futs = []
    for enemy_idea in results.enemy_troop:
        futs.append(executor.submit(_generate_enemy_profile, enemy_idea))
    gathered_futs = [fut.result() for fut in futs]
    enemy_profiles = [fut.to_enemy_profile() for fut in gathered_futs]
    return StageDescription(
        name=stage_name,
        subtitle=results.subtitle,
        lore=results.lore,
        danger_level=results.danger_level,
        enemies=enemy_profiles,
    )


def draw_tiled(img: pyxel.Image, ignore_col: int | None = 0) -> None:
    w, h = img.width, img.height
    for x, y in itertools.product(
        range(-w * 2, WINDOW_WIDTH, w), range(-h * 2, WINDOW_HEIGHT, h)
    ):
        pyxel.blt(x, y, img, 0, 0, w, h, ignore_col)


def placement_of_marker(desc: StageDescription) -> tuple[int, int]:
    # FIXME: do more advanced placement
    match desc.name:
        case "1-2A":
            return 120, 100
        case "1-2B":
            return 200, 80
        case _:
            return 120, 100


class Camera:
    def __init__(self, follow: MapMarker | None = None) -> None:
        self.tweener = Tweener()
        self.x = 0
        self.y = 0
        self.follow = follow
        self.memory_y = None
        self.memory_x = None

    # 8, 120
    def update(self):
        self.tweener.update()
        if self.follow is None:
            return
        target_x = self.follow.x - WINDOW_WIDTH * 0.4
        target_y = self.follow.y - WINDOW_HEIGHT // 2
        if self.x == target_x and self.y == target_y:
            return
        if self.memory_y != target_y or self.memory_x != target_x:
            self.memory_y = target_y
            self.memory_x = target_x
            self.tweener.append_and_flush_previous(
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


class StageInfoBox:
    description: StageDescription | None

    def __init__(self) -> None:
        self.description = None
        self.energy = 0.0

    def pump(self, description: StageDescription) -> None:
        self.description = description
        self.energy += 0.2
        self.energy = min(1.5, self.energy)

    def update(self) -> None:
        self.energy -= 0.1
        self.energy = max(0.0, self.energy)

    @property
    def truncated_energy(self) -> float:
        return min(1.0, self.energy)

    def draw(self) -> None:
        t = self.truncated_energy
        pyxel.camera(0, -t * 3)
        with dithering(t):
            self._draw()
        pyxel.camera(0, 0)

    def _draw(self) -> None:
        if not self.description:
            return
        d = self.description
        w = 120
        x = 240
        y = 40
        with dithering(0.5):
            draw_rounded_rectangle(x, y, w, 140, 4, 5)
        c1 = 7
        arcade_text(x, y + 5, d.name, c1, layout=layout(w=w, ha="center"))
        retro_text(x, y + 20, d.subtitle, c1, layout=layout(w=w, ha="center"))

        self.draw_danger_level(w, x, y)

        for i, line in enumerate(textwrap.wrap(self.description.lore, 26)):
            pyxel.text(x + 8, y + 84 + i * 7, line, 7)

    def draw_danger_level(self, w, x, y):
        background_image = load_image("ui", "yellow-ruins.png")
        with dithering(1):
            pyxel.rect(x + w // 2 - 50, y + 39, 48 + 53, 16 + 20, 1)
        with dithering(0.5):
            pyxel.blt(
                x + w // 2 - 50, y + 39, background_image, 40, 54, 48 + 53, 16 + 20, 254
            )
        pyxel.text(x + w // 2 - 24, y + 57, "Danger Level", 7)
        total_num_stars = self.description.danger_level
        left_shift = (total_num_stars - 1) * 4
        for i in range(total_num_stars):
            pyxel.blt(x + w // 2 - 4 - left_shift + i * 8, y + 49, 0, 8, 120, 8, 8, 0)


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
            self.scene.add_anim("anims.map_marker_appear", x + 3, y)
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


def draw_lush_background() -> None:
    pyxel.clip()
    with dithering(0.25):
        draw_tiled(load_image("tiles-black.png"), 4)
    pyxel.clip(0 + 30, 0 + 30, WINDOW_WIDTH - 60, WINDOW_HEIGHT - 60)
    draw_tiled(load_image("tiles-black.png"), None)
    pyxel.dither(0.5)
    pyxel.blt(100, 60, img := load_image("flowers.png"), 0, 0, 427, 240, 254)
    pyxel.dither(1)
    pyxel.blt(100, 60, img, 0, 0, img.width - 10, img.height - 10, 254)
    pyxel.dither(0.5)
    pyxel.dither(1.0)


class BezierAnimation:
    def __init__(
        self,
        p0: Vec2Int,
        p1: Vec2Int,
        sign: bool = True,
        col: int = 15,
        parent: CanAddAnim = None,
    ) -> None:
        midpoint = (p0 + p1) / 2
        n = np.linalg.norm(p1 - midpoint)
        if np.isclose(n, 0):
            dir = np.array([0, 0])
        else:
            dir = (p1 - midpoint) / n
            dir = np.array([-dir[1], dir[0]])
        mult = 1 if sign else -1
        c = midpoint + np.linalg.norm(p1 - p0) * mult * 0.3 * dir
        self.curve = QuadBezier(p0, c, p1)
        self.parent = parent
        self.tween = Tweener()
        self.t0 = 0.0
        self.t1 = 0.0
        self.col = col
        self.dead = False
        self.play()

    def screen_pos(self) -> tuple[int, int]:
        return tuple(self.curve.evaluate(self.t1))

    def play(self) -> None:
        self.parent.add_anim("anims.slow_walking", 0, 0, attached_to=self)
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
        self.tween.append(
            Instant(
                lambda: setattr(self, "dead", True),
            )
        )

    def draw(self) -> None:
        self.curve.draw(t0=self.t0, t1=self.t1, col=self.col)

    def update(self) -> None:
        self.tween.update()


class DrawBezier:
    def __init__(self, bezier_anim: BezierAnimation) -> None:
        self.bezier_anim = bezier_anim

    def __iter__(self):
        for _ in range(120):
            self.bezier_anim.update()
            yield


class PumpEnenergyFor:
    def __init__(
        self, info_box: StageInfoBox, stage_description: StageDescription
    ) -> None:
        self.info_box = info_box
        self.stage_description = stage_description

    def __iter__(self):
        for _ in range(60):
            self.info_box.pump(self.stage_description)
            yield


class StageSelectScene(Scene):
    futures: deque[Future[StageDescription]]
    sign_posts: list[SignPost]

    def __init__(self) -> None:
        super().__init__()
        self.executor = ThreadPoolExecutor(2)
        self.camera = cam = Camera()

        stage_descriptions = [
            StageDescription.default(),
        ]
        self.not_any_hovered_deadline = 0
        self.anims = []
        self.tweens = Tweener()

        self.map_markers = [
            first_marker := MapMarker(140, 150, cam, stage_descriptions[0], self),
        ]
        self.map_pin = MapPin(first_marker.x + 10, first_marker.y + 10, self)
        self.map_pin.appear()
        self.executor = ThreadPoolExecutor(2)
        self.futures = deque()
        self.info_box = StageInfoBox()
        self.beziers = []
        self.finished_counter = 0
        self.sign_posts = []
        self.currently_selected = None
        self.start_generation()
        self.weather = WeatherEffect(self, WeatherType.RAINY, 2, ["anims.fallen_leaf"])

        self.weather2 = WeatherEffect(
            self, WeatherType.BORDER_RIGHT_WIND, 0.8, ["anims.fallen_leaf2"]
        )

        self.sign_posts.append(
            SignPost(
                40, WINDOW_HEIGHT - 50, "W1: " + game_state.world.name, self, "willow"
            )
        )

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

    def start_generation(self) -> None:
        self.futures.append(
            self.executor.submit(
                lambda: generate_stage_description("1-2A"),
            ),
        )

        self.futures.append(
            self.executor.submit(
                lambda: generate_stage_description("1-2B"),
            ),
        )

    def check_mailbox(self) -> None:
        while self.futures and self.futures[0].done():
            stage_description = self.futures.popleft().result()
            self.tweens.append(
                itertools.zip_longest(
                    Instant(
                        (lambda sd: lambda: self.add_map_marker(sd))(stage_description)
                    ),
                    Instant(
                        (
                            lambda sd: lambda: self.beziers.append(
                                BezierAnimation(
                                    np.array(
                                        [self.map_markers[0].x, self.map_markers[0].y]
                                    )
                                    + np.array([3, 0]),
                                    np.array(placement_of_marker(sd))
                                    + np.array([3, 0]),
                                    parent=self,
                                )
                            )
                        )(stage_description)
                    ),
                    range(120),
                    itertools.chain(
                        range(30),
                        PumpEnenergyFor(self.info_box, stage_description),
                    ),
                ),
                Instant(self.increment_finished_counter),
            )

    def increment_finished_counter(self) -> None:
        self.finished_counter += 1
        if self.finished_counter == 2:
            self.camera.follow = self.map_markers[0]

    def add_map_marker(self, stage_description: StageDescription) -> None:
        self.map_markers.append(
            MapMarker(
                *placement_of_marker(stage_description),
                self.camera,
                stage_description,
                self,
                appearing=True,
            )
        )
        self.camera.follow = self.map_markers[-1]

    def update(self) -> None:
        for marker in self.map_markers:
            marker.update()
        self.camera.update()
        self.info_box.update()
        self.map_pin.update()
        self.check_mailbox()
        self.weather.update()
        self.weather2.update()

        for i, marker in enumerate(self.map_markers):
            if marker.hovering or marker.state == MapMarkerState.SELECTED:
                self.info_box.pump(marker.stage_description)
                break

        self.tweens.update()

        any_selected = any(
            marker.state == MapMarkerState.SELECTED for marker in self.map_markers
        )
        if any_selected:
            for i, marker in enumerate(self.map_markers):
                if marker.hovering and not marker.state == MapMarkerState.SELECTED:
                    for other_marker in self.map_markers:
                        if other_marker.state == MapMarkerState.SELECTED:
                            marker.set_state(MapMarkerState.IDLE)
                            continue
        for i, marker in enumerate(self.map_markers):
            if marker.state == MapMarkerState.SELECTED and self.currently_selected != i:
                self.tweens.append(
                    range(15),
                    Instant(lambda: self.map_pin.move_to(marker.x + 10, marker.y + 10)),
                )
                self.currently_selected = i
                break
        for anim in self.anims:
            anim.update()
        self.anims = [anim for anim in self.anims if not anim.dead]
        for bezier in self.beziers:
            bezier.update()
        self.beziers = [bezier for bezier in self.beziers if not bezier.dead]

        any_hovered = any(marker.hovering for marker in self.map_markers)
        if not any_hovered:
            self.not_any_hovered_deadline += 1
        else:
            self.not_any_hovered_deadline = 0
        if self.not_any_hovered_deadline > 120:
            for marker in self.map_markers:
                if marker.state == MapMarkerState.SELECTED:
                    marker.set_state(MapMarkerState.IDLE)
                    self.camera.follow = None
        two_selected = (
            sum(marker.state == MapMarkerState.SELECTED for marker in self.map_markers)
            >= 2
        )
        for sign_post in self.sign_posts:
            sign_post.update()
        self.sign_posts = [
            sign_post for sign_post in self.sign_posts if not sign_post.is_dead()
        ]
        if two_selected:
            for marker in self.map_markers:
                if marker.state == MapMarkerState.SELECTED and not marker.hovering:
                    marker.set_state(MapMarkerState.IDLE)
                    self.camera.follow = None

    def draw(self) -> None:
        pyxel.cls(0)
        with self.camera.focus():
            draw_lush_background()

            for marker in self.map_markers:
                marker.draw()

            Anim.draw()
            for bezier in self.beziers:
                bezier.draw()
            self.map_pin.draw()
        self.info_box.draw()

        Anim.draw()
        pyxel.clip()

        for sign_post in self.sign_posts:
            sign_post.draw()
        self.draw_mouse_cursor(pyxel.mouse_x, pyxel.mouse_y)

    def draw_mouse_cursor(self, x: int, y: int) -> None:
        cursor = load_image("cursor.png")
        pyxel.blt(x, y, cursor, 0, 0, 16, 16, colkey=254)

    def draw_overlay(self) -> None:
        from genio.components import willow_branch

        willow_branch(
            40,
            WINDOW_HEIGHT - 50,
            "W1: " + game_state.world.name,
            7,
        )


def gen_scene() -> Scene:
    return StageSelectScene()
