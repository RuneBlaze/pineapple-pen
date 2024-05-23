from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from queue import PriorityQueue
from typing import Any, ClassVar, cast

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_snake

from genio.concepts.geo import (
    BroadStrokesPlan,
    DailySchedule,
    DetailedPlans,
    default_klasses,
    default_locations,
    design_generic_schedule,
)
from genio.core.agent import Agent, ContextBuilder, ContextComponent
from genio.core.base import promptly
from genio.core.clock import Clock
from genio.core.components import StudentProfileComponent
from genio.core.map import Location, Map
from genio.core.tantivy import global_factual_storage


class GlobalComponents:
    _instance: ClassVar[GlobalComponents] = None

    def __init__(self) -> None:
        self.locs = default_locations()
        self.klasses = default_klasses()
        self.factual_storage = global_factual_storage()
        for loc in self.locs:
            self.factual_storage.insert("Location: " + loc.name, loc.description)
        self.schedule = design_generic_schedule(self.locs, self.klasses)
        self.map = Map.default()

    @staticmethod
    def instance() -> GlobalComponents:
        if not GlobalComponents._instance:
            GlobalComponents._instance = GlobalComponents()
        return GlobalComponents._instance


@promptly()
def plan_broad_strokes(agent: Agent, today_schedule: DailySchedule) -> BroadStrokesPlan:
    """\
    {{agent.context()}}

    ----

    Today is a school day. Here is the class schedule for the day.

    {% for entry in today_schedule.entries %}
    - {{ entry }}
    {% endfor %}

    > Note: usually there is homework and other activities after school, so plan accordingly.

    Now, plan your day in a **personal way** incorporating the class schedule,
    but do include personal notes. One must always get up in the morning,
    start the day, and one usually have plans after class and how to end their day.

    Please plan in broad strokes.
    Your list of plans should be slightly vague but allowing more detailed planning further along.

    Now, plan from 8AM to 8PM, incorporating the class schedule.

    {{formatting_instructions}}
    """


@promptly()
def plan_details(
    agent: Agent,
    broad_stroke_plans: BroadStrokesPlan,
    focus: str,
) -> DetailedPlans:
    """\
    {{agent.context(focus)}}

    ----

    You are planning for the day. Here is the broad-stroke plan you made earlier:

    {% for plan in broad_stroke_plans.plans %}
    - {{ plan }}
    {% endfor %}

    ----

    Now, focus on the plan you made earlier. As you think about it, you can make more detailed plans.

    Focus on this specific entry of your plan and expand on it:
    > {{focus}}

    Make detailed actionable goals of this focus. What might be your goals for this specific part of your plan?
    What might be the concrete sub-steps to achieve them? List three or four detailed actions
    that you can take to achieve the focus.

    {{formatting_instructions}}
    """
    ...


class PlanForToday(ContextComponent):
    broad_stroke_plans: BroadStrokesPlan
    detailed_plans: list[DetailedPlans]

    def __post_attach__(self) -> None:
        self.detailed_plans = []

    def tick(self, event: str) -> None:
        if event == "new_day":
            self._build_plan()

    def _build_plan(self) -> None:
        plan = plan_broad_strokes(self.agent, self.global_components.schedule)
        self.broad_stroke_plans = plan
        for entry in plan.plans:
            detailed_plan = plan_details(self.agent, plan, entry)
            self.detailed_plans.append(detailed_plan)


class PhysicalLocation(ContextComponent):
    location: Location

    def __post_attach__(self) -> None:
        self.location = self.global_components.map.fallback_location()

    def build_context(self, re: str | None, builder: ContextBuilder) -> None:
        builder.add_agenda("You are currently at: " + self.location.name)


@dataclass(order=True)
class PrioritizedItem:
    priority: time
    topic: Any = field(compare=False)
    metadata: Any = field(compare=False)


class MoveAction(BaseModel):
    """Effect: Move to a specific location in the world map."""

    model_config = ConfigDict(alias_generator=to_snake)

    target: str


class Simulation:
    def __init__(
        self,
        agents: list[Agent],
        clock: Clock,
        global_components: GlobalComponents | None = None,
    ) -> None:
        global_components = global_components or GlobalComponents()
        self.global_components = global_components
        self.agents = agents
        for agent in agents:
            agent.global_components = global_components
        self.clock = clock
        self.queue = PriorityQueue()
        for a in self.agents:
            self.queue.put(PrioritizedItem(self.clock.time, a))

    def turn(self) -> None:
        next_item = self.queue.get()
        self.clock.state = next_item.priority

        agent = cast(Agent, next_item.topic)
        action = agent.elicit_action([MoveAction])

        match action:
            case MoveAction(target=target):
                result = self.global_components.map.search(target)
                agent.location = self.global_components.map[result.title]
                self.queue.put(PrioritizedItem(self.clock.time, agent, result))
            case _:
                pass


if __name__ == "__main__":
    agent = Agent.named("test_agent_1")
    agent.add_component(
        StudentProfileComponent, lambda: StudentProfileComponent.generate_from_grade(4)
    )
    agent.add_component(PhysicalLocation)
    agent.commit_state()
    print(agent.context())
