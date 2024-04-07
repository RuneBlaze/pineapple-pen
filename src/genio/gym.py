"""
Environment to prototype agents.
"""

from __future__ import annotations

import json
from collections import deque
from copy import copy
from dataclasses import dataclass, field
from datetime import time
from queue import PriorityQueue
from typing import Any


@dataclass(order=True)
class PrioritizedItem:
    priority: time
    topic: Any = field(compare=False)
    metadata: Any = field(compare=False)


@dataclass
class ScheduleEntry:
    start_time: time
    end_time: time | None
    topic: str
    location: str
    document: Any | None

    @staticmethod
    def parse(text: str) -> "ScheduleEntry":
        # Splitting the text into parts
        time_part, topic, location = text.split("; ")

        start_str, end_str = time_part.split("-")
        start_str = start_str.strip()
        end_str = end_str.strip()
        start_hour, start_minute = map(int, start_str.split(":"))
        end_hour, end_minute = map(int, end_str.split(":"))

        return ScheduleEntry(
            start_time=time(start_hour, start_minute),
            end_time=time(end_hour, end_minute),
            topic=topic,
            location=location,
            document=None,
        )


# @dataclass
class ScheduleZipper:
    past: deque[ScheduleEntry]
    pending: deque[ScheduleEntry]

    def __init__(self, schedule: list[ScheduleEntry]) -> None:
        self.past = deque()
        self.pending = deque(schedule)

    def tick(self, t: time) -> None:
        while self.pending and self.pending[0].end_time <= t:
            self.past.append(self.pending.popleft())

    def make_context(self, t: time) -> str:
        context = ""

        # Current Activity
        if self.pending and self.pending[0].start_time <= t <= self.pending[0].end_time:
            context += f"You are currently engaged in: {self.pending[0].topic}.\n"
        else:
            context += "You currently have free time.\n"

        # Next Activity (Detailed)
        if self.pending:
            entry = self.pending[0]
            context += "\n**Next Activity:**\n"
            context += f"* Task: {entry.topic}\n"
            context += f"* Time: {entry.start_time.strftime('%I:%M %p')} - {entry.end_time.strftime('%I:%M %p')}\n"
            context += f"* Location: {entry.location}\n"
            if entry.document:
                context += f"* Reference: {entry.document}\n"

        # Upcoming Schedule (Summary)
        context += "\n**Upcoming Schedule:**\n"
        for i in range(1, min(len(self.pending), 10)):
            entry = self.pending[i]
            context += f"- {entry.start_time.strftime('%I:%M %p')}: {entry.topic} ({entry.location})\n"

        return context


SCHEDULE_KNIGHT = [
    "05:30 - 06:30; Dawn Training; Guardian's Keep",
    "07:00 - 07:30; Breakfast at Inn; The Crimson Tavern",
    "08:00 - 09:00; Patrol Duty; Dragon's Bridge",
    "09:30 - 10:30; Meeting with Local Leaders; Frostvale Village",
    "11:00 - 12:00; Strategic Planning; Guardian's Keep",
    "12:30 - 13:00; Quick Lunch; Frostvale Village",
    "13:30 - 14:30; Exploration of The Crystal Caverns; The Crystal Caverns",
    "15:00 - 16:00; Training Session; Guardian's Keep",
    "16:30 - 17:30; Meeting with Blacksmith; Emberfall Forge",
    "18:00 - 19:00; Dinner and Discussions; The Crimson Tavern",
    "19:30 - 20:30; Night Patrol; Frostvale Village",
    "21:00 - 22:00; Debriefing and Planning; Guardian's Keep",
]

SCHEDULE_MAIL_PERSON = [
    "06:00 - 06:30; Morning Prep; Small Residence",
    "06:30 - 07:00; Breakfast at Inn; The Crimson Tavern",
    "07:30 - 09:00; Mail Collection and Sorting; Frostvale Village",
    "09:30 - 10:30; Passage through Whispering Woods; Whispering Woods",
    "11:00 - 12:00; Message Delivery; The Sunken Cathedral",
    "12:30 - 13:30; Lunch Break; Frostvale Village",
    "14:00 - 15:00; Visit to Emberfall Forge; Emberfall Forge",
    "15:30 - 16:30; Trade at The Shrouded Bazaar; The Shrouded Bazaar",
    "17:00 - 18:00; Deliver Letters to Eclipse Tower; Eclipse Tower",
    "18:30 - 19:30; Dinner and Networking; The Crimson Tavern",
    "20:00 - 21:00; Final Mail Deliveries; Frostvale Village",
    "21:30 - 22:00; Nightly Reflection; Whispering Woods",
]


class Clock:
    now: time

    def __init__(self, t: time) -> None:
        self.now = t


class ChronoAgent:
    def __init__(
        self,
        name: str,
        description: str,
        loc: Location,
        schedule: list[str],
        clock: Clock,
    ) -> None:
        self.name = name
        self.description = description
        self.location = loc
        self.schedule = ScheduleZipper(ScheduleEntry.parse(entry) for entry in schedule)
        self.clock = clock

    def step(self) -> None:
        self.schedule.tick(self.clock.now)

    def make_context(self) -> str:
        prompt = f"You are {self.name}, {self.description}. Currently, you find yourself in {self.location.name}, a place known for {self.location.description}.\n\n"

        prompt += "Looking at your schedule, it seems:\n"
        prompt += self.schedule.make_context(self.clock.now)

        return prompt


# @dataclass
# class GoToAction:
#     location: str

# @dataclass
# class AwaitAction:
#     minutes: int

# def parse_actions(possible_actions: )


@dataclass
class Location:
    name: str
    description: str


class WorldMap:
    def __init__(self) -> None:
        self.locations = []

    @staticmethod
    def default() -> WorldMap:
        with open("assets/demo/places.json") as f:
            locations = json.load(f)
        instance = WorldMap()
        instance.locations = [Location(**loc) for loc in locations]
        return instance

    def __len__(self) -> int:
        return len(self.locations)


class SimulationState:
    def __init__(self) -> None:
        self.clock = time(6, 30)
        self.knight = ChronoAgent("Knight", SCHEDULE_KNIGHT)
        self.mail_person = ChronoAgent("Mail Person", SCHEDULE_MAIL_PERSON)

        self.pq = PriorityQueue()
        self.pq.put(PrioritizedItem(copy(self.clock), self.knight, None))
        self.pq.put(PrioritizedItem(copy(self.clock), self.mail_person, None))

    def step(self) -> None:
        next_item = self.pq.get()
        self.clock = next_item.priority
        agent = next_item.topic
        agent.step(self.clock)


if __name__ == "__main__":
    simulation = SimulationState()
    simulation.step()
