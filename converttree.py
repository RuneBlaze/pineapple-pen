# Licensed under UNLICENSE.

# This contains code to convert a traditional "recursive-struct" tree to the autograder format. "Pseudocode-like" Python, for education purposes only.

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    name: str  # name
    children: list[Node] = field(default_factory=list)  # pointers to children

    def is_terminal(self) -> bool:
        return not self.children

    def is_non_terminal(self) -> bool:
        return not self.is_terminal()


"""

      S
    /    \
   x     S
         |
         a
"""

example_tree = Node("S", [Node("x"), Node("S", [Node("a")])])


def convert_tree_to_string(node: Node) -> str:
    if node.is_terminal():
        return node.name
    else:  # non-terminal
        buf = ""
        buf += "("
        buf += node.name  # e.g. S
        buf += " "
        for child in node.children:
            buf += convert_tree_to_string(child)
            buf += " "
        buf = buf[:-1]  # extra space remove
        buf += ")"
        return buf


print(convert_tree_to_string(example_tree))
