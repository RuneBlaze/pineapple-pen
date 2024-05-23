from __future__ import annotations

import datetime as dt

import humanize


class Clock:
    def __init__(self, time: dt.datetime) -> None:
        self.state = time

    def add_seconds(self, seconds: float) -> None:
        self.state += dt.timedelta(seconds=seconds)

    def add_minutes(self, minutes: float) -> None:
        self.state += dt.timedelta(minutes=minutes)

    def in_minutes(self, minutes: float) -> dt.datetime:
        return self.state + dt.timedelta(minutes=minutes)

    @staticmethod
    def default() -> Clock:
        return Clock(dt.datetime(2002, 11, 6, 9))

    def natural_repr(self) -> str:
        d = humanize.naturaldate(self.state)
        t = self.state.strftime("%I:%M %p")
        return f"{d} at {t}"


global_clock = Clock.default()
