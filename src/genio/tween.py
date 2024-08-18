from __future__ import annotations

import itertools
from collections import deque
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

import numpy as np
import pytweening
from typing_extensions import Protocol

from genio.bezier import QuadBezier
from genio.layout import (
    lerp,
    sin_bounce,
)


class Tweening:
    def __init__(self, duration: int, inner: Callable[[float], float]):
        self.duration = duration
        self.inner = inner
        self.timer = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.timer += 1
        if self.timer > self.duration:
            raise StopIteration
        return self.inner(self.timer / self.duration)


class HasXY(Protocol):
    x: int
    y: int


class MutableTweening:
    def __init__(
        self,
        duration: int,
        inner: Callable[[float], float],
        this: HasXY,
        target: tuple[int, int],
    ):
        self.inner = Tweening(duration, inner)
        self.this = this
        self.current = (this.x, this.y)
        self.target = target

    def __iter__(self):
        for t in self.inner:
            self.this.x, self.this.y = lerp(self.current, self.target, t)
            yield


class BezierTweening:
    bezier: QuadBezier

    def __init__(
        self,
        duration: int,
        inner: Callable[[float], float],
        bezier: tuple[tuple[int, int], tuple[int, int], tuple[int, int]],
        this: HasXY,
    ):
        self.inner = Tweening(duration, inner)
        self.this = this
        self.bezier = QuadBezier.from_tuples(bezier)
        self.current = (this.x, this.y)

    def __iter__(self):
        for t in self.inner:
            self.this.x, self.this.y = self.bezier.evaluate(t)
            yield


class Mutator:
    lens: ImperativeLens

    def __init__(
        self,
        duration: int,
        inner: Callable[[float], float],
        this: object,
        lens: str,
        target: float | tuple[float, ...] | Callable[[], float | tuple[float, ...]],
    ) -> None:
        self.inner = Tweening(duration, inner)
        self.this = this
        self.lens = parse_lens(lens)
        self.target = target
        self.initial_value = self.lens.getter(self.this)

    def actual_target(self) -> float | tuple[float, ...]:
        if isinstance(self.target, tuple):
            return self.target
        elif isinstance(self.target, int | float):
            return self.target
        elif isinstance(self.target, np.int64 | np.float64 | np.ndarray):
            return self.target
        else:
            return self.target()

    def __iter__(self):
        for t in self.inner:
            self.lens.setter(
                self.this,
                lerp(self.initial_value, self.actual_target(), t),
            )
            yield


PredefinedTween: TypeAlias = Literal[
    "linear",
    "ease_in_quad",
    "ease_out_quad",
    "ease_in_out_quad",
    "ease_in_cubic",
    "ease_out_cubic",
    "ease_in_out_cubic",
    "ease_in_quart",
    "ease_out_quart",
    "ease_in_out_quart",
    "ease_in_circ",
    "ease_out_circ",
    "ease_in_out_circ",
    "ease_in_expo",
    "ease_out_expo",
    "ease_in_out_expo",
]


def wrap_tween(
    tween: Callable[[float], float],
) -> Callable[[float | tuple[float, ...]], float | tuple[float, ...]]:
    def inner(t: float | tuple[float, ...]) -> float | tuple[float, ...]:
        if isinstance(t, tuple):
            return tuple(tween(x) for x in t)
        return tween(t)

    return inner


PREDEFINED_TWEENS: Mapping[PredefinedTween, Callable[[float], float]] = {
    "linear": pytweening.linear,
    "ease_in_quad": pytweening.easeInQuad,
    "ease_out_quad": pytweening.easeOutQuad,
    "ease_in_out_quad": pytweening.easeInOutQuad,
    "ease_in_cubic": pytweening.easeInCubic,
    "ease_out_cubic": pytweening.easeOutCubic,
    "ease_in_out_cubic": pytweening.easeInOutCubic,
    "ease_in_quart": pytweening.easeInQuart,
    "ease_out_quart": pytweening.easeOutQuart,
    "ease_in_out_quart": pytweening.easeInOutQuart,
    "ease_in_circ": pytweening.easeInCirc,
    "ease_out_circ": pytweening.easeOutCirc,
    "ease_in_out_circ": pytweening.easeInOutCirc,
    "ease_in_expo": pytweening.easeInExpo,
    "ease_out_expo": pytweening.easeOutExpo,
    "ease_in_out_expo": pytweening.easeInOutExpo,
}


class WaitUntilTweening:
    def __init__(self, callable: Callable[[], bool]):
        self.callable = callable

    def __iter__(self):
        while not self.callable():
            yield


class Instant:
    def __init__(self, runnable: Callable):
        self.runnable = runnable

    def __iter__(self):
        yield
        self.runnable()
        return


