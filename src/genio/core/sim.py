from genio.concepts.geo import (
    BroadStrokesPlan,
    DailySchedule,
    DetailedPlans,
    default_klasses,
    default_locations,
    design_generic_schedule,
)
from genio.core.agent import Agent, ContextComponent
from genio.core.base import promptly
from genio.core.clock import Clock
from genio.core.map import Map
from genio.core.tantivy import global_factual_storage


class GlobalComponents:
    def __init__(self) -> None:
        self.locs = default_locations()
        self.klasses = default_klasses()
        self.factual_storage = global_factual_storage()
        for loc in self.locs:
            self.factual_storage.insert("Location: " + loc.name, loc.description)
        self.schedule = design_generic_schedule(self.locs, self.klasses)
        self.map = Map({loc.name: loc.description for loc in self.locs})


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


if __name__ == "__main__":
    global_components = GlobalComponents()
    agent = Agent(global_components)
    agent.add_component(PlanForToday)
