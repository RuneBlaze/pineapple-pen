from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import ClassVar

from genio.concepts.geo import (
    default_klasses,
    default_locations,
    design_generic_schedule,
)
from genio.core.agent_cache import agent_cache
from genio.core.clock import global_clock
from genio.core.map import Map
from genio.core.tantivy import global_factual_storage


class GlobalComponents:
    _instance: ClassVar[GlobalComponents] = None
    occupancy: Mapping[str, list]

    def __init__(self) -> None:
        self.locs = default_locations()
        self.klasses = default_klasses()
        self.factual_storage = global_factual_storage()
        for loc in self.locs:
            self.factual_storage.insert("Location: " + loc.name, loc.description)
        self.schedule = design_generic_schedule(self.locs, self.klasses)
        self.map = Map.default()
        self.clock = global_clock
        self.occupancy = defaultdict(list)

    @staticmethod
    def instance() -> GlobalComponents:
        if not GlobalComponents._instance:
            if global_components := agent_cache.get("global_components"):
                GlobalComponents._instance = global_components
            else:
                GlobalComponents._instance = GlobalComponents()
                agent_cache["global_components"] = GlobalComponents._instance
        return GlobalComponents._instance

    @staticmethod
    def save_instance() -> None:
        agent_cache["global_components"] = GlobalComponents.instance()
