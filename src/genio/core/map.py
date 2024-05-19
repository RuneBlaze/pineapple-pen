from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from genio.core.base import slurp_toml


@dataclass
class Map:
    locations: Mapping[str, str]

    @staticmethod
    def default() -> Map:
        locs = slurp_toml("assets/test_locations.toml")["locations"]
        locations = {}
        for i in locs:
            locations[i["name"]] = i["description"]
        return Map(locations)
