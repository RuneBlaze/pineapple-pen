from __future__ import annotations

import random
from random import gauss
from typing import Annotated
from typing import Literal
import yaml
from dataclasses import is_dataclass, dataclass

from .base import Mythical, generate_using_docstring
from .base import WriterArchetype, sparkle, slurp_toml
from icecream import ic
from functools import cache
import faker

fake = faker.Faker()


def to_yaml(ds: object) -> str:
    if is_dataclass(ds):
        return yaml.dump(ds.__dict__)
    return yaml.dump(ds)

@dataclass
class Backdrop:
    city_name: str
    description: str

    @staticmethod
    @cache
    def default() -> Backdrop:
        with open("assets/lore.txt") as fh:
            lore = fh.read().strip()
        return Backdrop(city_name="Auroravale", description=lore)

@dataclass
class Parent(Mythical):
    """An adult, with a life story to be written by you.

    You should write in this style:
    ```
    {writing_style}
    ```

    Remember. You are to design a life story for this person as the writer above. Some brief sketches about this person:
    ```
    {sketches}
    ```

    This person's wealth is {wealth} (from 1-10).
    This person's gender is {gender}.

    This person is married to, and is different from the following person:
    ```
    {marital}
    ```
    If you know who this person married, to, consider how they met and how their differences and similarities have shaped their lives.
    """

    name: str
    wealth: Annotated[
        int, "A number from 1 to 10, representing the wealth of the person."
    ]
    bio: Annotated[str, "A brief bio of the person in no more than four sentences."]
    job_title: str
    company: str
    hobbies: list[str]
    traits: list[str]
    flaws: list[str]
    parental_style: Annotated[str, "The parental style of the person, one sentence."]

    @staticmethod
    def generate(
        writer_archetype: WriterArchetype,
        socioeconomic_score: int,
        spouse: Parent | None = None,
        gender: Literal["male", "female"] = "female"
    ) -> Parent:
        return generate_using_docstring(
            Parent,
            {
                "writing_style": to_yaml(writer_archetype),
                "sketches": generate_expanded_life_story(socioeconomic_score),
                "marital": spouse.bio if spouse else "unknown",
                "wealth": socioeconomic_score,
                "gender": gender,
            },
        )

    @sparkle
    def affected_by_move(self, new_city: Backdrop) -> Parent:
        """Modify the person's bio. This person has moved to a new city. Add only **one or two** sentences
         to the bio to reflect the move. Be creative, always modify, without changing the person's core personality.

         Also, fix the company name to reflect the move. They might have changed jobs due to relocation."""
        ...

    def make_context(self) -> str:
        return (
            f"{self.name} is a {self.job_title} at {self.company}. "
            f"Bio: {self.bio}. "
            f"Parental style: {self.parental_style}."
            f"Traits: {self.traits}. "
            f"Flaws: {self.flaws}."
            f"Hobbies: {self.hobbies}."
        )

from dataclasses import field


@cache
def family_secrets_template() -> dict[str, list[str]]:
    struct = slurp_toml("assets/secrets.toml")
    return {
        "aspirations": list(struct["family_secret_aspirations"].values()),
        "skeletons": list(struct["family_secret_skeletons"].values()),
    }

@cache
def family_events() -> list[str]:
    struct = slurp_toml("assets/household_events.toml")
    vs = []
    # print(struct)
    for kv in struct.values():
        for v in kv.values():
            vs.append(v)
    return vs


from random import sample

@dataclass
class MemoryFragment:
    reaction: Annotated[str, "A four sentence paragraph of reactions to the event, give the situation and describe their reaction and emotional feelings."]

    def __post_init__(self):
        if isinstance(self.reaction, str):
            self.reaction = [self.reaction]
        if isinstance(self.reaction, dict):
            self.reaction = list(self.reaction.values())

@dataclass
class FamilySecret(Mythical):
    """A family secret, that has been kept for generations. Only write four to fix sentences
    as a single string, but elicit your inner mystery writer.

    The household description:
    ```
    {household}
    ```

    Their secret, in vague sketches that your job is to expand and tie together as a thorough lore:
    ```
    {sketch}
    ```
    """
    family_secret: Annotated[str, "A brief sketch of the family secret, in four to six sentences."]

    @staticmethod
    def generate(household: Household) -> FamilySecret:
        secrets = family_secrets_template()
        all_possible = secrets["aspirations"] + secrets["skeletons"]
        return generate_using_docstring(
            FamilySecret,
            {
                "household": household.short_context(),
                "sketch": ";".join(sample(all_possible, 2)),
            },
        )


