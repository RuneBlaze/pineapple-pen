from __future__ import annotations

from dataclasses import dataclass

from jinja2 import Template
from parse import Parser, search


@dataclass
class Subst:
    pattern: str
    replacement: str

    @staticmethod
    def parse(s: str) -> Subst:
        pattern, replacement = search("{} -> {};", s).fixed
        return Subst(pattern, replacement)

    def apply(self, s: str) -> str:
        # Create a parser based on the specified pattern
        parser = Parser(self.pattern)
        result = parser.parse(s)

        if not result:
            raise ValueError(f"Pattern {self.pattern} did not match the string {s}")

        # Extract matched groups as a list to pass to Jinja
        # Using 'm' for matches where m[0], m[1], ..., m[n] are the matched groups
        context = {"m": result.fixed}

        # Create a template from the replacement string
        template = Template(self.replacement)

        # Render the template with the context
        return template.render(context)


if __name__ == "__main__":
    subst = Subst.parse("[foo: {:d}] -> [foo: {{m[0] + 2}}];")
    print(subst.apply("[foo: 5]"))  # Expected: [foo: 7]
