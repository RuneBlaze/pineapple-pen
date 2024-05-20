from typing import Protocol

from genio.core.agent import Agent


class AgentPrototype(Protocol):
    def generate(self) -> Agent:
        ...


class StudentPrototype(AgentPrototype):
    def generate(self) -> Agent:
        ...
