from functools import partial
from typing import Any

from genio.base import asset_path
from genio.core.base import slurp_toml

predef = slurp_toml(asset_path("strings.toml"))


def access(structure, lens: str) -> Any:
    if "." not in lens:
        return structure[lens]
    for key in lens.split("."):
        structure = structure[key]
    return structure


access_predef = partial(access, predef)


def refresh_predef():
    reloaded = slurp_toml(asset_path("strings.toml"))
    for k, v in reloaded.items():
        predef[k] = v
