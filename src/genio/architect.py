from __future__ import annotations

from dataclasses import dataclass, is_dataclass
from functools import cache
from random import gauss, choice
from typing import Annotated, Literal
from .family import Backdrop
from random import sample

from .namegen import NameGenerator
from .base import slurp_toml

import faker
import yaml
from icecream import ic

from .base import (
    Mythical,
    WriterArchetype,
    generate_using_docstring,
    slurp_toml,
    sparkle,
)


@cache
def architectural_elements() -> dict:
    return slurp_toml("assets/architecture/architectural_elements.toml")


def sample_architectural_keywords() -> list[str]:
    elements = architectural_elements()
    keys = list(elements.keys())
    k1, k2 = sample(keys, 2)
    return sample(elements[k1][0]["keywords"], 2) + sample(
        elements[k2][0]["keywords"], 1
    )


@cache
def literature_elements() -> str:
    return slurp_toml("assets/architecture/lit.toml")


def sample_literature() -> str:
    kv = literature_elements()["classical_literature"]
    k = choice([k for k in kv.keys()])
    return f"{k}: {kv[k]}"


def format_markdown_list(items: list[str]) -> str:
    return "\n".join([f"- {i}" for i in items])


def yamlize(item: object) -> str:
    if is_dataclass(item):
        return yaml.dump(item.__dict__)
    return yaml.dump(item)


@dataclass
class SchoolConcept(Mythical):
    """An architectural design concept for a grand school building in a "Gakuen Toshi".

    Here is the brief of the city:
    ```
    {city_lore}
    ```

    Act as a reknowned designer with a specific love of literature works such as
    "{literature}". This time, you decide to try an architectural marvel using the following elements:

    ```
    {elements}
    ```

    Write your best magnus opus for the concept. This is a grand school encompassing
    both the primary and secondary levels.
    """

    description: Annotated[
        str, "A brief description of the concept, in four to six sentences."
    ]
    magnus_opus: Annotated[
        str, "The core of the concept, in a single sentence, fitting for a magnus opus."
    ]
    color_scheme: Annotated[
        str, "The color scheme of the building, in a single sentence."
    ]
    materials: Annotated[str, "The materials for the building."]
    unique_structure: Annotated[
        str, "A unique structure or feature that sets the building apart."
    ]

    @staticmethod
    def generate() -> SchoolConcept:
        city = Backdrop.default()
        return generate_using_docstring(
            SchoolConcept,
            {
                "city_lore": city.description,
                "literature": sample_literature(),
                "elements": format_markdown_list(sample_architectural_keywords()),
            },
        )


@dataclass
class FloorPlan(Mythical):
    """A high-level floor plan for a grand school, how many floors, and what's on them in general,
    as if designed by an excellent architect.

    Here is the brief about the concept of the building, a grand school building in a "Gakuen Toshi".
    ```
    {concept}
    ```

    Come up with a floor plan for the building, including the number of floors and the general
    layout of each floor. The building should be grand, encompassing both the primary and secondary
    levels.

    Each grade requires at least half a floor.
    """

    num_floors: Annotated[
        int,
        "The number of floors in the building. Should be at least 6. It should be sprawling and almost maze-like",
    ]
    floor_description_list: Annotated[
        list[str],
        "A list of descriptions for each floor, should be a YAML list, in the format - F0/1/2/3/4: single-line description.",
    ]

    @staticmethod
    def generate(concept: SchoolConcept) -> FloorPlan:
        return generate_using_docstring(FloorPlan, {"concept": concept.make_context()})

    def to_individual_floor_concepts(self) -> list[SingleFloorConcept]:
        concepts = []
        num_floors = self.num_floors
        for i in range(num_floors):
            concepts.append(
                generate_using_docstring(
                    SingleFloorConcept,
                    {"n": i, "grand_concept": yamlize(self.floor_description_list)},
                )
            )
        return concepts


@dataclass
class SingleFloorConcept:
    """Single floor concept for a grand school building in a "Gakuen Toshi".
    Your job is to extract the information from the grand concept and create a single floor concept.

    Extract from this grand concept:
    ```
    {grand_concept}
    ```

    Q: What's the {n}-th single floor (Floor {n}) for?
    """

    floor_title: str
    floor_description: str

    def make_context(self) -> str:
        return f"## {self.floor_title}\n{self.floor_description}"

    @sparkle
    def generate_room_catalogue(self) -> RoomCatalogue:
        """Be an administrative assistant and exhaustively list the rooms on the given floor.

        The rooms should be in a YAML list.
        Classrooms should be named as "Grade X Class X" where X is the grade number,
        and the other rooms should be named as they are. Each grade should have at least two classrooms.
        """
        ...


@dataclass
class RoomCatalogue:
    rooms: Annotated[
        list[str], "A *single* YAML list of rooms in the floor. Only the names."
    ]


if __name__ == "__main__":
    school_concept = SchoolConcept.generate()
    ic(school_concept)
    floor_plan = FloorPlan.generate(school_concept)
    ic(floor_plan)
    concepts = floor_plan.to_individual_floor_concepts()
    for concept in concepts:
        ic(concept)
        ic(concept.generate_room_catalogue())
