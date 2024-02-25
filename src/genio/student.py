from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from random import gauss, choice, random
from typing import Annotated

from .namegen import NameGenerator
from .height_chart import HeightChart

from .utils import embed_single_sentence
from numpy.typing import NDArray
from sentence_transformers.util import cos_sim
from .base import cmd_sparkle, levenshtein_distance
import pickle as pkl

from .base import (
    Mythical,
    WriterArchetype,
    generate_using_docstring,
    slurp_toml,
    raw_sparkle,
    AgentLike,
    yamlize,
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
class StudentProfile(Mythical, AgentLike):
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
    long_term_goal: Annotated[str, "The student's goal, their intrinsic motivation."]
    age: Annotated[int, "A single integer."]
    mbti_type: Annotated[str, "The student's MBTI type."]
    height: Annotated[int, "The height of the student, in CM."]
    grade: int
    gender: Annotated[str, "either male | female"]

    def __post_init__(self):
        if isinstance(self.age, str):
            self.age = int(self.age)
        if isinstance(self.height, str):
            self.height = self.height.lower()
            if "cm" in self.height:
                self.height = self.height.replace("cm", "").strip()
            self.height = int(self.height)
        if isinstance(self.grade, str):
            self.grade = int(self.grade)

    def agent_context(self) -> str:
        return (
            f"{self.name}, age {self.age}, grade {self.grade}, {self.height} CM tall.\n"
            f"gender: {self.gender}.\n"
            f"MBTI: {self.mbti_type}. {self.bio}\n"
        )

    @staticmethod
    def generate_from_grade(grade: int) -> StudentProfile:
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
            StudentProfile,
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
        if isinstance(self.significance, str):
            self.significance = int(self.significance)
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
        self.short_term_memories = []
        self.short_term_memories_watermark = 0

    def add_short_term_memory(self, log: str) -> None:
        self.short_term_memories.append(log)

    def catch_up_short_term_memories(self) -> None:
        self.short_term_memories_watermark = len(self.short_term_memories)

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

    def __str__(self):
        return f"MemoryBank for {self.agent} with {len(self.memories)} memories."

    def __repr__(self):
        return super().__repr__()


@dataclass
class World:
    elapsed_minutes: int = 0


def age_from_grade(grade: int) -> float:
    return gauss(5 + grade, 0.5)


@dataclass
class BriefThought:
    subconscious_thought: Annotated[
        str,
        (
            "What happened on the subconscious level that made the person had the brief thought,"
            "in third person, no more than two sentences."
        ),
    ]

    brief_thought: Annotated[
        str,
        (
            "A brief thought, a reaction to the event, in third person, "
            "a single phrase."
        ),
    ]


class Student:
    def __init__(self, profile: StudentProfile, max_memories: int = 8) -> None:
        self.profile = profile
        self.memories = MemoryBank(self.profile, max_memories)

    def inject_brief_thought(self, brief_thought: BriefThought) -> None:
        name = self.profile.name
        brief_thought = brief_thought.brief_thought
        self.memories.add_short_term_memory(f"{name} thought: {brief_thought}")

    def __str__(self) -> str:
        return


@dataclass
class AppearanceOf:
    appearance: Annotated[
        str,
        (
            "A brief description of the target person from the perspective of the observer. Write one descriptive sentence"
            "in third person: how does the target person look like to you?"
        ),
    ]


from collections.abc import Mapping


class Convo:
    def __init__(
        self,
        students: list[Student],
        appearance_matrix: Mapping[int, Mapping[int, AppearanceOf]],
        location_description: str,
    ) -> None:
        self.students = students
        self.appearance_matrix = appearance_matrix
        self.location_description = location_description

    def start_round(self) -> None:
        for student in self.students:
            brief_thought = elicit_brief_thought(
                student, self.extra_context_for_student(student)
            )
            student.inject_brief_thought(brief_thought)

    def elicit_conversation(self, student: Student) -> list[str]:
        return elicit_conversation(student, self.extra_context_for_student(student))

    def extra_context_for_student(self, student: Student) -> str:
        which_student = self.students.index(student)
        other_student_descriptions = [
            other.appearance for other in self.appearance_matrix[which_student].values()
        ]
        return (
            "You are in the middle of a conversation with some others. "
            "## Context:\n"
            f"{self.location_description}\n"
            f"## The others in the conversation:\n"
            f"{yamlize(other_student_descriptions)}"
        )

    def conversation_loop(self, student: Student) -> None:
        cnt = 0
        while True:
            cmd = self.elicit_conversation(student)
            if cmd[0] == "sayto":
                what_said = cmd.pop()
                cmd.pop(0)
                who_said = " ".join(cmd)
                closest_match = None
                closest_distance = float("inf")
                for i, other in enumerate(self.students):
                    distance = levenshtein_distance(who_said, other.profile.name)
                    if distance < closest_distance:
                        closest_distance = distance
                        closest_match = other
                log = f"{student.profile.name} said to {closest_match.profile.name}: {what_said}"
                print(log)
                for stu in self.students:
                    stu.memories.add_short_term_memory(log)
                if random() < 0.5:
                    student = closest_match
                else:
                    available_students = [
                        stu for stu in self.students if stu != student
                    ]
                    student = choice(available_students)
            elif cmd[0] == "say":
                what_said = cmd[1]
                log = f"{student.profile.name} said: {what_said}"
                print(log)
                for stu in self.students:
                    stu.memories.add_short_term_memory(
                        f"{student.profile.name} said: {what_said}"
                    )
                available_students = [stu for stu in self.students if stu != student]
                student = choice(available_students)

            else:
                raise ValueError(f"Unknown command: {cmd}")
            cnt += 1
            if cnt % 2 == 0:
                self.start_round()


@raw_sparkle
def _create_appearance_of(
    agent: str, memories: list[str], short_term: list[str], target_agent_profile: str
) -> AppearanceOf:
    """
    You are the following person:

    ```
    {agent}
    ```

    Here are the things that this person (you) remember:
    ```
    {memories}
    ```

    The most recent things that happened, in your **very fresh mind**, in log form:
    ```
    {short_term}
    ```

    Now, you are observing the following person:

    ```
    {target_agent_profile}
    ```

    How would you say this person looks like, mostly physically, from your perspective? Write a brief description of the person.

    {formatting_instructions}
    """
    ...


def create_appearance_of(agent: Student, target: Student) -> AppearanceOf:
    memories = agent.memories.recall(target.profile.bio)
    short_term = agent.memories.short_term_memories
    return _create_appearance_of(
        agent.profile.agent_context(),
        memories,
        short_term,
        target.profile.agent_context(),
    )


@raw_sparkle
def _elicit_brief_thought(
    agent: str, memories: list[str], short_term: list[str], extra_context: str
) -> BriefThought:
    """
    {extra_context}

    You are the following person:

    ```
    {agent}
    ```

    Here are the things that this person (you) remember:
    ```
    {memories}
    ```

    The most recent things that happened, in your **very fresh mind**, in log form:
    ```
    {short_term}
    ```

    What do you think in the current moment? Write down a brief thought, a reaction to the moment fitting for you,
    in third person, a single phrase. Also think what happened on the subconscious level that made the person had the brief thought.

    {formatting_instructions}
    """
    ...


def elicit_brief_thought(student: Student, extra_observation: str) -> BriefThought:
    memories = student.memories.recall("conversation")
    short_term = student.memories.short_term_memories
    return _elicit_brief_thought(
        student.profile.agent_context(), memories, short_term, extra_observation
    )


@cmd_sparkle(["sayto", "say"])
def _elicit_conversation(
    agent: str, memories: list[str], short_term: list[str], extra_context: str
) -> list[str]:
    """

    You are the following person:

    ```
    {agent}
    ```

    Here are the things that this person (you) remember:
    ```
    {memories}
    ```

    Here are some context:
    {extra_context}

    The most recent things that happened, in your **very fresh mind**, in log form, including the conversation:
    ```
    {short_term}
    ```

    How would you contribute something new to the conversation? Act almost as a novelist
    trying to create an interesting conversation in a novel, and act as the person you are to push
    the conversation to that direction.

    Return your call on one of two Python functions, in ``python`` code blocks.

    1. `sayto(target_person: str, what_to_say: str) -> None` - Say something to a specific person.
    2. `say(what_to_say: str) -> None` - Say something to everyone/anyone in the conversation.

    Either give Python code directly, or surround your function call with triple backticks.
    Remember to always quote the strings, especially when referring to the target person.
    """
    ...


def elicit_conversation(student: Student, extra_observation: str) -> list[str]:
    memories = student.memories.recall("conversation")
    short_term = student.memories.short_term_memories
    return _elicit_conversation(
        student.profile.agent_context(), memories, short_term, extra_observation
    )


def generate_student(grade: int) -> Student:
    return Student(StudentProfile.generate_from_grade(grade))


if __name__ == "__main__":
    # three_students = [generate_student(4) for _ in range(3)]
    # d = defaultdict(dict)
    # for i in range(3):
    #     for j in range(3):
    #         if i != j:
    #             d[i][j] = create_appearance_of(three_students[i], three_students[j])
    #
    # convo = Convo(three_students, d, """As you step inside the Principal's Office, a sense of
    #       reverence washes over you. Durable stone flooring, adorned with geometric
    #       patterns, complements the warm wooden walls, creating an atmosphere of timeless
    #       elegance. Recessed LED lighting provides a modern touch, while traditional
    #       paper lanterns add a touch of cultural charm. Earthy tones and intricate
    #       carvings adorn the wooden walls, while large glass windows let in natural
    #       light and provide a view of the surrounding nature. An antique globe sits
    #       on a shelf, whispering tales of distant lands. A framed photo of the school's
    #       founders hangs above the desk, their stern expressions watching over the
    #       room.""")
    # convo.start_round()

    with open("assets/convo.pkl", "rb") as f:
        convo = pkl.load(f)
    first_student = choice(convo.students)
    convo.conversation_loop(first_student)
    #
    # convo = convo.elicit_conversation(first_student)

    # breakpoint()

    # breakpoint()
    # ic(elicit_brief_thought(three_students[0], "The student is looking at a cat."))
    # ic(elicit_brief_thought(three_students[1], "The student is looking at a cat."))
    # ic(elicit_brief_thought(three_students[2], "The student is looking at a cat."))
    # memories = MemoryBank(student, 5)
    # for i in range(3):
    #     memories.witness_event("A cat died.")
    #     memories.witness_event("They found a new cat.")
    # ic(memories)
