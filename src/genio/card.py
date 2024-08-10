from __future__ import annotations

import re
import uuid
from base64 import b32encode
from dataclasses import dataclass, field
from functools import lru_cache

from parse import parse

keywords = re.compile(
    r"\b(?:noun|verb|adjective|adverb|pronoun|preposition|conjunction|interjection|article|determiner|auxiliary verb|modal verb|particle|gerund|infinitive|participle)\b"
)


@lru_cache(16)
def judge_is_flashcard_like(card_description: str | None) -> bool:
    if not card_description:
        return False
    return re.search(keywords, card_description) is not None


@dataclass
class Card:
    name: str = ""
    description: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    card_art_name: str | None = None

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

    def is_flashcard_like(self) -> bool:
        return self.is_singleword_title() and judge_is_flashcard_like(self.description)

    def is_singleword_title(self) -> bool:
        return " " not in self.name
