from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass

import pandas as pd

from .base import Mythical


@dataclass
class Parent(Mythical):
    ...


ASSET_NAME_MALE = "hfa-boys-z-who-2007-exp.xlsx"
ASSET_NAME_FEMALE = "hfa-girls-z-who-2007-exp.xlsx"

df_male = pd.read_excel(f"assets/{ASSET_NAME_MALE}")
df_female = pd.read_excel(f"assets/{ASSET_NAME_FEMALE}")


class HeightChart:
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
    def default() -> HeightChart:
        return HeightChart(
            df_male,
            df_female,
        )
