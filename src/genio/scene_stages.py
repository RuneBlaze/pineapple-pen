from __future__ import annotations

import contextlib
import itertools
import textwrap
from collections import Counter, deque
from concurrent.futures import Future
from concurrent.futures.thread import ThreadPoolExecutor
from enum import Enum

import pytweening
import pyxel
from pyxelxl import layout

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, load_image
from genio.components import (
    arcade_text,
    retro_text,
)
from genio.gamestate import StageDescription, game_state
from genio.gui import dithering
from genio.layout import pingpong
from genio.ps import Anim
from genio.scene import Scene
from genio.stagegen import (
    generate_stage_description as generate_stage_description_low_level,
)
from genio.tween import Mutator, Tweener


def generate_stage_description(stage_name: str) -> StageDescription:
    results = generate_stage_description_low_level(
        stage_name, game_state.battle_bundle.battle_logs
    )
    return StageDescription(
        name=stage_name,
        subtitle=results.subtitle,
        lore=results.lore,
        danger_level=results.danger_level,
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


class MapMarker:
    def __init__(
        self, x: int, y: int, camera: Camera, stage_description: StageDescription
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

    def draw(self) -> None:
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
            pyxel.text(self.x + 3 + 15, self.y + l - 2, "1-2", 0)

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


class StageSelectScene(Scene):
    futures: deque[Future[StageDescription]]

    def __init__(self) -> None:
        super().__init__()
        self.executor = ThreadPoolExecutor(2)
        self.camera = cam = Camera()

        stage_descriptions = [
            StageDescription.default(),
        ]
        self.not_any_hovered_deadline = 0

        self.map_markers = [
            MapMarker(140, 150, cam, stage_descriptions[0]),
        ]
        self.executor = ThreadPoolExecutor(2)
        self.futures = deque()
        self.info_box = StageInfoBox()

        self.start_generation()

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
            self.map_markers.append(
                MapMarker(
                    *placement_of_marker(stage_description),
                    self.camera,
                    stage_description,
                )
            )

    def update(self) -> None:
        for marker in self.map_markers:
            marker.update()
        self.camera.update()
        self.info_box.update()
        self.check_mailbox()

        for i, marker in enumerate(self.map_markers):
            if marker.hovering or marker.state == MapMarkerState.SELECTED:
                self.info_box.pump(marker.stage_description)
                break

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
        self.info_box.draw()

        Anim.draw()
        pyxel.clip()
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def draw_crosshair(self, x, y):
        pyxel.line(x - 5, y, x + 5, y, 7)
        pyxel.line(x, y - 5, x, y + 5, 7)


def gen_scene() -> Scene:
    return StageSelectScene()
