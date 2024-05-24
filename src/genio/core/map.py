from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from genio.core.base import slurp_toml
from genio.core.tantivy import TantivyStore

if TYPE_CHECKING:
    from genio.core.agent import Agent


@dataclass(frozen=True)
class Location:
    name: str
    description: str

    occupancy: ClassVar[Mapping[str, list[Agent]]] = defaultdict(list)

    def add_occupancy(self, agent: Agent) -> None:
        self.occupancy[self.name].append(agent)

    def remove_occupancy(self, agent: Agent) -> None:
        self.occupancy[self.name].remove(agent)


@dataclass
class Map:
    locations: Mapping[str, str]
    store: TantivyStore

    @staticmethod
    def default() -> Map:
        locs = slurp_toml("assets/test_locations.toml")["locations"]
        locations = {}
        store = TantivyStore()
        for i in locs:
            locations[i["name"]] = i["description"]
            store.insert(i["name"], i["description"], None)
        return Map(locations, store)

    def search(self, query: str) -> Location | None:
        entry = self.store.recall_one(query)
        if not entry:
            return None
        title = entry.title
        if found_loc := self.locations.get(title):
            return Location(title, found_loc)
        return None

    def fallback_location(self) -> Location:
        return self.search("dorm") or Location(
            "home", "a place where you feel comfortable"
        )


if __name__ == "__main__":
    m = Map.default()
    print(m.default())
