from __future__ import annotations

import imp
import importlib
import sys
from abc import ABC, abstractmethod
from collections import Counter, deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from enum import Enum

import pyxel
from pyxelxl.font import _image_as_ndarray
from structlog import get_logger

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, asset_path
from genio.components import (
    mask_screen,
    mask_screen_out,
    perlin_noise_with_horizontal_gradient,
)
from genio.predef import refresh_predef

logger = get_logger()


class Scene(ABC):
    @abstractmethod
    def update(self):
        ...

    @abstractmethod
    def draw(self):
        ...

    def on_request_reload(self):
        pass

    def request_next_scene(self) -> Scene | None | str:
        return None


class ReloadableScene(Scene):
    def __init__(self, scene_factory: Callable[[], Scene]) -> None:
        super().__init__()
        self.scene_factory = scene_factory
        self.current_version = self.scene_factory()

    def update(self):
        self.current_version.update()

    def draw(self):
        self.current_version.draw()

    def on_request_reload(self):
        refresh_predef()
        to_reload_modules = [
            module
            for module in sys.modules.values()
            if module.__name__.startswith("genio")
        ]
        for module in to_reload_modules:
            # filter out everything not named genio
            if not module.__name__.startswith("genio"):
                continue
            importlib.reload(module)
        self.current_version = self.scene_factory()

    def request_next_scene(self) -> Scene | None | str:
        return self.current_version.request_next_scene()


def load_scene_from_module(module) -> Scene:
    imp.reload(module)
    logger.info("Reloading scene", module=module)
    return module.gen_scene()


class AppState(Enum):
    RUNNING = 1
    TRANSITION_OUT = 2
    TRANSITION_IN = 3


class AppWithScenes:
    scenes: deque[Scene]
    screenshot: pyxel.Image | None

    def __init__(self, scene: Scene):
        self.scenes = deque()
        self.add_scene(scene)
        self.state = AppState.RUNNING
        self.state_timers = Counter()
        self.noise = perlin_noise_with_horizontal_gradient(
            WINDOW_WIDTH, WINDOW_HEIGHT, 0.01
        )
        self.executor = ThreadPoolExecutor(1)
        self.futures = deque()
        self.all_black = pyxel.Image(WINDOW_WIDTH, WINDOW_HEIGHT)
        _image_as_ndarray(self.all_black)[:] = 0
        self.screenshot = None

        pyxel.load(asset_path("sprites.pyxres"))
        pyxel.run(self.update, self.draw)

    def add_scene(self, scene: Scene) -> None:
        self.scenes.append(scene)

    def queue_scene(self, scene: Scene) -> None:
        self.scenes.append(scene)

    def pop_scene(self) -> None:
        self.scenes.pop()

    def set_state(self, state: AppState) -> None:
        self.state = state
        self.state_timers[state] = 0

    def update(self) -> None:
        self.scenes[0].update()
        if (
            not self.futures
            and (next_scene := self.scenes[0].request_next_scene()) is not None
        ):
            match next_scene:
                case (next_scene, fade_image) if isinstance(next_scene, str):
                    self.screenshot = fade_image
                    fut = self.executor.submit(
                        lambda: load_scene_from_module(
                            importlib.import_module(next_scene)
                        )
                    )
                    self.futures.append(fut)
                case next_scene if isinstance(next_scene, str):
                    fut = self.executor.submit(
                        lambda: load_scene_from_module(
                            importlib.import_module(next_scene)
                        )
                    )
                    self.screenshot = None
                    self.futures.append(fut)
                case _:
                    raise NotImplementedError
        if self.futures and self.futures[0].done():
            self.queue_scene(self.futures.popleft().result())
        if self.state == AppState.RUNNING:
            if pyxel.btnp(pyxel.KEY_R):
                self.scenes[0].on_request_reload()
                self.state = AppState.RUNNING
                self.state_timers.clear()
            if self.futures:
                self.set_state(AppState.TRANSITION_OUT)
        self.state_timers[self.state] += 1

        match self.state:
            case AppState.TRANSITION_OUT:
                if self.state_timers[self.state] >= 90 and not self.futures:
                    self.scenes.popleft()
                    self.set_state(AppState.TRANSITION_IN)
            case AppState.TRANSITION_IN:
                if self.state_timers[self.state] >= 90:
                    self.set_state(AppState.RUNNING)
                    self.screenshot = None

    def draw(self):
        self.scenes[0].draw()
        timer = self.state_timers[self.state]
        if self.state == AppState.TRANSITION_OUT:
            if self.screenshot:
                opacity = min(timer / 60, 1)
                pyxel.dither(opacity)
                pyxel.blt(0, 0, self.screenshot, 0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
                pyxel.blt(0, 0, self.all_black, 0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, 0)
                pyxel.dither(1.0)
            else:
                mask_screen_out(self.noise, timer / 60, 0)
        elif self.state == AppState.TRANSITION_IN:
            if self.screenshot:
                opacity = 1 - min(timer / 60, 1)
                pyxel.dither(opacity)
                pyxel.blt(0, 0, self.screenshot, 0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
                pyxel.blt(0, 0, self.all_black, 0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, 0)
                pyxel.dither(1.0)
            else:
                mask_screen(self.noise, timer / 60, 0)
