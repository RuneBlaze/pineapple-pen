from dataclasses import dataclass
from .base import slurp_toml, raw_sparkle
from functools import cache
from typing import Annotated
from .student import Student, Friendship, embellish_event, global_clock
import yaml


@dataclass
class Location:
    name: str
    description: str


@dataclass
class Klass:
    name: str
    description: str


@cache
def default_locations() -> list[Location]:
    locs = slurp_toml("assets/test_locations.toml")["locations"]
    return [Location(**i) for i in locs]


@cache
def default_klasses() -> list[Klass]:
    klasses = slurp_toml("assets/test_locations.toml")["classes"]
    return [Klass(**i) for i in klasses]


@dataclass
class DailySchedule:
    entries: Annotated[
        str,
        "A YAML list of strings, each representing a schedule entry. In the format, 'HH:MM - HH:MM; Title; Class Location'",
    ]


@raw_sparkle(demangle=True)
def design_generic_schedule(
    locations: list[Location], klasses: list[Klass]
) -> DailySchedule:
    """\
    Act as an excellent course designer. This is the Spring semester of 2002.
    You are the course designer of a Gakuen Toshi Primary School, in charge
    of designing the daily schedule of Wednesday, the 3rd of April for fourth graders.

    The school day starts at 9AM and must end by 3PM. Each period lasts 45 minutes,
    and must have at least 15 minutes between periods.
    There must be a lunch break but there can be other breaks.
    Each day must have at least 6 periods.
    These are strict rules that must be followed.

    ----

    Here are the locations in this school. Most classes take place in the classroom:

    {% for loc in locations %}
    - {loc.name}
    {% endfor %}

    ----

    Here are the potential classes in your mind, but feel free to be creative:

    {% for klass in klasses %}
    - {klass.name}
    {% endfor %}

    ----

    Now, design the schedule for the day. The setting is under a Gakuen Toshi
    light novel.

    {formatting_instructions}
    """


def remind_recurrent_memories(student: Student) -> None:
    for other, appearance in student.appearance_view.items():
        if isinstance(appearance, Friendship):
            student.etch_into_memory(
                f"{student.name} recalled the friendship with {other.name}, "
                f"and the reason they became friends. "
                f"{appearance.friendship_reason}"
            )


@dataclass
class BroadStrokesPlan:
    plans: Annotated[
        list[str],
        (
            "Plans for the day, slightly vague but allowing more detailed planning further along;"
            "in broad strokes."
        ),
    ]


class LocationTracker:
    locations: list[Location]
    student_positions: dict[Student, Location]

    def __init__(self, locations: list[Location], students: list[Student]) -> None:
        self.locations = locations
        self.student_positions = {student: locations[0] for student in students}


@raw_sparkle(demangle=True)
def plan_broad_strokes(
    student: Student, location_tracker: LocationTracker, today_schedule: DailySchedule
) -> BroadStrokesPlan:
    """\
    You are {student.profile.name}. Here is your profile:

    > {student.profile.agent_context()}. {student.memories.recall("plan")|join(', ')}.

    You are currently at {location_tracker.student_positions[student].name}.

    ----

    You looked at the calendar and the watch -- {student.clock.natural_repr()}.
    You are at {location_tracker.student_positions[student].name}.

    ----

    Today is a school day. Here is the schedule for today:

    {% for entry in today_schedule.entries %}
    - { entry }
    {% endfor %}

    Now, you have to plan your day. Please plan in broad strokes.
    Your list of plans should be slightly vague but allowing more detailed planning further along.

    {formatting_instructions}
    """


@dataclass
class DetailedPlans:
    goal: Annotated[str, "The focus of the detailed plans. A single sentence."]
    plans: Annotated[list[str], "Detailed steps to achieve the focus. Three or four steps, a YAML list."]


@raw_sparkle(demangle=True)
def plan_details(
    student: Student,
    location_tracker: LocationTracker,
    broad_stroke_plans: BroadStrokesPlan,
    focus: str,
) -> DetailedPlans:
    """\
    You are {student.profile.name}. Here is your profile:

    > {student.profile.agent_context()}. {student.memories.recall(focus)|join(', ')}.

    ----

    You looked at the calendar and the watch -- {student.clock.natural_repr()}.
    You are at {location_tracker.student_positions[student].name}.

    ----

    You are planning for the day. Here is the broad-stroke plan you made earlier:

    {% for plan in broad_stroke_plans.plans %}
    - { plan }
    {% endfor %}

    ----

    Now, focus on the plan you made earlier. As you think about it, you can make more detailed plans.

    Focus on this specific entry of your plan and expand on it:
    > {focus}

    Make detailed actionable goals of this focus. What might be your goals for this specific part of your plan?
    What might be the concrete sub-steps to achieve them? List three or four detailed actions
    that you can take to achieve the focus.

    {formatting_instructions}
    """
    ...


if __name__ == "__main__":
    locs = default_locations()
    klasses = default_klasses()
    schedule = design_generic_schedule(locs, klasses)
    with open("saves/students.yml", "r") as f:
        students = yaml.load(f, yaml.Loader)["students"]
    tracker = LocationTracker(locs, students)
    for student in students:
        remind_recurrent_memories(student)
    location_tracker = LocationTracker(locs, students)

    for student in students:
        plan = plan_broad_strokes(student, location_tracker, schedule)
        print(plan)
        for entry in schedule.entries:
            detailed = plan_details(student, location_tracker, plan, entry)
            print(detailed)
        break
