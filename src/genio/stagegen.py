from dataclasses import dataclass
from typing import Annotated

from genio.core.base import promptly


@dataclass
class BonusItems:
    """A list of objects with keys `title` and `delta`."""

    items: Annotated[
        list[dict],
        (
            "list of objects, of keys `title: string` and `delta: number`; "
            "where `title` can be things like 'Overkill', or 'Master of Poison', "
            "`delta` is the amount of bonus gold awarded, in pure numerical form."
        ),
    ]

    def to_individual_items(self) -> list["IndividualBonusItem"]:
        return [
            IndividualBonusItem(title=item["title"], delta=item["delta"])
            for item in self.items
        ]


@dataclass(frozen=True)
class IndividualBonusItem:
    title: str
    delta: float


@promptly()
def generate_bonus_items(base_money: float, battle_logs: list[str]) -> BonusItems:
    """\
    Act as an excellent GM. 
    The player has emerged victorious, and will be awarded base gold
    {{ base_money }}. However, based on what they performed in the battle,
    we can award them additional gold. Kind of like "mini achievements"
    in games that award interesting or positive behavior. For example,
    we might have something like this in some other games:

    "Overkill: +$3.00"
    "Triple Order: +$2.00"
    "Item Master: +$4.00"

    The bonus should be awarded roughly that `%15` of the base
    should be awarded for "normal" achievements, but if anything
    very interesting happens then the bonus can be higher, e.g., `+50%`.

    Your format should be roughly of the form of a list of objects.
    More smaller bonuses are preferred fewer larger bonuses.
    Consult the battle logs to judge the player's behaviors:

    {% for log in battle_logs %}
    "{{ log }}";
    {% endfor %}

    {{ formatting_instructions }}
    """


@dataclass
class GenerateSATFlashCardResult:
    """A set of precisely 5 flashcards for SAT preparation."""

    flashcards: Annotated[
        list[dict],
        (
            "A list of flashcards, objects containing two keys: 'word' and 'definition', "
            "each corresponding to the word and its definition from dictionary. Definition "
            "should be in dictionary form, like (noun) a person who is very interested in [...]"
        ),
    ]


@promptly
def generate_sat_flashcards() -> GenerateSATFlashCardResult:
    """\
    Act as an excellent tutor and a test prep professional by designing
    a set of 5 flashcards for SAT preparation, as if pulled from a dictionary.

    Write words in their entire form, and provide their definitions.
    Choose words that are no longer than 9 characters.

    {{ formatting_instructions }}
    """


@dataclass
class GenerateStageResult:
    subtitle: Annotated[
        str,
        (
            "A suitable short name for the stage, no longer than something like "
            "'Beneath the Soil' or 'Name of the Rose'. "
        ),
    ]
    lore: Annotated[
        str,
        (
            "A short twenty words of lore text, written as if by an excelllent game writer. The lore text style should be mystical, eerie, and contemplative."
        ),
    ]
    danger_level: Annotated[
        int, ("A number between 1 and 5, indicating the danger level of the stage. ")
    ]


@promptly
def generate_stage_description(
    stage_name: str, adventure_logs: list[str]
) -> GenerateStageResult:
    """\
    Act as an excellent game writer. The player will arrive at a new stage named
    '{{ stage_name }}'. Your task is to provide a fitting description of this stage,
    considering the atmosphere for their next intriguing adventure.

    First, provide a subtitle for the stage. The subtitle should be short,
    capturing your main inspiration.

    Next, write a short lore text of no more than twenty words that captures the
    essence of the stage. Your writing style should be mystical, eerie, and contemplative.

    Finally, assign a danger level to the stage, a number between 1 and 5.
    1 should indicate a beginner level stage, 3 is a somewhat challenging
    stage, and 5 is a stage that is extremely dangerous (e.g., optional level,
    for final boss). World 1 should only occasionally feature a danger level
    above 2, but otherwise the danger level should increase as the player
    progresses through the worlds.

    For your context, the player's adventure logs are as follows:

    {% for log in adventure_logs %}
    "{{ log }}";
    {% endfor %}

    {{ formatting_instructions }}
    """
