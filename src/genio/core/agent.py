"""
Generative agents.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Annotated

import humanize
from numpy.typing import NDArray
from sentence_transformers.util import cos_sim

from genio.base import OUTPUT_FORMAT, jinja_global, promptly
from genio.prelude.tantivy import TantivyStore, global_factual_storage
from genio.student import global_clock
from genio.utils import embed_single_sentence


class Agent:
    components: list[ContextComponent]
    def __init__(self):
        self.components = []

    def add_component(self, component: ContextComponent) -> None:
        self.components.append(component)
        component.agent = self

    def context(self) -> str:
        components = sorted(self.components, key=lambda x: x.priority(), reverse=True)
        return " ".join([x.context() for x in components])


class ContextComponent:
    agent: Agent

    def __init__(self, agent: Agent) -> None:
        self.agent = agent

    def context(self) -> str:
        raise NotImplementedError
    
    def priority(self) -> int:
        return 0


@dataclass
class MemoryEntry:
    log: str
    significance: int
    embedding: NDArray

    timestamp: dt.datetime


@dataclass
class ShortTermMemoryEntry:
    log: str
    timestamp: dt.datetime


def humanize_time_delta(delta: dt.timedelta) -> str:
    if delta.seconds <= 10:
        return "just now"
    return humanize.naturaltime(delta) + " ago"


class MemoryBank(ContextComponent):
    def __init__(self, agent: Agent, max_memories: int = 30) -> None:
        super().__init__(agent)
        self.max_memories = max_memories
        self.memories = []

        self.factual_store = TantivyStore(global_factual_storage())
        self.short_term_memories = []
        self.short_term_memories_watermark = global_clock.state

    def add_short_term_memory(self, log: str) -> None:
        self.short_term_memories.append(ShortTermMemoryEntry(log, global_clock.state))

    def catch_up_short_term_memories(self) -> None:
        # TODO: implement this.
        self.short_term_memories_watermark = len(self.short_term_memories)

    def short_term_memories_repr(self) -> list[str]:
        to_concat = [
            (humanize_time_delta(global_clock.state - x.timestamp), x.log)
            for x in self.short_term_memories
        ]
        return [f"({x[0]}) {x[1]}" for x in to_concat]

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
                    global_clock.state,
                )
            )
        if len(self.memories) > self.max_memories:
            self.run_compaction()

    def run_compaction(self) -> None:
        memories = [x.log for x in self.memories]
        compacted = compact_memories(self.agent, memories)
        for log, significance in zip(compacted.memories, compacted.significances):
            self.memories.append(
                MemoryEntry(
                    log, significance, embed_single_sentence(log), global_clock.state
                )
            )
        self.memories = sorted(
            self.memories, key=lambda x: x.significance, reverse=True
        )[: self.max_memories]

    def recall(self, topic: str, max_recall: int = 3) -> list[str]:
        semantic_results = self.recall_semantic(topic, max_recall)
        factual_results = self.factual_store.recall(topic, 1)
        if factual_results:
            factual_results = [factual_results[0].to_context()]
        return semantic_results + factual_results

    def recall_semantic(self, topic: str, max_recall: int = 5) -> list[str]:
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
class CompactedMemories:
    memories: Annotated[
        list[str], f"A {OUTPUT_FORMAT} list of strings, the compacted memories."
    ]
    significances: Annotated[
        list[int],
        f"A {OUTPUT_FORMAT} list of integers, the significances. A parallel array to memories.",
    ]

    def __post_init__(self):
        if len(self.memories) != len(self.significances):
            raise ValueError(
                "The length of memories and significances must be the same."
            )


@jinja_global
def listof(coll: list[str]) -> str:
    return "\n".join('- ' + x for x in coll)


@promptly
def compact_memories(agent: Agent, memories: list[str]) -> CompactedMemories:
    """\
    Act as the following person:
    > {{ agent.core_context() }}

    For context, some relevant things that this person (you) remember:
    {{ listof(memories) }}

    Help them think about some high-level thoughts about these memories,
    and reflect on how these memories have impacted, influenced, and
    shaped them. What would they think about their own experiences of those memories?
    **Write in the third person.**

    Write down a couple of new thoughts about the memories,
    along with their significance, on a scale of 1 to 10, where 2, 3
    are mundane everyday thoughts, 5, 6 are relatively big thoughts such as
    thinking about a promotion, and 8, 9 are life-changing thoughts such as
    thinking about a loved one who has passed away.

    {{ formatting_instructions }}
    """


@promptly
def witness_event(agent: Agent, event: str) -> Thought:
    """\
    You are the following person:
    > {{agent.context()}}

    Help them rate the significance of the following event, on a scale of 1 to 10:
    > {{ event }}

    In addition, how did they react? Write down one thought, reflection, given
    who they are. Step yourself in their shoes.
    **Write in the third person.**

    {{formatting_instructions}}
    """
    ...


@dataclass
class Thought:
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
    thought: Annotated[
        str,
        (
            "The reaction of the person to the event, in third person, "
            "their thoughts, their reflections, in one to four sentences."
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
