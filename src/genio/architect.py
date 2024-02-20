from __future__ import annotations

from dataclasses import dataclass, is_dataclass
from functools import cache
from random import gauss, choice
from typing import Annotated, Literal
from .family import Backdrop
from random import sample
import shelve
from functools import partial
from .base import raw_sparkle
import re
from structlog import get_logger

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

logger = get_logger()


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

    def __post_init__(self):
        if not isinstance(self.num_floors, int):
            self.num_floors = int(self.num_floors)

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
        return f"## Administrative Assistant to {self.floor_title}\n{self.floor_description}"

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


@dataclass
class ConcreteRoom:
    """A concrete room to be furnished."""

    is_classroom: bool
    name: str

    hardware_concept: str
    furniture_concept: str
    pitch: str

    description_generic: str
    description_day: str
    description_evening: str
    description_night: str


CLASSROOM_REGEX = re.compile(r"grade ([\da-z]+) class ([\da-z]+)", re.IGNORECASE)


def is_classroom_name(name: str) -> bool:
    return "class" in name.lower() and CLASSROOM_REGEX.match(name)


def parse_classroom_name(name: str) -> ClassRef:
    match = CLASSROOM_REGEX.match(name)
    if match:
        grade, class_num = match.groups()
        return ClassRef(int(grade), int(class_num))


@dataclass
class ClassRef:
    grade: int
    class_num: int

    def is_primary(self) -> bool:
        return self.grade < 7

    def is_secondary(self) -> bool:
        return not self.is_primary()


@dataclass
class HardwareConcept:
    walls_and_windows: Annotated[
        str, "A description of the walls, as designed by the architect."
    ]
    floors: Annotated[str, "A description of the floors, as designed by the architect."]
    lighting: Annotated[
        str, "A description of the lighting, as designed by the architect."
    ]


@dataclass
class FurnitureConcept:
    furniture_ideas: Annotated[list[str], "A list of furniture styles."]
    decors: Annotated[list[str], "A list of small decors and accessories for the room."]


@dataclass
class ArchitecturalGuidelines(Mythical):
    """Guidelines for the architecture of a grand school building in a "Gakuen Toshi".
    You should act as an excellent architect and come up with actionable guidelines for
    other architects to follow.

    Here is the brief about the concept of the building, a grand school building in a "Gakuen Toshi".
    ```
    {concept}
    ```

    Q: What are the guidelines for the architecture of the building?
    """

    guidelines: Annotated[list[str], "A YAML list of actionable guidelines."]
    motifs: Annotated[list[str], "A YAML list of architectural motifs."]
    materials: Annotated[list[str], "A YAML list of materials."]
    color_scheme: Annotated[str, "Actionable color scheme of the building."]

    @staticmethod
    def generate(concept: SchoolConcept) -> ArchitecturalGuidelines:
        return generate_using_docstring(
            ArchitecturalGuidelines, {"concept": concept.make_context()}
        )


@dataclass
class InteriorDesignGuidelines(Mythical):
    """Guidelines for the interior design of a grand school building in a "Gakuen Toshi".
    You should act as an excellent interior designer and come up with actionable guidelines for
    other interior designers to follow.

    Think about the materials, fabrics, and colors that would be used in the interior design.

    Here is the brief about the concept of the building, a grand school building in a "Gakuen Toshi".
    ```
    {concept}
    ```

    Q: What are the guidelines for the interior design of the building?
    """

    furniture_styles: Annotated[
        list[str], "A short description of the furniture style."
    ]
    primary_school_classroom_design: Annotated[
        str, "Short interior design concept for primary school classrooms."
    ]
    secondary_school_classroom_design: Annotated[
        str, "Short interior design concept for secondary school classrooms."
    ]
    other_rooms_design: Annotated[str, "Short interior design concept for other rooms."]

    @staticmethod
    def generate(concept: SchoolConcept) -> InteriorDesignGuidelines:
        return generate_using_docstring(
            InteriorDesignGuidelines, {"concept": concept.make_context()}
        )


