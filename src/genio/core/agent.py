from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, TypeAlias

from genio.core.base import render_template
from genio.core.clock import Clock

KV: TypeAlias = tuple[str, Any]
SingleIntoContext: TypeAlias = str | KV
IntoContext: TypeAlias = SingleIntoContext | list[SingleIntoContext]


@dataclass
class FragmentWithPriority:
    fragment: str | KV
    priority: int
    timestamp: dt.datetime | None = None

    def to_text(self, agent: Agent) -> str:
        sentence = self.fragment
        if sentence[-1] not in [".", "!", "?"]:
            sentence += "."
        return render_template(
            sentence,
            {
                # The Agent.
                "TA": agent.name,
            },
        )


@dataclass
class Paragraph:
    sentences: list[FragmentWithPriority]

    def to_text(self, agent: Agent) -> str:
        return " ".join([x.to_text(agent) for x in self.sentences])


@dataclass
class TextFragment:
    paragraphs: list[Paragraph]

    def to_text(self, agent: Agent) -> str:
        return "\n\n".join([x.to_text(agent) for x in self.paragraphs])


@dataclass
class AgentContext:
    identity: list[FragmentWithPriority]  # Information about the agent
    agenda: list[FragmentWithPriority]  # Today's schedule
    memory: list[FragmentWithPriority]  # High-level memory
    activity: list[FragmentWithPriority]  # Recent events or logs

    @staticmethod
    def default() -> AgentContext:
        return AgentContext([], [], [], [])

    def combine(self, context: AgentContext) -> AgentContext:
        return AgentContext(
            self.identity + context.identity,
            self.agenda + context.agenda,
            self.memory + context.memory,
            self.activity + context.activity,
        )

    def __add__(self, context: AgentContext) -> AgentContext:
        return self.combine(context)

    def describe_context(self, agent: Agent) -> str:
        identity_paragraph = Paragraph(self.identity)
        agenda_paragraph = Paragraph(self.agenda)
        memory_paragraph = Paragraph(self.memory)
        activity_paragraph = Paragraph(self.activity)
        text_fragment = TextFragment(
            [identity_paragraph, agenda_paragraph, memory_paragraph, activity_paragraph]
        )
        return text_fragment.to_text(agent)


class ContextBuilder:
    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self.state = AgentContext([], [], [], [])

    def _preprocess(self, fragment: IntoContext) -> list[FragmentWithPriority]:
        if isinstance(fragment, str):
            return [FragmentWithPriority(fragment, 0)]
        elif isinstance(fragment, tuple):
            return [FragmentWithPriority(fragment, 0)]
        return [FragmentWithPriority(x, 0) for x in fragment]

    def add_identity(self, fragment: IntoContext, priority: int = 0) -> None:
        self.state.identity.extend(
            [FragmentWithPriority(x, priority) for x in self._preprocess(fragment)]
        )

    def add_identity_pair(self, key: str, value: Any, priority: int = 0) -> None:
        self.state.identity.append(FragmentWithPriority((key, value), priority))

    def add_agenda(self, fragment: IntoContext, priority: int = 0) -> None:
        self.state.agenda.extend(
            [FragmentWithPriority(x, priority) for x in self._preprocess(fragment)]
        )

    def add_agenda_pair(self, key: str, value: Any, priority: int = 0) -> None:
        self.state.agenda.append(FragmentWithPriority((key, value), priority))

    def add_memory(self, fragment: IntoContext, priority: int = 0) -> None:
        self.state.memory.extend(
            [FragmentWithPriority(x, priority) for x in self._preprocess(fragment)]
        )

    def add_memory_pair(self, key: str, value: Any, priority: int = 0) -> None:
        self.state.memory.append(FragmentWithPriority((key, value), priority))

    def add_activity(self, fragment: IntoContext, priority: int = 0) -> None:
        self.state.activity.extend(
            [FragmentWithPriority(x, priority) for x in self._preprocess(fragment)]
        )

    def add_activity_pair(self, key: str, value: Any, priority: int = 0) -> None:
        self.state.activity.append(FragmentWithPriority((key, value), priority))

    def build(self) -> AgentContext:
        return self.state



class Agent:
    components: list[ContextComponent]

    def __init__(self, global_components : Any = None) -> None:
        self.components = []
        self.global_components = global_components

    def add_component(self, component: ContextComponent | type[ContextComponent]) -> None:
        if not isinstance(component, ContextComponent):
            component = component(self)
        component.__post_init__()
        component.agent = self
        component.tick("init")
        component.tick("new_day")
        self.components.append(component)

    def context(self, re: str | None = None) -> str:
        components = sorted(self.components, key=lambda x: x.priority(), reverse=True)
        return " ".join([x.context() for x in components])

    def provided_attributes(self) -> dict[str, Any]:
        return {k: v for x in self.components for k, v in x.provides().items()}

    def attribute_set(self, key: str, value: Any) -> None:
        for component in self.components:
            component.try_set_attribute(key, value)

    def attribute_get(self, key: str) -> Any:
        for component in self.components:
            if key in (provided := component.provides()):
                return provided[key]

    def search_component(self, typ: type[ContextComponent]) -> ContextComponent | None:
        for component in self.components:
            if isinstance(component, typ):
                return component
        return None

    @property
    def name(self) -> str | None:
        return self.attribute_get("name")

    @property
    def clock(self) -> Clock | None:
        return self.attribute_get("clock")


class ContextComponent:
    agent: Agent

    def __init__(self, agent: Agent) -> None:
        self.agent = agent

    def __post_init__(self) -> None:
        ...

    def context(self, re: str | None) -> AgentContext:
        builder = ContextBuilder(self.agent)
        self.build_context(re, builder)
        return builder.build()

    def build_context(self, re: str | None, builder: ContextBuilder) -> None:
        raise NotImplementedError

    def provides(self) -> dict[str, Any]:
        return {}

    def try_set_attribute(self, key: str, value: Any) -> None:
        if key in self.provides():
            self.set_attribute(key, value)

    def set_attribute(self, key: str, value: Any) -> None:
        raise NotImplementedError
    
    @property
    def global_components(self) -> Any:
        return self.agent.global_components

    def tick(self, event: str) -> None:
        raise NotImplementedError