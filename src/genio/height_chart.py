from __future__ import annotations
import pandas as pd
from bisect import bisect_left
import pickle as pkl
from dataclasses import dataclass
from functools import cache
from random import gauss
import random
import tomllib

from .base import Mythical

@dataclass
class Parent(Mythical):
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
        "young activist, community volunteer"
    ]
    events_mid_ses = [
        "suburban mystery, neighborhood adventures",
        "school science fair winner, robotics enthusiast",
        "college road trips, aspiring writer",
        "eco-warrior, nature blogger",
        "amateur astronomer, stargazing nights",
        "high school debate champion, aspiring politician",
        "art school hopeful, budding painter",
        "youth soccer star, team captain"
    ]
    events_high_ses = [
        "globetrotting family, polyglot",
        "young philanthropist, classical musician",
        "elite university, quantum computing research",
        "fashion icon, trendsetter",
        "child prodigy, early achiever",
        "international competitions, chess master",
        "youth ambassador, diplomatic travels",
        "exclusive art galleries, young collector"
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
        "experimental musician, electronic beats"
    ]

    # Selecting events based on socioeconomic status
    if socioeconomic_status <= 3:
        selected_events = random.sample(events_low_ses + modern_classic_inspirations, 3)
    elif socioeconomic_status <= 7:
        selected_events = random.sample(events_mid_ses + modern_classic_inspirations, 3)
    else:
        selected_events = random.sample(events_high_ses + modern_classic_inspirations, 3)

    # Creating an even more expanded and creative list of life story keywords
    life_story_keywords = [f"{stage}: {event}" for stage, event in zip(life_stages, selected_events)]

    return life_story_keywords


@dataclass
class WriterArchetype:
    name: str
    tone: str
    register: str
    genres: list[str]

    @staticmethod
    def random() -> WriterArchetype:
        return random.choice(load_writer_archetypes())


@cache
def load_writer_archetypes() -> list[WriterArchetype]:
    with open("assets/archetypes.toml", "r") as f:
        parsed_data = tomllib.load(f)
    return [WriterArchetype(**archetype) for archetype in parsed_data["writer"]]


ASSET_NAME_MALE = "hfa-boys-z-who-2007-exp.xlsx"
ASSET_NAME_FEMALE = "hfa-girls-z-who-2007-exp.xlsx"

df_male = pd.read_excel(f"assets/{ASSET_NAME_MALE}")
df_female = pd.read_excel(f"assets/{ASSET_NAME_FEMALE}")


class HeightLookup:
    months: list[int]
    male_median: list[float]
    female_median: list[float]
    male_stddev: list[float]
    female_stddev: list[float]

    def __init__(self, df_male, df_female) -> None:
        self.df_male = df_male
        self.df_female = df_female

        self.months = self.df_male["Month"].tolist()
        self.male_median = self.df_male["M"].tolist()
        self.female_median = self.df_female["M"].tolist()
        self.male_stddev = self.df_male["StDev"].tolist()
        self.female_stddev = self.df_female["StDev"].tolist()

    def query_params(self, is_male: bool, months: float) -> tuple[float, float]:
        index = bisect_left(self.months, months)
        index = max(0, index - 1)
        if is_male:
            return self.male_median[index], self.male_stddev[index]
        else:
            return self.female_median[index], self.female_stddev[index]

    @staticmethod
    def default() -> "HeightLookup":
        with open("assets/height_lookup.pkl", "rb") as f:
            return pkl.load(f)


lookup = HeightLookup.default()
print(lookup.query_params(False, 12 * 12))
