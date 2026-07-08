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
    prefix: str | None = None
    prefix_min_length: int = 0
    prefix_max_length: int = 0
    prefix_length: int | None = None
    prefix_typed: str = ""
    prefix_pending: bool = False
    energy_cost: int | None = None
    temporary_original_name: str | None = None
    temporary_original_description: str | None = None
    temporary_original_card_art_name: str | None = None

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
        return Card(
            name=self.name,
            description=self.description,
            card_art_name=self.card_art_name,
            prefix=self.prefix,
            prefix_min_length=self.prefix_min_length,
            prefix_max_length=self.prefix_max_length,
            prefix_length=self.prefix_length,
            prefix_typed=self.prefix_typed,
            prefix_pending=self.prefix_pending,
            energy_cost=self.energy_cost,
        )

    def begin_temporary_transform(
        self,
        name: str,
        description: str | None,
        card_art_name: str | None = None,
    ) -> None:
        if self.temporary_original_name is None:
            self.temporary_original_name = self.name
            self.temporary_original_description = self.description
            self.temporary_original_card_art_name = self.card_art_name
        self.name = name
        self.description = description
        self.card_art_name = card_art_name

    def revert_temporary_transform(self) -> None:
        if self.temporary_original_name is None:
            return
        self.name = self.temporary_original_name
        self.description = self.temporary_original_description
        self.card_art_name = self.temporary_original_card_art_name
        self.temporary_original_name = None
        self.temporary_original_description = None
        self.temporary_original_card_art_name = None

    def has_temporary_transform(self) -> bool:
        return self.temporary_original_name is not None

    def is_prefix_card(self) -> bool:
        return self.prefix is not None

    def prefix_suffix_length(self) -> int:
        if not self.is_prefix_card() or self.prefix_length is None:
            return 0
        return max(self.prefix_length - len(self.prefix or ""), 0)

    def is_prefix_filled(self) -> bool:
        return (
            self.is_prefix_card()
            and len(self.prefix_typed) == self.prefix_suffix_length()
        )

    def is_playable_prefix_state(self) -> bool:
        return not self.is_prefix_card() or (
            self.is_prefix_filled()
            and bool(self.description)
            and not self.prefix_pending
            and "_" not in self.name
        )

    def prepare_prefix_draw(self, length: int) -> None:
        if not self.is_prefix_card():
            return
        prefix = self.prefix or ""
        self.prefix_length = max(length, len(prefix))
        self.prefix_typed = ""
        self.prefix_pending = False
        self.description = None
        self.name = prefix + "_" * self.prefix_suffix_length()

    def set_prefix_suffix(self, suffix: str) -> None:
        if not self.is_prefix_card():
            return
        suffix = "".join(ch for ch in suffix if ch.isalpha()).lower()
        self.prefix_typed = suffix[: self.prefix_suffix_length()]
        remaining = self.prefix_suffix_length() - len(self.prefix_typed)
        self.name = f"{self.prefix}{self.prefix_typed}{'_' * remaining}"
        self.description = None
        self.prefix_pending = False

    def append_prefix_letter(self, letter: str) -> None:
        if len(letter) != 1 or not letter.isalpha():
            return
        self.set_prefix_suffix(self.prefix_typed + letter)

    def pop_prefix_letter(self) -> None:
        self.set_prefix_suffix(self.prefix_typed[:-1])

    def reset_prefix_entry(self) -> None:
        self.set_prefix_suffix("")

    def confirm_prefix_entry(self) -> None:
        if not self.is_prefix_filled():
            return
        word = f"{self.prefix}{self.prefix_typed}"
        self.name = word[:1].upper() + word[1:].lower()
        self.description = None
        self.prefix_pending = True

    def finish_prefix_description(self, description: str) -> None:
        if not self.is_prefix_card():
            return
        self.description = description
        self.prefix_pending = False

    def __hash__(self) -> int:
        return hash(self.id)

    def is_flashcard_like(self) -> bool:
        return self.is_singleword_title() and judge_is_flashcard_like(self.description)

    def is_singleword_title(self) -> bool:
        return " " not in self.name
