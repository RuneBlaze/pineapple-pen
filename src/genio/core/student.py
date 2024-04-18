from __future__ import annotations

import datetime as dt
import pickle as pkl
from collections import defaultdict
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import cache
from random import choice, gauss
from typing import Annotated, Protocol

import humanize

from genio.core.agent import MemoryBank, MemoryEntry, Thought

from ..human.height_chart import HeightChart
from ..human.namegen import NameGenerator
from .tantivy import TantivyStore
from ..utils.embed import embed_single_sentence
from .base import (
    TEMPLATE_REGISTRY,
    Agent,
    Mythical,
    WriterArchetype,
    generate_using_docstring,
    promptly,
    slurp_toml,
    yamlize,
)


class Clock:
    def __init__(self, time: dt.datetime) -> None:
        self.state = time

    def add_seconds(self, seconds: float) -> None:
        self.state += dt.timedelta(seconds=seconds)

    def add_minutes(self, minutes: float) -> None:
        self.state += dt.timedelta(minutes=minutes)

    @staticmethod
    def default() -> Clock:
        return Clock(dt.datetime(2002, 11, 6, 9))

    def natural_repr(self) -> str:
        d = humanize.naturaldate(self.state)
        t = self.state.strftime("%I:%M %p")
        return f"{d} at {t}"


