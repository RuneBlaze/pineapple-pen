import weakref
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

from structlog import get_logger

logger = get_logger()


@dataclass(frozen=True)
class LLMOutboundEv:
    pass


@dataclass(frozen=True)
class LLMInboundEv:
    pass


Event: TypeAlias = LLMOutboundEv | LLMInboundEv


class EventBus:
    def __init__(self) -> None:
        self.listeners = []
        self.seen = set()
        self.replay = deque()

    def emit(self, event: Event) -> None:
        if not self.listeners:
            self.replay.append(event)
            return
        for listener in self.listeners:
            if (unwrapped := listener()) is not None:
                logger.info("EventBus.emit", listener=listener, unwrapped=unwrapped)
                unwrapped(event)

    def add_listener(
        self, m: Callable[[Event], None], idempotency_key: str | None = None
    ) -> None:
        if idempotency_key is not None:
            if idempotency_key in self.seen:
                return
            self.seen.add(idempotency_key)
        self.listeners.append(weakref.WeakMethod(m))
        if self.replay:
            for event in self.replay:
                m(event)
            self.replay.clear()


event_bus = EventBus()
