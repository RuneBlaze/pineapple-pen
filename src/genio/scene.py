from __future__ import annotations

import imp
import importlib
import sys
from abc import ABC, abstractmethod
from collections import Counter, deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

import pyxel
from pyxelxl.font import _image_as_ndarray
from structlog import get_logger

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, asset_path, load_image
from genio.components import (
    mask_screen,
    mask_screen_out,
    perlin_noise_with_horizontal_gradient,
)
from genio.eventbus import Event, LLMInboundEv, LLMOutboundEv, event_bus
from genio.gears.async_visualizer import AsyncVisualizer
from genio.gears.recorder import Recorder
from genio.predef import refresh_predef
from genio.sound_events import SoundEv
from genio.tween import Instant

logger = get_logger()


class Scene(ABC):
    @abstractmethod
    def update(self) -> None:
        ...

    @abstractmethod
    def draw(self) -> None:
        ...

    def on_request_reload(self) -> None:
        pass

    def request_next_scene(self) -> Scene | None | str:
        return None

    def draw_cursor(self, x, y):
        cursor = load_image("cursor.png")
        pyxel.blt(x, y, cursor, 0, 0, 16, 16, colkey=254)


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
        app_with_scenes = AppWithScenes.instance
        refresh_predef()
        to_reload_modules = [
            module
            for module in sys.modules.values()
            if module.__name__.startswith("genio") or module.__name__.startswith("surv")
        ]
        for module in to_reload_modules:
            # filter out everything not named genio
            if not module.__name__.startswith(
                "genio"
            ) and not module.__name__.startswith("surv"):
                continue
            importlib.reload(module)
        self.current_version = self.scene_factory()
        AppWithScenes.instance = app_with_scenes

    def request_next_scene(self) -> Scene | None | str:
        return self.current_version.request_next_scene()

    def add_anim(self, *args, **kwargs) -> None:
        self.current_version.add_anim(*args, **kwargs)


def load_scene_from_module(module) -> Scene:
    imp.reload(module)
    logger.info("Reloading scene", module=module)
    return module.gen_scene()


class AppState(Enum):
    RUNNING = 1
    TRANSITION_OUT = 2
    TRANSITION_IN = 3


@dataclass
class MouseDownEvent:
    x: int
    y: int
    canceled: bool = False

    def stop_propagation(self) -> None:
        self.canceled = True


class AppWithScenes:
    instance: ClassVar[AppWithScenes] | None = None
    scenes: deque[Scene]
    screenshot: pyxel.Image | None
    events: list[SoundEv]

    def __init__(self, scene: Scene, record_from_start: bool = False) -> None:
        if AppWithScenes.instance is not None:
            raise RuntimeError("AppWithScenes is a singleton")
        AppWithScenes.instance = self
        self.scenes = deque()
        self.add_scene(scene)
        self.state = AppState.TRANSITION_IN
        self.state_timers = Counter()
        self.async_visualizer = AsyncVisualizer(self)
        self.noise = perlin_noise_with_horizontal_gradient(
            WINDOW_WIDTH, WINDOW_HEIGHT, 0.01
        )
        self.executor = ThreadPoolExecutor(1)
        self.futures = deque()
        self.all_black = pyxel.Image(WINDOW_WIDTH, WINDOW_HEIGHT)
        _image_as_ndarray(self.all_black)[:] = 0
        self.screenshot = None
        event_bus.add_listener(self.on_event, "app")

        self.recorder = Recorder(self)
        if record_from_start:
            logger.info("Recording from start")
            self.recorder.toggle_recording()
        self.events = []
        self.sound_effects = []

        self.input_events = []
        self.load_sound_effects()

        pyxel.load(asset_path("sprites.pyxres"))
        pyxel.run(self.update, self.draw)

    def load_sound_effects(self) -> None:
        ...
        # for p in access_predef("sounds.predefined"):
        #     self.sound_effects.append(sa.WaveObject.from_wave_file(asset_path(p)))

    def add_anim(self, *args, **kwargs) -> None:
        self.scenes[0].add_anim(*args, **kwargs)

    def emit_sound_event(self, event: SoundEv) -> None:
        self.events.append(event.value)

    def on_event(self, event: Event) -> None:
        logger.info("AppWithScenes.on_event", ev=event)
        match event:
            case LLMOutboundEv():
                logger.info("AppWithScenes.on_event; case 0", ev=event)
                self.async_visualizer.ping()
            case LLMInboundEv():
                self.async_visualizer.pong()

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
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.input_events.append(MouseDownEvent(pyxel.mouse_x, pyxel.mouse_y))
        self.scenes[0].update()
        self.async_visualizer.update()
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
        if pyxel.btnp(pyxel.KEY_S):
            self.recorder.toggle_recording()
        self.play_all_audios()
        self.events.clear()
        self.input_events.clear()

    def play_all_audios(self) -> None:
        for ev in self.events:
            if ev < len(self.sound_effects):
                self.sound_effects[ev].play()

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
        self.async_visualizer.draw()
        self.recorder.update()
        self.recorder.draw()


def module_scene(cls: type[Scene]) -> type[Scene]:
    """
    Decorator that simplifies the creation of a top-level scene generation function
    for classes inheriting from `genio.scene.Scene`.
    """

    def gen_scene() -> Scene:
        return cls()

    # Add the function to the module's global namespace
    module = sys.modules[cls.__module__]
    setattr(module, "gen_scene", gen_scene)

    return cls


def emit_sound_event(event: SoundEv) -> None:
    if ins := AppWithScenes.instance:
        ins.emit_sound_event(event)


def EmitSound(sound_ev: SoundEv) -> Instant:
    return Instant(lambda: emit_sound_event(sound_ev))


def input_events() -> list[MouseDownEvent]:
    if ins := AppWithScenes.instance:
        return ins.input_events
    return []
