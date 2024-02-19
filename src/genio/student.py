from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from random import gauss, choice
from typing import Annotated, Literal, Protocol

from .architect import yamlize
from .namegen import NameGenerator
from .height_chart import HeightChart

from .utils import embed_single_sentence
from numpy.typing import NDArray
from sentence_transformers.util import cos_sim


from icecream import ic

from .base import (
    Mythical,
    WriterArchetype,
    generate_using_docstring,
    slurp_toml,
    sparkle,
    raw_sparkle,
)


class AgentLike(Protocol):
    def agent_context(self) -> str:
        ...

    def local_time(self) -> int:
        ...


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
class Student(Mythical, AgentLike):
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

    def agent_context(self) -> str:
        return (
            f"{self.name}, age {self.age}, grade {self.grade}, {self.height} CM tall.\n"
            f"gender: {self.gender}.\n"
            f"MBTI: {self.mbti_type}. {self.bio}\n"
        )

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


class MemoryCell:
    agent: AgentLike
    memory_stream: list[MemoryNote]

    def insert(self, log: str) -> None:
        ...


@dataclass
class Thought:
    thought: Annotated[
        str,
        (
            "The reaction of the person to the event, in third person, "
            "their thoughts, their reflections, in one to four sentences."
        ),
    ]
    significance: Annotated[
        int,
        (
            "An integer from 1 to 10. The significance of the event,"
            "where 8 or 9 are significant, e.g., getting married, a loved"
            "one dies, etc.. 5 are relatively big events, e.g., getting a"
            "new job, moving to a new city. 1 are everyday events, e.g.,"
            "eating breakfast, going to work."
        ),
    ]

    def __post_init__(self):
        if isinstance(self.significance, dict):
            self.significance = list(self.significance.keys())[0]
        self.significance = int(max(1, self.significance))
        if self.significance < 1 or self.significance > 10:
            raise ValueError("Significance must be between 1 and 10.")


@dataclass
class MemoryEntry:
    log: str
    significance: int
    embedding: NDArray[float]


@raw_sparkle
def witness_event(agent: AgentLike, related_events: list[str], event: str) -> Thought:
    """You are the following person:

    ```
    {agent}
    ```

    Some of the recent events that transpired:
    ```
    {related_events}
    ```

    Help them rate the significance of the following event, on a scale of 1 to 10:
    ```
    {event}
    ```

    In addition, how did they react? Write down one thought, reflection, given
    who they are. Step yourself in their shoes.
    **Write in the third person.**

    {formatting_instructions}
    """
    ...


@dataclass
class CompactedMemories:
    memories: Annotated[list[str], "A YAML list of strings, the compacted memories."]
    significances: Annotated[
        list[int],
        "A YAML list of integers, the significances. A parallel array to memories.",
    ]

    def __post_init__(self):
        if len(self.memories) != len(self.significances):
            raise ValueError(
                "The length of memories and significances must be the same."
            )


@raw_sparkle
def compact_memories(agent: AgentLike, memories: list[str]) -> CompactedMemories:
    """You are the following person:

    ```
    {agent}
    ```

    Here are the things that this person (you) remember:

    **The memories**:
    ```
    {memories}
    ```

    Help them think about some high-level thoughts about these memories,
    and reflect on how these memories have impacted, influenced, and
    shaped them. What would they think about their own experiences of those memories?
    **Write in the third person.**

    Write down a couple of new thoughts about the memories,
    along with their significance, on a scale of 1 to 10, where 2, 3
    are mundane everyday thoughts, 5, 6 are relatively big thoughts such as
    thinking about a promotion, and 8, 9 are life-changing thoughts such as
    thinking about a loved one who has passed away.

    {formatting_instructions}
    """


class MemoryBank:
    def __init__(self, agent: AgentLike, max_memories: int = 30) -> None:
        self.agent = agent
        self.max_memories = max_memories
        self.memories = []

    def witness_event(self, log: str) -> None:
        related_events = self.recall(log, max_recall=5)
        thoughts = witness_event(self.agent, related_events, log)
        if not isinstance(thoughts, list):
            thoughts = [thoughts]
        for t in thoughts:
            self.memories.append(
                MemoryEntry(
                    t.thought,
                    t.significance,
                    embed_single_sentence(t.thought),
                )
            )
        if len(self.memories) > self.max_memories:
            self.run_compaction()

    def run_compaction(self) -> None:
        memories = [x.log for x in self.memories]
        compacted = compact_memories(self.agent, memories)
        for log, significance in zip(compacted.memories, compacted.significances):
            self.memories.append(
                MemoryEntry(log, significance, embed_single_sentence(log))
            )
        ic(self.memories)
        self.memories = sorted(
            self.memories, key=lambda x: x.significance, reverse=True
        )[: self.max_memories]

    def recall(self, topic: str, max_recall: int = 5) -> list[str]:
        topic_embedding = embed_single_sentence(topic)
        similarities = []
        for memory in self.memories:
            similarities.append((memory, cos_sim(topic_embedding, memory.embedding)))
        similarities = sorted(
            similarities,
            key=lambda x: x[1] * x[0].significance ** 0.5,
            reverse=True,
        )
        return [x[0].log for x in similarities[:max_recall]]


@dataclass
class World:
    elapsed_minutes: int = 0


def age_from_grade(grade: int) -> float:
    return gauss(5 + grade, 0.5)


if __name__ == "__main__":
    student = Student.generate_from_grade(1)
    memories = MemoryBank(student, 5)
    for i in range(3):
        memories.witness_event("A cat died.")
        memories.witness_event("They found a new cat.")