class Shake:
    def __init__(self, this, duration: int, magnitude: int):
        self.this = this
        self.magnitude = magnitude
        self.inner = Tweening(duration, sin_bounce)

    def __iter__(self):
        for t in self.inner:
            self.this.rotation = self.magnitude * t
            yield


class ImperativeLens(Protocol):
    def getter(self, parent: Any) -> Any:
        ...

    def setter(self, parent: Any, value: Any) -> None:
        ...


def nested_getattr(obj: Any, attr: str) -> Any:
    for a in attr.split("."):
        obj = getattr(obj, a)
    return obj


def nested_setattr(obj: Any, attr: str, value: Any) -> None:
    attrs = attr.split(".")
    for a in attrs[:-1]:
        obj = getattr(obj, a)
    setattr(obj, attrs[-1], value)


@dataclass
class AttributeLens:
    attribute: str

    def getter(self, parent: Any) -> Any:
        return nested_getattr(parent, self.attribute)

    def setter(self, parent: Any, value: Any) -> None:
        nested_setattr(parent, self.attribute, value)


@dataclass
class ProductLens:
    lenses: tuple[ImperativeLens]

    def __post_init__(self):
        self.lenses = tuple(self.lenses)

    def getter(self, parent: Any) -> tuple:
        return tuple(lens.getter(parent) for lens in self.lenses)

    def setter(self, parent: Any, value: tuple) -> None:
        for lens, v in zip(self.lenses, value):
            lens.setter(parent, v)


def parse_lens(lens: str) -> ImperativeLens:
    if " " in lens:
        return ProductLens(tuple(map(parse_lens, lens.split(" "))))
    return AttributeLens(lens)


class Tweener:
    """A scheduler for tweening animations."""

    variable_play_speed: bool

    def __init__(self, variable_play_speed: bool = False, parent: Any = None):
        self.inner = deque()
        self.variable_play_speed = variable_play_speed
        self.parent = parent
        if self.parent is None:
            self.tracks = [Tweener(variable_play_speed, self) for _ in range(4)]

    def track(self, n: int) -> Tweener:
        return self.tracks[n]

    def _append(self, tween: Iterator):
        self.inner.append(itertools.chain(tween))

    def append(self, *tweens: Iterator):
        for tween in tweens:
            self._append(tween)

    def append_mutate(
        self,
        subject: Any,
        lens: str,
        duration: int,
        target_value: float,
        tween_type: PredefinedTween,
    ):
        self._append(
            Mutator(
                duration, PREDEFINED_TWEENS[tween_type], subject, lens, target_value
            )
        )

    def append_mutate_xy(
        self,
        subject: HasXY,
        duration: int,
        target: tuple[int, int],
        tween_type: PredefinedTween,
    ):
        self._append(
            MutableTweening(duration, PREDEFINED_TWEENS[tween_type], subject, target)
        )

    def append_bezier(
        self,
        subject: HasXY,
        duration: int,
        bezier: tuple[tuple[int, int], tuple[int, int], tuple[int, int]],
        tween_type: PredefinedTween,
    ):
        self._append(
            BezierTweening(duration, PREDEFINED_TWEENS[tween_type], bezier, subject)
        )

    def append_simple_bezier(
        self,
        subject: HasXY,
        target: tuple[int, int],
        duration: int,
        tween_type: PredefinedTween,
        sign: bool = True,
    ):
        p0 = np.array([subject.x, subject.y])
        p1 = np.array(target)
        midpoint = (p0 + p1) / 2
        n = np.linalg.norm(p1 - midpoint)
        if np.isclose(n, 0):
            dir = np.array([0, 0])
        else:
            dir = (p1 - midpoint) / n
            dir = np.array([-dir[1], dir[0]])
        mult = 1 if sign else -1
        c = midpoint + np.linalg.norm(p1 - p0) * mult * 0.3 * dir
        self.append_bezier(
            subject, duration, (tuple(p0), tuple(c), tuple(p1)), tween_type
        )

    def append_and_flush_previous(self, tween: Iterator):
        self.flush()
        self._append(tween)

    def flush(self):
        """Clear all tweens, effectively fast-forwarding them to the end."""

        while self.inner:
            try:
                next(self.inner[0])
            except StopIteration:
                self.inner.popleft()
            except RuntimeError:
                self.inner.popleft()

    def update(self):
        if not self.inner:
            return
        play_speed = (2 ** (len(self.inner) - 2)) if self.variable_play_speed else 1
        play_speed = min(play_speed, 4)
        play_speed = max(play_speed, 1)
        try:
            for _ in range(play_speed):
                next(self.inner[0])
        except StopIteration:
            self.inner.popleft()
        except RuntimeError:
            self.inner.popleft()

    def keep_at_most(self, n: int):
        while len(self.inner) > n:
            self.inner.popleft()

    def __len__(self):
        return len(self.inner)

    def clear(self):
        self.inner.clear()
