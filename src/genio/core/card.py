from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Annotated, Any, Iterator

from pydantic import BaseModel, ConfigDict, create_model, field_validator
from pydantic.alias_generators import to_snake

from genio.core.agent import Agent
from genio.core.map import Location, Map


class Effect(ABC):
    ...


@dataclass
class WaitEffect:
    duration: int


@dataclass
class TeleportEffect:
    location: Location


class ModelBuilder:
    def __init__(self) -> None:
        self.doc: str | None = None
        self.name: str | None = None
        self.fields: dict[str, tuple[type[Any], Any]] = {}

    def build(self) -> type[BaseModel]:
        if not self.name:
            raise ValueError("Model name must be provided")
        model = create_model(
            self.name, **self.fields, __config__=ConfigDict(alias_generator=to_snake)
        )
        model.__doc__ = self.doc
        return model

    def set_name(self, name: str) -> "ModelBuilder":
        self.name = name
        return self

    def set_doc(self, doc: str) -> "ModelBuilder":
        self.doc = doc
        return self

    def add_field(
        self, name: str, field_type: type[Any], annotation: Any, default: Any = ...
    ) -> "ModelBuilder":
        self.fields[name] = (Annotated[field_type, annotation], default)
        return self

    def add_int_field(
        self, name: str, annotation: str, default: int = ...
    ) -> "ModelBuilder":
        return self.add_field(name, int, annotation, default)

    def add_float_field(
        self, name: str, annotation: str, default: float = ...
    ) -> "ModelBuilder":
        return self.add_field(name, float, annotation, default)

    def add_string_field(
        self, name: str, annotation: str, default: str = ...
    ) -> "ModelBuilder":
        return self.add_field(name, str, annotation, default)


class Card(ABC):
    @abstractmethod
    def to_action(self, re: Agent) -> type[BaseModel]:
        ...

    def effects(self, caster: Agent, action: BaseModel) -> Iterator[Effect]:
        ...


class MoveAction(BaseModel):
    """Move to a specific location."""

    model_config = ConfigDict(alias_generator=to_snake)

    target: str

    @field_validator("target", mode="after")
    def validate_location(cls, v):
        world_map = Map.default()
        search_result = world_map.search(v)
        if search_result is None:
            raise ValueError(f"Location '{v}' not found in the world map")
        return v


class WaitCard(Card):
    def to_action(self, re: Agent) -> type[BaseModel]:
        builder = ModelBuilder()
        return (
            builder.set_name("WaitAction")
            .set_doc("Wait for a specified duration. The duration is in minutes.")
            .add_int_field("duration", "Duration in minutes")
            .build()
        )

    def effects(self, caster: Agent, action: BaseModel) -> Iterator[Effect]:
        yield WaitEffect(duration=action.duration)


class MoveCard(Card):
    def to_action(self, re: Agent) -> type[BaseModel]:
        return MoveAction

    def effects(self, caster: Agent, action: BaseModel) -> Iterator[Effect]:
        yield TeleportEffect(location=Map.default().search(action.target))
