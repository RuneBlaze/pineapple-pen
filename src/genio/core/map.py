from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from genio.core.base import slurp_toml
from genio.core.tantivy import TantivyStore


@dataclass(frozen=True)
class Location:
    name: str
    description: str


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
        title = self.store.recall_one(query).title
        if found_loc := self.locations.get(title):
            return Location(title, found_loc)
        return None

    def fallback_location(self) -> Location:
        return self.search("dorm") or Location(
            "home", "a place where you feel comfortable"
        )
