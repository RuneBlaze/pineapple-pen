from functools import partial
from typing import Any

from genio.base import asset_path
from genio.core.base import fmap_leaves, render_jinjaish_string, slurp_toml
from dataclasses import dataclass

predef = fmap_leaves(render_jinjaish_string, slurp_toml(asset_path("strings.toml")))



def access(structure, lens: str, default: Any = ...) -> Any:
    if "." not in lens:
        if default is ...:
            return structure[lens]
        else:
            return structure.get(lens, default)
    for key in lens.split("."):
        if key not in structure:
            return default
        structure = structure[key]
    return structure


access_predef = partial(access, predef)


def refresh_predef():
    reloaded = fmap_leaves(
        render_jinjaish_string, slurp_toml(asset_path("strings.toml"))
    )
    for k, v in reloaded.items():
        predef[k] = v