global_clock = Clock.default()


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
class StudentProfile(Mythical, Agent):
    """\
    A student in a school, the hero in their life.

    This student fits under the following archetype:

    > {{archetype}}

    The student is a {{age}} year old {{height}} CM tall {{name}}.
    They are currently in grade {{grade}}. Be a light novel writer; write in this style: {{style}}.
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

def from_documents(*args, **kwargs) -> TantivyStore:
    return TantivyStore.from_documents(*args, **kwargs)


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


@dataclass
class RelationshipTag:
    relationship: str
    reason: str


class Student:
    appearance_view: dict[Student, AppearanceLike]
    memories: MemoryBank

    def __init__(self, profile: StudentProfile, max_memories: int = 8) -> None:
        self.profile = profile
        self.memories = MemoryBank(self.profile, max_memories)
        self.relationships = {}
        self.appearance_view = {}

    def inject_brief_thought(self, brief_thought: BriefThought) -> None:
        name = self.profile.name
        brief_thought = brief_thought.brief_thought
        self.memories.add_short_term_memory(f"{name} thought: {brief_thought}")

    def etch_into_memory(self, event: str) -> None:
        thoughts = embellish_event(self, event)
        if not isinstance(thoughts, list):
            thoughts = [thoughts]
        for t in thoughts:
            self.memories.memories.append(
                MemoryEntry(
                    t.thought,
                    t.significance,
                    embed_single_sentence(t.thought),
                    global_clock.state,
                )
            )

    @property
    def name(self) -> str:
        return self.profile.name

    @property
    def clock(self) -> Clock:
        return global_clock


def populate_appearances_matrix(students: list[Student]) -> None:
    n = len(students)
    for i in range(n):
        for j in range(n):
            if i != j:
                students[i].appearance_view[students[j]] = create_appearance_of(
                    students[i], students[j]
                )


def estimate_speaking_time(sentence, words_per_minute=135):
    words = len(sentence.split())
    minutes = words / words_per_minute
    seconds = minutes * 60
    return round(seconds, 2)


class AppearanceLike(Protocol):
    appearance: str


@dataclass
class AppearanceOf(AppearanceLike):
    appearance: Annotated[
        str,
        (
            "A brief description of the target person from the perspective of the observer. Write one descriptive sentence"
            "in third person: how does the target person physically look like to you? Height differences, etc."
        ),
    ]


@dataclass
class Friendship(AppearanceLike):
    appearance: Annotated[
        str,
        (
            "A brief description of the target person from the perspective of the observer. Write one descriptive sentence"
            "in third person: how does the target person physically look like to you? Height differences, etc. (Might"
            "you look at them differently now that you are friends?)"
        ),
    ]
    friendship_reason: Annotated[
        str,
        (
            "Brief memo on why the observer is friends with the target person. Write one descriptive sentence."
        ),
    ]


@dataclass
class Narrator:
    def writing_mantra(self) -> str:
        return (
            "Focus on creating vivid, imaginative scenes that captivate readers through"
            "detailed descriptions and fast-paced action. Prioritize character development"
            "and emotional depth, allowing the personalities and interactions of your characters"
            "to drive the plot and engage your audience. If you see cute moments between"
            "physical heights of the characters, write them down. Encourage cute moments."
        )


@dataclass
class NarratorAddition:
    additional_paragraph: Annotated[
        str,
        (
            "A short one or two sentence of narration to add to the logs, written in third person."
        ),
    ]


@promptly(demangle=True)
def add_narration(
    narrator: Narrator, students: list[Student], logs: list[str]
) -> NarratorAddition:
    """\
    Act as an omniscient narrator and add a short paragraph of narration to the logs.
    Write as if you are a light-novel writer adept at writing stories for a Gakuen Toshi
    setting. Write in the third person.

    Here is a profile of the scene: [The Principal's Office]. The Principal's Office is a space where tradition
    and modernity coalesce, defined by its stone flooring with geometric patterns and warm wooden
    walls adorned with intricate carvings. Recessed LED lights and traditional paper lanterns provide
    a blend of lighting, while large windows open to the natural world outside. Central to the room is
    an imposing desk, flanked by an antique globe and a framed photograph of the school's founders, creating
    an atmosphere of solemn history and quiet authority.

    Act almost like the "spirit" of the scene, and narrate like the best light novelist you can be.

    The characters in the scene are: {{students|join(', ', attribute='name')}}.
    Here is a profile of each of them:
    {% for stu in students %}
    - **{{stu.profile.name}}**: [{{stu.profile.age}}-year-old, {{stu.profile.height}} CM tall, Grade {{stu.profile.grade}}] {{stu.profile.bio}}
    {% endfor %}

    Add a short paragraph of narration to the conversation of the students. {{narrator.writing_mantra()}}

    The logs, what had transpired so far:
    > {% for log in logs %}
    {{log}}
    {% endfor %}

    Prioritize on breezy pace and describe how the students are interacting with each other
    (standing together, head-patting, etc., be light-novelly). Encourage cute moments.

    {{formatting_instructions}}
    """


class Scenario:
    logs: list[str]

    def __init__(
        self,
        students: list[Student],
        appearance_matrix: Mapping[int, Mapping[int, AppearanceOf]],
        location_description: str,
    ) -> None:
        self.students = students
        self.appearance_matrix = appearance_matrix
        self.location_description = location_description
        self.logs = []

    def elicit_thoughts(self) -> None:
        with ThreadPoolExecutor(max_workers=2) as executor:

            def deal_with_student(student: Student):
                memories = student.memories.recall("conversation")
                short_term = student.memories.short_term_memories_repr()
                return _elicit_brief_thought(
                    student.profile,
                    memories,
                    short_term,
                    self.extra_context_for_student(student),
                )

            brief_thoughts = executor.map(
                deal_with_student,
                self.students,
            )
        for student, brief_thought in zip(self.students, brief_thoughts):
            student.inject_brief_thought(brief_thought)

    def elicit_conversation(self, student: Student) -> ConversationResponse:
        memories = student.memories.recall("conversation")
        short_term = student.memories.short_term_memories_repr()
        return _elicit_conversation(
            student.profile,
            memories,
            short_term,
            self.extra_context_for_student(student),
        )

    def extra_context_for_student(self, student: Student) -> Surroundings:
        which_student = self.students.index(student)
        other_student_descriptions = [
            (self.students[i], other)
            for i, other in self.appearance_matrix[which_student].items()
        ]
        return Surroundings(
            [stu.profile for stu, app in other_student_descriptions],
            [app for stu, app in other_student_descriptions],
        )

    def conversation_loop(self, student: Student) -> None:
        cnt = 0
        while True:
            raw = self.elicit_conversation(student)
            cmd = ["say", raw.response]
            what_said = cmd[1]
            elapsed = estimate_speaking_time(what_said)
            global_clock.add_seconds(elapsed)
            log = f"{student.profile.name} said: {what_said}"
            print(log)
            self.logs.append(log)
            for stu in self.students:
                stu.memories.add_short_term_memory(
                    f"{student.profile.name} said: {what_said}"
                )
            available_students = [stu for stu in self.students if stu != student]
            student = choice(available_students)
            cnt += 1
            if cnt % 2 == 0:
                self.elicit_thoughts()
                narrator = add_narration(Narrator(), self.students, self.logs)
                print("Narrator: " + narrator.additional_paragraph)
                self.logs.append(narrator.additional_paragraph)
                for stu in self.students:
                    stu.memories.add_short_term_memory(
                        "Narrator: " + narrator.additional_paragraph
                    )


@promptly(demangle=True)
def _create_appearance_of(
    agent: StudentProfile,
    memories: list[str],
    short_term: list[str],
    target_agent_profile: str,
) -> AppearanceOf:
    """\
    You are {{agent.name}}. Here is your profile:

    > {{agent.agent_context()}}. {{'. '.join(memories)}}

    The most recent things that happened, in your **very fresh mind**, in log form:

    {% for s in short_term %}
    - {{ s }}
    {% endfor %}

    Now, you are observing the following person:

    > {{target_agent_profile}}

    How would you say this person looks like, mostly physically, from your perspective? Write a brief description of the person.

    {{formatting_instructions}}
    """
    ...


def create_appearance_of(agent: Student, target: Student) -> AppearanceOf:
    memories = agent.memories.recall(target.profile.bio)
    short_term = agent.memories.short_term_memories_repr()
    return _create_appearance_of(
        agent.profile,
        memories,
        short_term,
        target.profile.agent_context(),
    )


@dataclass
class Surroundings:
    people: list[StudentProfile]
    appearances: list[AppearanceOf]

    def people_names(self) -> list[str]:
        return [p.name for p in self.people]


TEMPLATE_REGISTRY["student_agent_thought_convo"] = """\
    You are {{_agent.name}}. Here is your profile:

    > {{_agent.agent_context()}}. {{'. '.join(_memories)}}

    You ({{_agent.name}}) are having a conversation with {{', '.join(_surroundings.people_names())}}. They are
    in the room with you. You recalled your recent impression of them, still fresh in your mind:

    {% for person, appearance in zip(_surroundings.people, _surroundings.appearances) %}
    - **{{person.name}}**: [{{person.age}}-year-old, {{person.height}} CM tall] {{appearance.appearance}}
    {% endfor %}

    ----

    Here is your recent memories of the conversation, your thoughts, what your conversation
    with {{', '.join(_surroundings.people_names())}} was like:

    {% for s in _short_term %}
    - {{ s }}
    {% endfor %}"""


@promptly
def _elicit_brief_thought(
    agent: StudentProfile,
    memories: list[str],
    short_term: list[str],
    surroundings: Surroundings,
) -> BriefThought:
    """\
    {% include "student_agent_thought_convo" %}

    What do you think in the current moment? Write down a brief thought, a reaction to the moment fitting for you,
    or a brief goal that you hope to achieve in the very near short term, in third person, a single phrase.
    Also think what happened on the subconscious level that made the person had the brief thought.

    {{formatting_instructions}}
    """
    ...


@dataclass
class ConversationResponse:
    response: Annotated[str, "What you would say in this context. (Required)"]


@promptly
def _elicit_conversation(
    agent: StudentProfile,
    memories: list[str],
    short_term: list[str],
    surroundings: Surroundings,
) -> ConversationResponse:
    """\
    {% include "student_agent_thought_convo" %}

    What would you ({{_agent.name}}) say? What would you do? Remember that your MBTI type is {{_agent.mbti_type}}
    and you are in grade {{_agent.grade}}, age {{_agent.age}}. If no conversation is happening, you can
    initiate one. If you are in the middle of a conversation, please continue it. Be engaging,
    writer your own story. Act your age and in character. Be casual and breezy.

    ----

    {{formatting_instructions}}
    """
    ...


def elicit_conversation(
    student: Student, surroundings: Surroundings
) -> ConversationResponse:
    ...


@promptly(demangle=True)
def upgrade_to_friendship(student: Student, other: Student) -> Friendship:
    """\
    You are {{student.profile.name}}. Here is your profile:

    > {{student.profile.agent_context()}}. {{student.memories.recall(other.profile.bio)|join(', ')}}.

    The most recent things that happened, in your **very fresh mind**, in log form:

    > {{student.memories.short_term_memories_repr()}}

    Now, you are thinking about the following person, and you are thinking about your friendship with them:

    > {{other.profile.agent_context()}}

    Your original thoughts about them:

    > {{student.appearance_view[other].appearance}}

    Why are you friends with them?

    ----

    How would you say this person looks like, mostly physically, from your physical perspective?
    Write a brief description of the person and your friendship with them.

    {{formatting_instructions}}
    """


@promptly(demangle=True)
def embellish_event(student: Student, event: str) -> Thought:
    """\
    You are {{student.profile.name}}. Here is your profile:

    > {{student.profile.agent_context()}}. {{student.memories.recall(event)|join(', ')}}.

    You just suddenly recalled from your memory. It popped up in your thoughts
    again:
    > {{event}}

    Help them rate the significance on a scale of 1 to 10:

    In addition, how would they rephrase this fact in their own words,
    to be etched again in their memory? Write down one direct rephrased
    thought, in third person.

    {{formatting_instructions}}
    """
    ...


def generate_student(grade: int) -> Student:
    return Student(StudentProfile.generate_from_grade(grade))


if __name__ == "__main__":
    three_students = [generate_student(4) for _ in range(3)]
    d = defaultdict(dict)
    for i in range(3):
        for j in range(3):
            if i != j:
                d[i][j] = create_appearance_of(three_students[i], three_students[j])
    # convo = Scenario(three_students, d, textwrap.dedent("""
    # As you step inside the Principal's Office, a sense of
    # reverence washes over you. Durable stone flooring, adorned with geometric
    # patterns, complements the warm wooden walls, creating an atmosphere of timeless
    # elegance. Recessed LED lighting provides a modern touch, while traditional
    # paper lanterns add a touch of cultural charm. Earthy tones and intricate
    # carvings adorn the wooden walls, while large glass windows let in natural
    # light and provide a view of the surrounding nature. An antique globe sits
    # on a shelf, whispering tales of distant lands. A framed photo of the school's
    # founders hangs above the desk, their stern expressions watching over the
    # room."""))
    # convo.elicit_thoughts()
    #
    # with open("assets/convo.pkl", "wb") as f:
    #     pkl.dump(convo, f)

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
