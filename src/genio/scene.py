import imp
from abc import ABC, abstractmethod
from collections.abc import Callable

import pyxel
from structlog import get_logger

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


def load_scene_from_module(module) -> Scene:
    imp.reload(module)
    logger.info("Reloading scene", module=module)
    return module.gen_scene()


class AppWithScenes:
    def __init__(self, scene: Scene):
        self.scenes = []
        self.add_scene(scene)
        pyxel.load("/Users/lbq/goof/genio/assets/sprites.pyxres")
        pyxel.run(self.update, self.draw)

    def add_scene(self, scene: Scene):
        self.scenes.append(scene)

    def pop_scene(self):
        self.scenes.pop()

    def update(self):
        self.scenes[-1].update()
        if pyxel.btnp(pyxel.KEY_R):
            self.scenes[-1].on_request_reload()

    def draw(self):
        self.scenes[-1].draw()
