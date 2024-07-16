from __future__ import annotations

import uuid
from base64 import b32encode
from dataclasses import dataclass, field

from parse import parse


@dataclass
class Card:
    name: str = ""
    description: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_record(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }

    def to_plaintext(self) -> str:
        if self.description:
            return f"<{self.name}: {self.description}>"
        return f"<{self.name}>"

    def short_id(self) -> str:
        return b32encode(bytes.fromhex(self.id[:8])).decode().lower()[:4]

    @staticmethod
    def parse(s: str) -> Card:
        if result := parse("<{}: {}>", s):
            name, description = result.fixed
            return Card(name=name, description=description)
        if result := parse("<{}>", s):
            return Card(name=result.fixed[0], description=None)
        raise ValueError("Invalid card format")

    def duplicate(self) -> Card:
        """Copy, but with a new ID."""
        return Card(name=self.name, description=self.description)

    def __hash__(self) -> int:
        return hash(self.id)
