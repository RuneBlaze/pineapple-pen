from genio.core.agent import Agent
from genio.core.clock import Clock
from genio.core.map import Map


class Simulation:
    def __init__(self, map: Map, agents: list[Agent], clock: Clock) -> None:
        self.map = map
        self.agents = agents
        self.clock = clock
