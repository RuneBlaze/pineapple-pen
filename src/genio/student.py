from __future__ import annotations

from dataclasses import dataclass, is_dataclass, field
from functools import cache
from random import gauss, choice
from typing import Annotated, Literal, Protocol

from .architect import yamlize
from .namegen import NameGenerator
from .height_chart import HeightChart

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
def load_raw_archetypes():
    return slurp_toml("assets/students/normal_archetypes.toml")


@dataclass
class Archetype:
    name: str
    description: str

    @staticmethod
    def choice():
        return Archetype(**choice(load_raw_archetypes()["archetypes"]))


@dataclass
class Student(Mythical):
    """A student in a school, the hero in their life.

    This student fits under the following archetype:
    ```
    {archetype}
    ```

    The student is a {age} year old {height} CM tall {name}.
    They are currently in grade {grade}. You should write in this style: {style}.
    """

    name: str
    bio: Annotated[
        str, "A brief biography of the student, their quirks, knowledge, and skills."
    ]
    goal: Annotated[str, "The student's goal, what drives them."]
    age: Annotated[int, "A single integer."]
    mbti_type: Annotated[str, "The student's MBTI type."]
    height: Annotated[int, "The height of the student, in CM."]
    grade: int
    gender: Annotated[str, "either male | female"]

    @staticmethod
    def generate_from_grade(grade: int) -> Student:
        """Generate a random student."""
        age = age_from_grade(grade)
        namegen = NameGenerator.default()
        age_months = int(age * 12)
        gender = choice([True, False])
        lookup = HeightChart.default()
        mean, stddev = lookup.query_params(gender, age_months)
        height = gauss(0, 1) * stddev + mean
        name = namegen.generate_name("m" if gender else "f", "JP")
        return generate_using_docstring(
            Student,
            dict(
                name=f"{name.first_name} {name.last_name}",
                grade=grade,
                age=round(age),
                archetype=yamlize(Archetype.choice()),
                height=round(height),
                style=WriterArchetype.random().tone,
            ),
        )

@dataclass
class MemoryNote:
    log: str
    topic: str
    significance: int

    def __post_init__(self):
        self.significance = int(max(1, self.significance))

class AgentLike(Protocol):

    def agent_context(self) -> str:
        ...

class MemoryCell:
    agent: AgentLike
    memory_stream: list[MemoryNote]

    def insert(self, log: str) -> None:
        ...


def age_from_grade(grade: int) -> float:
    return gauss(5 + grade, 0.5)


if __name__ == "__main__":
    ic(Student.generate_from_grade(1))