quirk_keywords = [
    "studious",
    "athletic",
    "artistic",
    "musical",
    "eco-friendly",
    "tech-savvy",
    "bilingual",
    "multicultural",
    "nature lovers",
    "bookworms",
    "height uniformity",
    "animal lovers",
    "culinary experts",
    "puzzle solvers",
    "green thumbs",
    "fashion forward",
    "drama enthusiasts",
    "sci-fi fans",
    "historical buffs",
    "globetrotters",
    "comedians",
    "mystery enthusiasts",
    "adventure seekers",
    "debaters",
    "chess masters",
    "gadget geeks",
    "polyglots",
    "young entrepreneurs",
    "volunteers",
    "film buffs",
    "stargazers",
    "inventors",
    "health enthusiasts",
    "anime fans",
    "robotics whizzes",
    "time travelers",
    "philosophers",
    "poets",
    "gamers",
    "survival experts",
    "code breakers",
    "environmental activists",
    "magicians",
    "dreamers",
    "futurists",
    "historical reenactors",
    "astronaut trainees",
    "mythology lovers",
    "geniuses",
    "philanthropists",
    "peacekeepers",
    "thrill seekers",
]

EXTRA_SENTENCES = {
    "primary": {
        "room_type": "primary school classroom in a Gakuen Toshi",
        "extra": "The classroom should be designed to be friendly and welcoming to children.",
    },
    "secondary": {
        "room_type": "secondary school classroom in a Gakuen Toshi",
        "extra": "The classroom should be designed to be friendly while studious to accommodate the older students.",
    },
}


@raw_sparkle
def design_hardware_concept(
    room_type: str, extra: str, guidelines: ArchitecturalGuidelines
) -> HardwareConcept:
    """Act as an architect and design the hardware (wall, floor, lightning) concept for a {room_type}.

    {extra}

    Here are the guidelines for the design:
    ```
    {guidelines}
    ```

    {formatting_instructions}
    """
    ...


@raw_sparkle
def design_furniture_concept(
    room_type: str, extra: str, guidelines: InteriorDesignGuidelines
) -> FurnitureConcept:
    """Act as an interior designer and design the furniture concept for a {room_type}.

    {extra}

    Here are the guidelines for the design:
    ```
    {guidelines}
    ```

    {formatting_instructions}
    """
    ...



def cache_retrieve_or_generate(cache: shelve.Shelf, key: str, func: callable, *args, **kwargs):
    if key not in cache:
        cache[key] = func(*args, **kwargs)
    return cache[key]

if __name__ == "__main__":
    # school_concept = SchoolConcept.generate()
    # guidelines = ArchitecturalGuidelines.generate(school_concept)
    # interior_guidelines = InteriorDesignGuidelines.generate(school_concept)
    # floor_plan = FloorPlan.generate(school_concept)
    # concepts = floor_plan.to_individual_floor_concepts()
    # concepts_and_catalogs = []
    # for concept in concepts:
    #     concepts_and_catalogs.append((concept, concept.generate_room_catalogue()))
    # logger.info("Generated school thingies")
    # with shelve.open("assets/test") as db:
    #     db["school_concept"] = school_concept
    #     db["guidelines"] = guidelines
    #     db["interior_guidelines"] = interior_guidelines
    #     db["floor_plan"] = floor_plan
    #     db["concepts_and_catalogs"] = concepts_and_catalogs

    with shelve.open("assets/test") as db:
        school_concept = db["school_concept"]
        guidelines = db["guidelines"]
        interior_guidelines = db["interior_guidelines"]
        floor_plan = db["floor_plan"]
        concepts_and_catalogs = db["concepts_and_catalogs"]

    ic(school_concept)
    ic(guidelines)
    ic(interior_guidelines)
    ic(concepts_and_catalogs)

    for concept, catalog in concepts_and_catalogs:
        for room in catalog.rooms:
            if is_classroom_name(room):
                class_ref = parse_classroom_name(room)
                if class_ref.is_primary():
                    hardware_concept = design_hardware_concept(
                        f"primary school classroom in a Gakuen Toshi: Grade {class_ref.grade} Class {class_ref.class_num}",
                        "The classroom should be designed to be friendly and welcoming to children.",
                        guidelines,
                    )
                else:
                    hardware_concept = design_hardware_concept(
                        f"secondary school classroom in a Gakuen Toshi: Grade {class_ref.grade} Class {class_ref.class_num}",
                        "The classroom should be designed to be friendly while studious to accommodate the older students.",
                        guidelines,
                    )
                if class_ref.is_primary():
                    furniture_concept = design_furniture_concept(
                        f"primary school classroom in a Gakuen Toshi: Grade {class_ref.grade} Class {class_ref.class_num}",
                        "The classroom should be designed to be friendly and welcoming to children.",
                        interior_guidelines,
                    )
                else:
                    furniture_concept = design_furniture_concept(
                        f"secondary school classroom in a Gakuen Toshi: Grade {class_ref.grade} Class {class_ref.class_num}",
                        "The classroom should be designed to be friendly while studious to accommodate the older students.",
                        interior_guidelines,
                    )
                ic(hardware_concept)
                ic(furniture_concept)
