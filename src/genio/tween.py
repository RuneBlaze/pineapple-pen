from __future__ import annotations

import itertools
from collections import deque
from collections.abc import Callable, Iterator

from typing_extensions import Protocol

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


class Mutator:
    def __init__(
        self,
        duration: int,
        inner: Callable[[float], float],
        this: object,
        lens: str,
        target: float,
    ) -> None:
        self.inner = Tweening(duration, inner)
        self.this = this
        self.lens = lens
        self.target = target

    def __iter__(self):
        for t in self.inner:
            setattr(
                self.this,
                self.lens,
                lerp(getattr(self.this, self.lens), self.target, t),
            )
            yield


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


class Tweener:
    def __init__(self):
        self.inner = deque()

    def _append(self, tween: Iterator):
        self.inner.append(itertools.chain(tween))

    def append(self, *tweens: Iterator):
        for tween in tweens:
            self._append(tween)

    def append_and_flush_previous(self, tween: Iterator):
        self.flush()
        self._append(tween)

    def flush(self):
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
        try:
            next(self.inner[0])
        except StopIteration:
            self.inner.popleft()
        except RuntimeError:
            self.inner.popleft()

    def keep_at_most(self, n: int):
        while len(self.inner) > n:
            self.inner.popleft()