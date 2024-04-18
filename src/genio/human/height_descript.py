from dataclasses import dataclass
from typing import Annotated

from ..core.base import promptly


@dataclass
class HeightDescript:
    height_difference: Annotated[
        str,
        "Height difference in CM, a head taller? half a head taller? Two heads taller?",
    ]
    short_sentence: Annotated[
        str,
        (
            "One sentence that writes the target person in a short, descriptive way."
            "The target person is written in third person, with placeholder <PERSON>."
        ),
    ]
    more_graphic_desription: Annotated[
        str,
        (
            "A more graphic description of the target person's height relative to yours."
            "In three or four sentences, with placeholder <PERSON> and <YOU>."
        ),
    ]


@promptly
def generate_height_descript(
    your_height: int,
    person_height: int,
    person_gender: str = "male",
    target_build: str = "bulky",
) -> HeightDescript:
    """Act as an excellent light novel writer for a Gakuen Toshi story.
    Gauge how height will be described in a light novel, and generate a description.

    Your height is {{your_height}} CM, and the target person's height is {{person_height}} CM.
    Target person's gender is {{person_gender}}

    Refer to yourself as <YOU> and the target person as <PERSON> in the description. Write in the third person.

    Remember, you are a light novel writer and writing generic descriptions from
    the perspective of <YOU> looking at <PERSON> in a light novel setting. Height difference
    can be cute. Your writing will be used for templates in a light novel setting.

    {{formatting_instructions}}
    """
    ...


def generate_auxiliary(your_height: int, person_height: int) -> str:
    buf = ""

    height_difference = abs(your_height - person_height)

    if height_difference <= 5:
        buf = "In other words, you two are about the same height. "
        if your_height > person_height:
            buf += "But you are just very slightly taller, perhaps enough to notice when you're standing close."
        else:
            buf += "But you are just very slightly shorter, a subtle difference that's only apparent when you're side by side."
    elif height_difference <= 10:
        buf = "There's a noticeable difference between you two. "
        if your_height > person_height:
            buf += (
                "You're taller, enough to look down slightly when making eye contact."
            )
        else:
            buf += "You're shorter, which means you have to look up to meet their eyes."
    elif height_difference <= 20:
        buf = "The height difference is quite apparent. "
        if your_height > person_height:
            buf += (
                "Towering over them, you can easily rest your elbow on their shoulder."
            )
        else:
            buf += "You have to crane your neck upwards to see their face, feeling somewhat overshadowed."
    elif height_difference <= 30:
        buf = "The disparity in height is stark. "
        if your_height > person_height:
            buf += "You loom over them like a gentle giant, able to see the top of their head easily."
        else:
            buf += "You barely reach their chest, making you feel distinctly smaller in their towering presence."
    elif height_difference <= 40:
        buf = "The difference in height is significant, almost like a scene from a fantasy tale. "
        if your_height > person_height:
            buf += "You stand like a watchtower beside them, able to oversee their every move."
        else:
            buf += "You come up just to their shoulder, making you feel noticeably shorter in comparison."
    else:  # More than 40
        buf = "The difference in height is colossal, almost mythical. "
        if your_height > person_height:
            buf += "Standing next to them, you indeed feel like a giant, a towering figure from a legend."
        else:
            buf += "Next to them, you could almost be mistaken for a child, utterly dwarfed by their imposing stature."

    return buf


if __name__ == "__main__":
    print(generate_height_descript(150, 110, "female"))
