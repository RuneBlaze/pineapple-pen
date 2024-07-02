import argparse

import pyxel

import genio.gui
import genio.ps_edit
from genio.scene import AppWithScenes, ReloadableScene, load_scene_from_module


def main_scene_factory():
    return load_scene_from_module(genio.gui)


def edit_scene_factory():
    return load_scene_from_module(genio.ps_edit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--edit", action="store_true")

    args = parser.parse_args()
    fact = edit_scene_factory if args.edit else main_scene_factory

    pyxel.init(427, 240, title="Genio")
    AppWithScenes(ReloadableScene(fact))
