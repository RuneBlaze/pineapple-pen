from __future__ import annotations

import pickle as pkl
import re
import shelve
from dataclasses import dataclass
from functools import cache
from random import choice, sample
from typing import Annotated

from structlog import get_logger
from tqdm import tqdm

from ..core.base import (
    Mythical,
    generate_using_docstring,
    promptly,
    slurp_toml,
    sparkle,
    yamlize,
)
from .family import Backdrop

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


@dataclass
class SchoolConcept(Mythical):
    """An architectural design concept for a grand school building in a "Gakuen Toshi".

    Here is the brief of the city:
    ```
    {{city_lore}}
    ```

    Act as a reknowned designer with a specific love of literature works such as
    "{{literature}}". This time, you decide to try an architectural marvel using the following elements:

    ```
    {{elements}}
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
    {{concept}}
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
    {{grand_concept}}
    ```

    Q: What's the {{n}}-th single floor (Floor {{n}}) for?
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
        str,
        "A description of the walls, as designed by the architect. No more than two sentences.",
    ]
    floors: Annotated[
        str,
        "A description of the floors, as designed by the architect. No more than two sentences.",
    ]
    lighting: Annotated[
        str,
        "A description of the lighting, as designed by the architect. No more than two sentences.",
    ]


@dataclass
class FurnitureConcept:
    furniture_ideas: Annotated[
        list[str], "A list of furniture styles. No more than four list entries."
    ]
    decors: Annotated[
        list[str],
        "A list of small decors and accessories for the room. No more than four list entries.",
    ]


@dataclass
class ArchitecturalGuidelines(Mythical):
    """Guidelines for the architecture of a grand school building in a "Gakuen Toshi".
    You should act as an excellent architect and come up with actionable guidelines for
    other architects to follow.

    Here is the brief about the concept of the building, a grand school building in a "Gakuen Toshi".
    ```
    {{concept}}
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
    {{concept}}
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


@promptly
def design_hardware_concept(
    room_type: str, extra: str, guidelines: ArchitecturalGuidelines
) -> HardwareConcept:
    """Act as an architect and design the hardware (wall, floor, lightning) concept for a {{room_type}}.

    {{extra}}

    Here are the guidelines for the design:
    ```
    {{guidelines}}
    ```

    {{formatting_instructions}}
    """
    ...


@promptly
def design_furniture_concept(
    room_type: str, extra: str, guidelines: InteriorDesignGuidelines
) -> FurnitureConcept:
    """Act as an interior designer and design the furniture concept for a {{room_type}}.

    {{extra}}

    Here are the guidelines for the design:
    ```
    {{guidelines}}
    ```

    {{formatting_instructions}}
    """
    ...


@dataclass
class NovelistConcept:
    room_name: Annotated[str, "The name of the room."]
    brief_description: Annotated[
        str, "A brief description of the room, in one sentence."
    ]
    longer_description: Annotated[
        str,
        (
            "A longer description of the room, as if intro"
            "text for the player in a text adventure game."
            "Describe visuals, sounds, and smells."
            "Elicit mental imagery."
        ),
    ]


@promptly
def design_novelist_concept(
    room_name: str,
    hardware_concept: HardwareConcept,
    furniture_concept: FurnitureConcept,
) -> NovelistConcept:
    """Act as a novelist doing excellent game design, and write the lore text for a {{room_name}}.

    Remember, you are writing for a game, so the lore text should be engaging and interesting,
    while be informational to new players.

    Here are the hardware and furniture concepts for the room:
    ```
    {{hardware_concept}}
    {{furniture_concept}}
    ```

    {{formatting_instructions}}
    """


class LogicalClassroom:
    def __init__(
        self,
        class_ref: ClassRef,
        hardware_concept: HardwareConcept,
        furniture_concept: FurnitureConcept,
    ):
        self.class_ref = class_ref
        self.hardware_concept = hardware_concept
        self.furniture_concept = furniture_concept
        self.students = []


def cache_retrieve_or_generate(
    cache: shelve.Shelf, key: str, func: callable, *args, **kwargs
):
    if key not in cache:
        cache[key] = func(*args, **kwargs)
    return cache[key]


@dataclass
class ConceptPacket:
    school_concept: SchoolConcept
    architectural_guidelines: ArchitecturalGuidelines
    interior_guidelines: InteriorDesignGuidelines
    floor_plan: FloorPlan
    concepts_and_catalogues: list[tuple[SingleFloorConcept, RoomCatalogue]]
    floor_rooms: list[list[TriConcept]]


@dataclass
class TriConcept:
    hardware_concept: HardwareConcept
    furniture_concept: FurnitureConcept
    novelist_concept: NovelistConcept

    classref: ClassRef | None = None

    @property
    def name(self) -> str:
        return self.novelist_concept.room_name


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
    tri_concepts = []
    cached_primary_school_hardware = []
    cached_secondary_school_hardware = []
    cached_primary_school_furniture = []
    cached_secondary_school_furniture = []
    tt = sum([len(c.rooms) for _, c in concepts_and_catalogs])
    with tqdm(total=tt) as pbar:
        for concept, catalog in concepts_and_catalogs:
            tri_concepts.append([])
            for room in catalog.rooms:
                if is_classroom_name(room):
                    class_ref = parse_classroom_name(room)
                    if class_ref.is_primary():
                        room_title = f"primary school classroom in a Gakuen Toshi: Grade {class_ref.grade} Class {class_ref.class_num}"
                        room_extra = "The classroom should be designed to be friendly and welcoming to children."
                        cache_type = "primary"
                    else:
                        room_title = f"secondary school classroom in a Gakuen Toshi: Grade {class_ref.grade} Class {class_ref.class_num}"
                        room_extra = "The classroom should be designed to be friendly while studious to accommodate the older students."
                        cache_type = "secondary"
                else:
                    class_ref = None
                    cache_type = None
                    room_title = f"**{room}** (on floor {concept.floor_title})."
                    room_extra = f"For context, here is the concept for the school:\n```\n{yamlize(school_concept)}\n```\n"
                if cache_type == "primary" and len(cached_primary_school_hardware) > 2:
                    hardware_concept = choice(cached_primary_school_hardware)
                    # print("cached primary", hardware_concept)
                elif (
                    cache_type == "secondary"
                    and len(cached_secondary_school_hardware) > 2
                ):
                    hardware_concept = choice(cached_secondary_school_hardware)
                    # print("cached secondary", hardware_concept)
                else:
                    hardware_concept = design_hardware_concept(
                        room_title,
                        room_extra,
                        guidelines,
                    )

                    if cache_type == "primary":
                        cached_primary_school_hardware.append(hardware_concept)
                    elif cache_type == "secondary":
                        cached_secondary_school_hardware.append(hardware_concept)

                if cache_type == "primary" and len(cached_primary_school_furniture) > 2:
                    furniture_concept = choice(cached_primary_school_furniture)
                    # print("cached primary", furniture_concept)
                elif (
                    cache_type == "secondary"
                    and len(cached_secondary_school_furniture) > 2
                ):
                    furniture_concept = choice(cached_secondary_school_furniture)
                    # print("cached secondary", furniture_concept)
                else:
                    furniture_concept = design_furniture_concept(
                        room_title,
                        room_extra,
                        interior_guidelines,
                    )
                    if cache_type == "primary":
                        cached_primary_school_hardware.append(hardware_concept)
                        cached_primary_school_furniture.append(furniture_concept)
                    elif cache_type == "secondary":
                        cached_secondary_school_hardware.append(hardware_concept)
                        cached_secondary_school_furniture.append(furniture_concept)

                novelist_concept = design_novelist_concept(
                    room_title, hardware_concept, furniture_concept
                )
                tri_concepts[-1].append(
                    TriConcept(
                        hardware_concept=hardware_concept,
                        furniture_concept=furniture_concept,
                        novelist_concept=novelist_concept,
                        classref=class_ref,
                    )
                )
                pbar.update(1)
    concept_packet = ConceptPacket(
        school_concept=school_concept,
        architectural_guidelines=guidelines,
        interior_guidelines=interior_guidelines,
        floor_plan=floor_plan,
        concepts_and_catalogues=concepts_and_catalogs,
        floor_rooms=tri_concepts,
    )

    with open("assets/test.pkl", "wb") as f:
        pkl.dump(concept_packet, f)
