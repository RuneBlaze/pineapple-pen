from __future__ import annotations

import random
from dataclasses import dataclass, field, is_dataclass
from functools import cache
from random import gauss, sample, choice
from typing import Annotated, Literal

import faker
import yaml
from icecream import ic

from .base import (
    Mythical,
    WriterArchetype,
    generate_using_docstring,
    slurp_toml,
    sparkle,
)
from .namegen import NameGenerator

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
    """An adult, named {name}, with a life story to be written by you.

    You should write in this style:
    ```
    {writing_style}
    ```

    Remember. You are to design a life story for this person as the writer above. Some brief sketches about this person:
    ```
    {sketches}
    ```

    This person, {name}, has wealth score of {wealth} (from 1-10).
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
        name_source: str,
        spouse: Parent | None = None,
        gender: Literal["male", "female"] = "female",
    ) -> Parent:
        name_gen = NameGenerator.default()
        name = name_gen.generate_name("m" if gender == "male" else "f", name_source)
        name_str = f"{name.first_name} {name.last_name}"
        return generate_using_docstring(
            Parent,
            {
                "writing_style": to_yaml(
                    {
                        "tone": writer_archetype.tone,
                        "register": writer_archetype.register,
                    }
                ),
                "sketches": generate_expanded_life_story(socioeconomic_score),
                "marital": spouse.bio if spouse else "unknown",
                "wealth": socioeconomic_score,
                "gender": gender,
                "name": name_str,
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


@dataclass
class MemoryFragment:
    reaction: Annotated[
        str,
        "A four sentence paragraph of reactions to the event, give the situation and describe their reaction and emotional feelings.",
    ]

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

    family_secret: Annotated[
        str, "A brief sketch of the family secret, in four to six sentences."
    ]

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
        buf = (
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
        if self.family_secret:
            buf += f"\n## Family Secret\n{self.family_secret.family_secret}"
        return buf

    def make_context(self) -> str:
        return self.short_context()


def pair_of_socioeonomic_status() -> tuple[int, int]:
    n = random.randint(1, 10)
    m = n + gauss(0, 2.5)
    m = max(1, min(10, round(m)))
    return n, random.randint(1, 10)


def madlib_event(event_template, attributes):
    # Replace placeholders in the template with random attributes
    for key, values in attributes.items():
        event_template = event_template.replace("{" + key + "}", random.choice(values))
    return event_template


def generate_expanded_life_story(score: int):
    socioeconomic_status = score

    # Define life stages
    life_stages = ["childhood", "adolescence", "young adulthood"]

    # Define events for different SES groups
    events_low_ses = [
        "urban explorer, street art enthusiast",
        "community library fan, secret poet",
        "small town hero, local entrepreneur",
        "backyard inventor, DIY project creator",
        "neighborhood sports coach, youth mentor",
        "local band member, aspiring singer",
        "community garden volunteer, plant enthusiast",
        "street performer, aspiring magician",
    ]

    events_mid_ses = [
        "suburban adventurer, neighborhood mystery solver",
        "school science fair winner, robotics club member",
        "college road trip organizer, aspiring writer",
        "amateur astronomer, stargazing hobbyist",
        "high school athlete, team captain",
        "budding artist, local gallery exhibitor",
        "young environmentalist, recycling advocate",
        "student government leader, aspiring politician",
    ]

    events_high_ses = [
        "globetrotting young traveler, polyglot in the making",
        "young philanthropist, classical music apprentice",
        "elite university attendee, quantum computing novice",
        "junior diplomat, Model United Nations participant",
        "young inventor, national science competition winner",
        "child actor, performing arts prodigy",
        "competitive chess player, international tournament participant",
        "private pilot trainee, aviation enthusiast",
    ]

    # Define attributes for MadLib-style events
    attributes = {
        "hobby": ["painting", "coding", "robotics", "music", "writing"],
        "achievement": ["won a competition", "published a paper", "recorded an album"],
        "place": ["in a small town", "in a big city", "abroad"],
    }

    # Define some event templates for MadLib-style randomization
    madlib_templates = [
        "As a {hobby} enthusiast, {achievement} {place}.",
        "Started {hobby} at a young age and {achievement} {place}.",
        "Passion for {hobby} led to {achievement} {place}.",
    ]

    # Select events based on socioeconomic status
    if socioeconomic_status <= 3:
        event_list = events_low_ses
    elif socioeconomic_status <= 7:
        event_list = events_mid_ses
    else:
        event_list = events_high_ses

    # Create life story with a mix of standard and MadLib-style events
    selected_events = []
    for _ in range(3):
        if random.random() < 0.5:  # 50% chance to select a MadLib-style event
            selected_events.append(
                madlib_event(random.choice(madlib_templates), attributes)
            )
        else:
            selected_events.append(random.choice(event_list))

    # Combine life stages with events
    life_story_keywords = [
        f"{stage}: {event}" for stage, event in zip(life_stages, selected_events)
    ]

    return life_story_keywords


CULTURE_POOL = ["JP", "CN", "US", "GB"]


@dataclass
class HouseholdSummary(Mythical):
    """A summary of parents from the perspective of the children that they will take care of,
    with a brief description of the family members and their life stories.

    You should be like a relentless journalist, be descriptive, succinct, and don't leave out information.
    Keep at most 8 bullet points while also summarizing their wealth and cultural background.

    What you should summarize as a journalist:
    ```
    {household_profile}
    ```
    """

    wealth_score: Annotated[
        int,
        "A number from 1 to 5, where 3 is middle-class, 5 is very well-off, and 1 is poor.",
    ]
    cultural_background: Annotated[
        str,
        "A single phrase, representing the cultural, racial background. Make a best guess.",
    ]
    bullet_points: Annotated[
        list[str],
        "A list of bullet points (YAML list), a succinct but descriptive bio encompassing key points of the family bio.",
    ]

    @staticmethod
    def generate(household: Household) -> HouseholdSummary:
        return generate_using_docstring(
            HouseholdSummary,
            {
                "household_profile": household.short_context(),
            },
        )


class HouseholdGenerator:
    @staticmethod
    def generate_household(cultural_origin: str | None = None) -> Household:
        if not cultural_origin:
            cultural_origin = choice(CULTURE_POOL)
        writer_archetype = WriterArchetype.random()
        s1, s2 = pair_of_socioeonomic_status()
        parent = Parent.generate(writer_archetype, s1, cultural_origin, gender="male")
        parent2 = Parent.generate(
            writer_archetype, s2, cultural_origin, parent, gender="female"
        )
        household = Household(main_parent=parent, secondary_parent=parent2)
        household.face_random_event()
        secret = FamilySecret.generate(household)
        household.family_secret = secret
        return household


if __name__ == "__main__":
    household = HouseholdGenerator.generate_household()
    ic(household)
    summary = HouseholdSummary.generate(household)
    ic(summary)
    # writer_archetype = WriterArchetype.random()
    # s1, s2 = pair_of_socioeonomic_status()
    # parent = Parent.generate(writer_archetype, s1, gender="male")
    # ic(parent)
    # # parent = parent.affected_by_move(Backdrop.default())
    # parent2 = Parent.generate(writer_archetype, s2, parent, gender="female")
    # # parent2 = parent2.affected_by_move(Backdrop.default())
    #
    # household = Household(main_parent=parent, secondary_parent=parent2)
    # household.face_random_event()
    # ic(household)
    # ic(household.memories)
    # ic(household.short_context())
    # secret = FamilySecret.generate(household)
    # ic(secret)
