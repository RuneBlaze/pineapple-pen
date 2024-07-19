from typing import TypeAlias

import numpy as np

Vec2Int: TypeAlias = np.ndarray
Vec2: TypeAlias = np.ndarray


def vec2int(x: int, y: int) -> Vec2Int:
    return np.array([x, y], dtype=np.int32)


def vec2(x: float, y: float) -> Vec2:
    return np.array([x, y], dtype=np.float32)
