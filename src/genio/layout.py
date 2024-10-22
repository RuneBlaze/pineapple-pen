from __future__ import annotations

import functools
import math
from collections.abc import Sequence

import numpy as np

WINDOW_WIDTH, WINDOW_HEIGHT = 427, 240


def sin_bounce(t: float) -> float:
    if t == 1.0:
        return 0.0
    return math.sin(t * math.pi * 2)


def layout_center_for_n(n: int, width: int) -> list[int]:
    div_by = n + 1
    spacing = width // div_by
    start_x = WINDOW_WIDTH // 2 - width // 2
    return [start_x + i * spacing for i in range(1, n + 1)]


def _pingpong(n: int, double_end_points: bool = False):
    while True:
        yield 0
        if double_end_points:
            yield from [0] * 3
        for i in range(1, n - 1):
            yield i
        if double_end_points:
            yield from [n - 1] * 5
        for i in range(n - 1, 0, -1):
            yield i


def dilated(it: Sequence[int], dilation: int):
    for i in it:
        for _ in range(dilation):
            yield i


def pingpong(n: int, dilation: int = 1, double_end_points: bool = False):
    return dilated(_pingpong(n, double_end_points=double_end_points), dilation)


def lerp(
    uv: np.ndarray | tuple[float, float] | float,
    target: np.ndarray | tuple[float, float] | float,
    t: float,
) -> tuple[float, float]:
    if isinstance(uv, np.ndarray) or isinstance(target, np.ndarray):
        return uv + (target - uv) * t
    if isinstance(uv, Sequence):
        return (uv[0] + (target[0] - uv[0]) * t, uv[1] + (target[1] - uv[1]) * t)
    return uv + (target - uv) * t


@functools.cache
def calculate_fan_out_angles_symmetry(
    N: int, max_angle: int, max_difference: int
) -> list[int]:
    if N == 0:
        return []

    angles = [0] * N
    middle_index = N // 2

    # Generate angles for one side
    for i in range(1, middle_index + 1):
        target_angle = min(i * max_difference, max_angle)
        angles[middle_index - i] = -target_angle  # Left side
        angles[
            middle_index + (i - 1) + (0 if N % 2 == 0 else 0)
        ] = target_angle  # Right side

    return angles


fan_out_for_N = functools.partial(
    calculate_fan_out_angles_symmetry, max_angle=15, max_difference=1.5
)
