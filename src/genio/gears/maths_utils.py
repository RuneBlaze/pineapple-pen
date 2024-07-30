import math


def sin_01(t: float, dilation: float) -> float:
    return (math.sin(t * dilation) + 1) / 2
