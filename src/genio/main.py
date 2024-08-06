import argparse
import importlib

import pyxel

import genio.ps_edit
from genio.scene import AppWithScenes, ReloadableScene, load_scene_from_module


def edit_scene_factory():
    return load_scene_from_module(genio.ps_edit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--edit", action="store_true")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--module", type=str, default="genio.gui")

    args = parser.parse_args()
    fact = edit_scene_factory if args.edit else None

    pyxel.init(427, 240, title="Pen Apple")
    if not fact:
        AppWithScenes(
            ReloadableScene(
                lambda: load_scene_from_module(importlib.import_module(args.module))
            ),
            record_from_start=args.record,
        )
    else:
        AppWithScenes(ReloadableScene(fact))
