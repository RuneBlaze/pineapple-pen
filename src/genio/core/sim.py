from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import time
from queue import PriorityQueue
from typing import Any, cast

import logfire
from icecream import ic  # noqa
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_snake

from genio.concepts.geo import (
    BroadStrokesPlan,
    DailySchedule,
    DetailedPlans,
)
from genio.core.agent import Agent, ContextBuilder, ContextComponent
from genio.core.base import promptly
from genio.core.card import (
    Card,
    Effect,
    ListenToClassCard,
    TeleportEffect,
    WaitEffect,
)
from genio.core.clock import Clock
from genio.core.components import StudentProfileComponent
from genio.core.global_components import GlobalComponents
from genio.core.map import Location
from genio.core.memory import MemoryBank, create_appearance_of


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

    def __pre_attach__(self) -> None:
        self.detailed_plans = []

    def tick(self, event: str) -> None:
        if event == "new_day":
            self._build_plan()

    def _build_plan(self) -> None:
        self.broad_stroke_plans = broad_stroke_plans = plan_broad_strokes(
            self.agent, self.global_components.schedule
        )
        for entry in broad_stroke_plans.plans:
            detailed_plan = plan_details(self.agent, broad_stroke_plans, entry)
            self.detailed_plans.append(detailed_plan)

    def build_context(self, re: str | None, builder: ContextBuilder) -> None:
        builder.add_agenda("Today's plan:")
        for plan in self.broad_stroke_plans.plans:
            builder.add_agenda(plan)


class PhysicalLocation(ContextComponent):
    location: Location

    def __pre_attach__(self) -> None:
        self.location = self.global_components.map.fallback_location()

    def __post_attach__(self) -> None:
        self.location.add_occupancy(self.agent)

    def build_context(self, re: str | None, builder: ContextBuilder) -> None:
        builder.add_agenda(
            "You are currently at: "
            + self.location.name
            + " -- "
            + self.location.description
        )

    def provides(self) -> dict[str, Any]:
        return {
            "location": self.location,
        }

    def set_attribute(self, key: str, value: Any) -> None:
        match key:
            case "location":
                current_location = self.location
                self.location = value
                if current_location != value:
                    current_location.remove_occupancy(self.agent)
                    value.add_occupancy(self.agent)
            case _:
                raise ValueError(f"Unknown attribute {key}")

    def provide_cards(self) -> list[Card]:
        current_entry = self.global_components.schedule.current_entry(self.clock)
        if (
            current_entry.location == self.location
            and "classroom" in self.location.name.lower()
        ):
            return [ListenToClassCard()]
        return []

    def performed_observable(self, topic: Agent, message: str) -> None:
        self.location.broadcast("log", topic, message)


class CurrentTimeComponent(ContextComponent):
    def build_context(self, re: str | None, builder: ContextBuilder) -> None:
        builder.add_identity(
            "You look at your watch and see the time: "
            + self.global_components.clock.state.strftime("%I:%M %p")
        )


@dataclass(order=True)
class PrioritizedItem:
    priority: time
    topic: Any = field(compare=False)
    metadata: Any = field(compare=False, default=None)


class MoveAction(BaseModel):
    """Effect: Move to a specific location in the world map."""

    model_config = ConfigDict(alias_generator=to_snake)

    target: str


class Simulation:
    def __init__(
        self,
        agents: list[Agent],
    ) -> None:
        global_components = GlobalComponents.instance()
        self.global_components = global_components
        self.agents = agents
        self.queue = PriorityQueue()
        for a in self.agents:
            self.queue.put(PrioritizedItem(self.clock.state, a))

    @property
    def clock(self) -> Clock:
        return self.global_components.clock

    def turn(self) -> None:
        next_item = self.queue.get()
        self.clock.state = next_item.priority

        agent = cast(Agent, next_item.topic)
        with logfire.span("Simulation", agent_name=agent.name):
            effects = cast(Iterator[Effect] | None, next_item.metadata)

            cont: Effect | None = None
            if effects:
                try:
                    cont = next(effects)
                except StopIteration:
                    pass
            if not cont:
                logfire.info("elicit action")
                cards = agent.provide_cards()
                logfire.info("cards", cards=cards)
                possible_actions = [card.to_action(agent) for card in cards]
                action2card = {
                    action: card for action, card in zip(possible_actions, cards)
                }
                action = agent.elicit_action(possible_actions)
                effects = action2card[action.__class__].effects(agent, action)
                cont = next(effects)
            logfire.info("effect", cont=cont)
            match cont:
                case WaitEffect(duration):
                    self.queue.put(
                        PrioritizedItem(self.clock.in_minutes(duration), agent, effects)
                    )
                case TeleportEffect(target):
                    agent.attribute_set("location", target)
                    self.queue.put(
                        PrioritizedItem(self.clock.in_minutes(5), agent, effects)
                    )
                case _:
                    raise ValueError(f"Unknown effect {cont}")


class MemoryBankComponent(ContextComponent):
    memory_bank: MemoryBank

    def __post_attach__(self) -> None:
        self.met_agents = set()

    def build_context(self, re: str | None, builder: ContextBuilder) -> None:
        if not re:
            recalled = self.memory_bank.top_memories()
        else:
            recalled = self.memory_bank.recall(re)
        for entry in recalled:
            builder.add_memory(entry)

    @staticmethod
    def for_agent(agent: Agent, max_memories: int) -> MemoryBankComponent:
        component = MemoryBankComponent()
        component.memory_bank = MemoryBank(agent, max_memories)
        return component

    def log(self, topic: Agent, message: str) -> None:
        self.memory_bank.add_short_term_memory(topic.name + " " + message)

    def meet_agent(self, agent: Agent) -> None:
        if agent.identifier not in self.met_agents:
            self.met_agents.add(agent.identifier)
            self._meet_agent(agent)

    def _meet_agent(self, agent: Agent) -> None:
        appearance_of = create_appearance_of(self.agent, agent)
        self.memory_bank.append_entry(appearance_of.appearance, 5, self.agent.clock)


if __name__ == "__main__":
    b_agent = Agent.named("bigger_kid")
    b_agent.add_component(
        StudentProfileComponent,
        lambda: StudentProfileComponent.generate_from_grade(
            4, height_zscore=2, gender="female"
        ),
    )
    b_agent.add_component(
        MemoryBankComponent, lambda: MemoryBankComponent.for_agent(b_agent, 5)
    )
    # b_agent.commit_state()

    s_agent = Agent.named("smaller_kid")
    s_agent.add_component(
        StudentProfileComponent,
        lambda: StudentProfileComponent.generate_from_grade(
            4, height_zscore=-2, gender="male"
        ),
    )
    s_agent.add_component(
        MemoryBankComponent, lambda: MemoryBankComponent.for_agent(s_agent, 5)
    )
    # s_agent.commit_state()

    s_agent.b.meet_agent(b_agent)
    b_agent.b.meet_agent(s_agent)

    s_agent.commit_state()
    b_agent.commit_state()

    breakpoint()

    # sim = Simulation([agent])
    # while True:
    #     sim.turn()
