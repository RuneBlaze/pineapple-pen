from __future__ import annotations
from enum import Enum
import imp
from abc import ABC, abstractmethod
from collections.abc import Callable
from collections import Counter
import importlib

import pyxel
from structlog import get_logger

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, asset_path
from genio.components import mask_screen, mask_screen_out, perlin_noise_with_horizontal_gradient
from genio.predef import refresh_predef
from collections import deque

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
    def __init__(self, scene: Scene):
        self.scenes = deque()
        self.add_scene(scene)
        self.state = AppState.RUNNING
        self.state_timers = Counter()
        self.noise = perlin_noise_with_horizontal_gradient(WINDOW_WIDTH, WINDOW_HEIGHT, 0.01)
        pyxel.load(asset_path("sprites.pyxres"))
        pyxel.run(self.update, self.draw)

    def add_scene(self, scene: Scene):
        self.scenes.append(scene)

    def queue_scene(self, scene: Scene):
        self.scenes.append(scene)

    def pop_scene(self) -> None:
        self.scenes.pop()

    def set_state(self, state: AppState):
        self.state = state
        self.state_timers[state] = 0

    def update(self):
        self.scenes[0].update()
        if (next_scene := self.scenes[0].request_next_scene()) is not None:
            if isinstance(next_scene, str):
                next_scene = load_scene_from_module(importlib.import_module(next_scene))
            self.queue_scene(next_scene)
        if pyxel.btnp(pyxel.KEY_R) and self.state == AppState.RUNNING:
            self.scenes[0].on_request_reload()
        if len(self.scenes) > 1 and self.state == AppState.RUNNING:
            self.set_state(AppState.TRANSITION_OUT)
        self.state_timers[self.state] += 1

        match self.state:
            case AppState.TRANSITION_OUT:
                if self.state_timers[self.state] >= 90:
                    self.scenes.popleft()
                    self.set_state(AppState.TRANSITION_IN)
            case AppState.TRANSITION_IN:
                if self.state_timers[self.state] >= 90:
                    self.set_state(AppState.RUNNING)

    def draw(self):
        self.scenes[0].draw()
        timer = self.state_timers[self.state]
        if self.state == AppState.TRANSITION_OUT:
            mask_screen_out(self.noise, timer / 60, 0)
        elif self.state == AppState.TRANSITION_IN:
            mask_screen(self.noise, timer / 60, 0)
