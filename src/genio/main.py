import pyxel

import genio.gui
from genio.scene import AppWithScenes, ReloadableScene, load_scene_from_module


def scene_factory():
    return load_scene_from_module(genio.gui)


if __name__ == "__main__":
    pyxel.init(427, 240, title="Genio")
    AppWithScenes(ReloadableScene(scene_factory))
