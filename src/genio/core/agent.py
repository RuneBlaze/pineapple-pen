from __future__ import annotations

import datetime as dt
import textwrap
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeAlias
from uuid import uuid4

from pydantic import BaseModel
from structlog import get_logger

from genio.core.agent_cache import agent_cache
from genio.core.base import render_text
from genio.core.card import Card, MoveCard, WaitCard
from genio.core.clock import Clock
from genio.core.funccall import prompt_for_structured_output

if TYPE_CHECKING:
    from genio.core.global_components import GlobalComponents

logger = get_logger()

KV: TypeAlias = tuple[str, Any]
SingleIntoContext: TypeAlias = str | KV
IntoContext: TypeAlias = SingleIntoContext | list[SingleIntoContext]


@dataclass
class FragmentWithPriority:
    fragment: str | KV
    priority: int
    timestamp: dt.datetime | None = None

    def __post_init__(self) -> None:
        if isinstance(self.fragment, FragmentWithPriority):
            raise ValueError(
                "FragmentWithPriority cannot contain another FragmentWithPriority"
            )

    def to_text(self, agent: Agent) -> str:
        sentence = self.fragment
        if isinstance(sentence, tuple):
            k, v = sentence
            sentence = f"{k}: {v}"
        if sentence[-1] not in [".", "!", "?"]:
            sentence += "."
        return render_text(
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

    def __len__(self) -> int:
        return len(self.sentences)


@dataclass
class TextFragment:
    paragraphs: list[Paragraph]

    def to_text(self, agent: Agent) -> str:
        return "\n\n".join([x.to_text(agent) for x in self.paragraphs if x])

    def __len__(self) -> int:
        return sum(len(x) for x in self.paragraphs)


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
            return [fragment]
        elif isinstance(fragment, tuple):
            return [fragment]
        elif isinstance(fragment, FragmentWithPriority):
            return [fragment]
        return [str(fragment)]

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


@dataclass
class ObservableLog:
    topic: Agent | None
    message: str


class Agent:
    components: list[ContextComponent]
    identifier: str

    def __init__(self, identifier: str | None = None) -> None:
        self.components = []
        if identifier is None:
            identifier = uuid4().hex
        self.identifier = identifier

    @staticmethod
    def named(identifier: str) -> Agent:
        if (k := identifier.encode()) in agent_cache:
            logger.debug("Agent cache hit", identifier=identifier)
            return agent_cache[k]
        return Agent(identifier)

    def add_component(
        self,
        component: type[ContextComponent],
        ctor: Callable[[], ContextComponent] | None = None,
    ) -> None:
        for c in self.components:
            if isinstance(c, component):
                logger.debug("Component already attached", component=component.__name__)
                c.__post_attach__()
                return
        component = ctor() if ctor else component()
        if not component.agent:
            component.agent = self
        component.__pre_attach__()
        component.agent = self
        component.__post_attach__()
        component.tick("init")
        component.tick("new_day")
        self.components.append(component)

    def context(self, re: str | None = None) -> str:
        components = sorted(self.components, key=lambda x: x.priority(), reverse=True)
        return " ".join([x.context().describe_context(self) for x in components])

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

    def elicit_action(self, actions: list[type[BaseModel]]) -> BaseModel:
        if not actions:
            raise ValueError("Expected at least one action to choose from; got none.")
        ctxt = self.context()
        prompt = textwrap.dedent(
            f"""\
        {ctxt}
        What would you like to do next? Please provide a valid action.
        """
        )
        return prompt_for_structured_output(prompt, actions)

    def commit_state(self) -> None:
        from genio.core.global_components import GlobalComponents

        agent_cache[self.identifier.encode()] = self
        GlobalComponents.save_instance()

    @property
    def global_components(self) -> Any:
        from genio.core.global_components import GlobalComponents

        return GlobalComponents.instance()

    def provide_cards(self) -> list[Card]:
        cards = []
        cards.extend([MoveCard(), WaitCard()])
        for component in self.components:
            cards.extend(component.provide_cards())
        if len(cards) >= 5:
            return cards[:5]
        return cards

    def log(self, topic: Agent, message: str) -> None:
        for c in self.components:
            c.log(topic, message)

    def log_myself(self, message: str) -> None:
        return self.log(self, message)

    def performed_observable(self, topic: Agent, message: str) -> None:
        ...

    def just_performed(self, message: str) -> None:
        self.performed_observable(self, message)

    def broadcast(self, method: str, *args: Any, **kwargs: Any) -> None:
        for c in self.components:
            if hasattr(c, method):
                getattr(c, method)(*args, **kwargs)
                return
        raise AttributeError(f"Method {method} not found in any component.")

    def broadcast_attr(self, attr: str) -> None:
        for c in self.components:
            if hasattr(c, attr):
                return getattr(c, attr)
        raise AttributeError(f"Attribute {attr} not found in any component.")

    def __str__(self) -> str:
        return (
            f"Agent({self.identifier}, {self.name}, {list(map(str, self.components))})"
        )

    @property
    def b(self) -> BroadcastProxy:
        return BroadcastProxy(self)


class BroadcastProxy:
    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: self._agent.broadcast(name, *args, **kwargs)

    def __getitem__(self, name: str) -> Any:
        return self._agent.broadcast_attr(name)


class ContextComponent(ABC):
    agent: Agent = None

    def __pre_attach__(self) -> None:
        pass

    def __post_attach__(self) -> None:
        pass

    def context(self, re: str | None = None) -> AgentContext:
        builder = ContextBuilder(self.agent)
        self.build_context(re, builder)
        return builder.build()

    @abstractmethod
    def build_context(self, re: str | None, builder: ContextBuilder) -> None:
        ...

    def provides(self) -> dict[str, Any]:
        return {}

    def try_set_attribute(self, key: str, value: Any) -> None:
        if key in self.provides():
            self.set_attribute(key, value)

    def set_attribute(self, key: str, value: Any) -> None:
        raise NotImplementedError

    @property
    def global_components(self) -> GlobalComponents:
        return self.agent.global_components

    @property
    def clock(self) -> Clock:
        return self.global_components.clock

    def tick(self, event: str) -> None:
        pass

    def priority(self) -> int:
        return 0

    def provide_cards(self) -> list[Card]:
        return []

    def log(self, topic: Agent, message: str) -> None:
        ...

    def performed_observable(self, topic: Agent, message: str) -> None:
        ...

    def just_performed(self, message: str) -> None:
        self.agent.just_performed(message)
