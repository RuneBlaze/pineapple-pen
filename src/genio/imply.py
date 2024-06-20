from __future__ import annotations

from dataclasses import dataclass

from jinja2 import Template
from parse import Parser, search


@dataclass(eq=True, frozen=True)
class Subst:
    pattern: str
    replacement: str

    condition: str | None = None

    @staticmethod
    def parse(s: str) -> Subst:
        if "if" in s:
            pattern, condition, replacement = search("{} if {} -> {};", s).fixed
            return Subst(pattern, replacement, condition)
        pattern, replacement = search("{} -> {};", s).fixed
        return Subst(pattern, replacement)

    def apply(self, s: str, extra_context: dict | None = None) -> str:
        extra_context = extra_context or {}
        # Create a parser based on the specified pattern
        parser = Parser(self.pattern)
        result = parser.parse(s)
        if not result:
            raise ValueError(f"Pattern {self.pattern} did not match the string {s}")
        context = {"m": result.fixed, **extra_context}
        if self.condition:
            if not eval(self.condition, {}, context):
                return s
        template = Template(self.replacement)
        return template.render(context)
