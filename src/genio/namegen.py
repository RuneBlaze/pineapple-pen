from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from random import sample, choice
from functools import cache
import pandas as pd
import pickle as pkl


@dataclass
class NamePair:
    first_name: str
    last_name: str
    origin: str


TAG_TRANSL = {
    "Oriental": ["JP", "KR", "CN", "TW"],
    "Western": ["US", "GB"],
}


class NameGenerator:
    def __init__(self, forenames: pd.DataFrame, surnames: pd.DataFrame):
        self.forenames = forenames
        self.surnames = surnames

    def generate_name(self, gender: Literal["m", "f"], tag: str) -> NamePair:
        if possibilities := TAG_TRANSL.get(tag):
            origin = choice(possibilities)
        else:
            origin = tag

        first_name_candidates = self.forenames[
            (self.forenames.Country == origin)
            & (self.forenames.Gender == gender.upper())
        ]["Romanized Name"].tolist()

        last_name_candidates = self.surnames[self.surnames.Country == origin][
            "Romanized Name"
        ].tolist()

        return NamePair(
            first_name=choice(first_name_candidates),
            last_name=choice(last_name_candidates),
            origin=origin,
        )

    @staticmethod
    @cache
    def default() -> NameGenerator:
        forenames = pd.read_csv("assets/common-forenames-by-country.csv")
        surnames = pd.read_csv("assets/common-surnames-by-country.csv")
        forenames = forenames[
            forenames.Country.isin(["JP", "KR", "US", "CN", "TW", "GB"])
        ][["Country", "Gender", "Romanized Name"]]
        surnames = surnames[
            surnames.Country.isin(["JP", "KR", "US", "CN", "TW", "GB"])
        ][["Country", "Romanized Name"]]
        return NameGenerator(forenames, surnames)