@dataclass
class Household:
    main_parent: Parent
    secondary_parent: Parent
    memories: list[MemoryFragment] = field(default_factory=list)
    family_secret: FamilySecret | None = None


    @sparkle
    def react_to_event(self, event_string: str) -> MemoryFragment:
        """Household reacts to an event, and logs their collective memory.
        Write a couple of sentences (single-string) using of how
        the household reacted to the event. Also add their personal reflections.

        How did they react?
        """
        ...

    def face_random_event(self) -> None:
        ev = random.choice(family_events())
        self.memories.append(self.react_to_event(ev))

    def short_context(self) -> str:
        memories = []
        for mem in self.memories:
            memories.extend(mem.reaction)
        return (
            f"{self.main_parent.name} and {self.secondary_parent.name} live together.\n"
            f"## {self.main_parent.name}\n"
            f"{self.main_parent.name} is a {self.main_parent.job_title} at {self.main_parent.company}."
            f"{self.main_parent.bio}\n"
            f"## {self.secondary_parent.name}\n"
            f"{self.secondary_parent.name} is a {self.secondary_parent.job_title} at {self.secondary_parent.company}."
            f"{self.secondary_parent.bio}\n"
            f"## Collective memories\n"
            f"{', '.join(memories)}"
        )

    def make_context(self) -> str:
        return self.short_context()

class Student(Mythical):
    ...


def pair_of_socioeonomic_status() -> tuple[int, int]:
    n = random.randint(1, 10)
    m = n + gauss(0, 2.5)
    m = max(1, min(10, round(m)))
    return n, random.randint(1, 10)


def generate_expanded_life_story(score: int):
    # Generating a socioeconomic status score (SES) between 1 (low) to 10 (high)
    socioeconomic_status = score

    # Expanding the list of life events and experiences with even more diverse options
    life_stages = ["childhood", "adolescence", "young adulthood"]
    events_low_ses = [
        "urban exploration, street art enthusiast",
        "community library, secret poet",
        "small town hero, local entrepreneur",
        "mystery hobbyist, amateur detective",
        "backyard inventor, DIY projects",
        "local theater actor, drama club star",
        "garage band guitarist, aspiring musician",
        "young activist, community volunteer",
    ]
    events_mid_ses = [
        "suburban mystery, neighborhood adventures",
        "school science fair winner, robotics enthusiast",
        "college road trips, aspiring writer",
        "eco-warrior, nature blogger",
        "amateur astronomer, stargazing nights",
        "high school debate champion, aspiring politician",
        "art school hopeful, budding painter",
        "youth soccer star, team captain",
    ]
    events_high_ses = [
        "globetrotting family, polyglot",
        "young philanthropist, classical musician",
        "elite university, quantum computing research",
        "fashion icon, trendsetter",
        "child prodigy, early achiever",
        "international competitions, chess master",
        "youth ambassador, diplomatic travels",
        "exclusive art galleries, young collector",
    ]

    # Drawing inspiration from modern classics for a 2000-inspired setting
    modern_classic_inspirations = [
        "cyberpunk hacker, underground fame",
        "virtual reality gamer, eSports champion",
        "social media influencer, digital nomad",
        "urban gardener, sustainability advocate",
        "indie filmmaker, festival awards",
        "start-up founder, tech innovator",
        "freelance journalist, world traveler",
        "experimental musician, electronic beats",
    ]

    # Selecting events based on socioeconomic status
    if socioeconomic_status <= 3:
        selected_events = random.sample(events_low_ses + modern_classic_inspirations, 3)
    elif socioeconomic_status <= 7:
        selected_events = random.sample(events_mid_ses + modern_classic_inspirations, 3)
    else:
        selected_events = random.sample(
            events_high_ses + modern_classic_inspirations, 3
        )

    # Creating an even more expanded and creative list of life story keywords
    life_story_keywords = [
        f"{stage}: {event}" for stage, event in zip(life_stages, selected_events)
    ]

    return life_story_keywords


if __name__ == "__main__":
    writer_archetype = WriterArchetype.random()
    s1, s2 = pair_of_socioeonomic_status()
    parent = Parent.generate(writer_archetype, s1, gender="male")
    ic(parent)
    # parent = parent.affected_by_move(Backdrop.default())
    parent2 = Parent.generate(writer_archetype, s2, parent, gender="female")
    # parent2 = parent2.affected_by_move(Backdrop.default())

    household = Household(main_parent=parent, secondary_parent=parent2)
    household.face_random_event()
    ic(household)
    ic(household.memories)
    ic(household.short_context())
    secret = FamilySecret.generate(household)
    ic(secret)
