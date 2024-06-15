from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from genio.core.base import slurp_toml

predef = slurp_toml("assets/strings.toml")


@dataclass
class ResolvedResults:
    """A completed sentence in the game. An occurrence, a line, of the game's narrative."""

    reason: Annotated[
        str,
        "Justification for the completion. How the *action* connects the concepts serially.",
    ]
    results: Annotated[
        str,
        (
            "The results of the actions taken by both the player and the enemies, and the consequences of those actions. "
            "The nuemrical deltas should be given in square brackets like [Slime: receive 5 damage]. "
        ),
    ]


# @promptly
# def _judge_results(
#     cards: list[Card],
#     user: PlayerBattler,
#     enemies: list[EnemyBattler],
#     battle_context: str,
# ) -> ResolvedResults:
#     """\
#     {% include('judge.md') %}

#     {{ formatting_instructions }}

#     Let's think step by step.
#     """
#     ...


# if __name__ == "__main__":
#     deck = create_deck(predef["initial_deck"]["cards"])

#     slash = [c for c in deck if c.name.lower() == "slash"][0]
#     left = [c for c in deck if c.name.lower() == "left"][0]
#     right = [c for c in deck if c.name.lower() == "right"][0]
#     repeat = [c for c in deck if c.name.lower() == "repeat all previous"][0]

#     default_battle_context = []
#     default_battle_context.append(
#         "It's a brightly lit cave, with torches lining the walls."
#     )
#     # default_battle_context.append("")
#     # default_battle_context.append("Enemies' intents:")
#     enemies = [EnemyBattler.from_predef("enemies.slime", i + 1) for i in range(2)]
#     # for e in enemies:
#     #     default_battle_context.append(f"{e.name}: {e.profile.pattern[0]}")
#     # default_battle_context.append("The list of enemies on the battlefield:")
#     # default_battle_context.append("")
#     # for e in enemies:
#     #     default_battle_context.append(f"{e.name} ({e.profile.description})")

#     # default_battle_context.append("[FILL IN]")

#     # print(default_battle_context)

#     # starter_enemy = PlayerProfile.from_predef("enemies.starter")
#     starter_player = PlayerProfile.from_predef("players.starter")
#     built_context = "\n".join(default_battle_context)
#     # print(built_context)

#     completed = _judge_results(
#         cards=[slash, left, right, repeat, left, right],
#         user=PlayerBattler.from_profile(starter_player),
#         enemies=enemies,
#         battle_context=built_context,
#     )

#     # print(completed)
