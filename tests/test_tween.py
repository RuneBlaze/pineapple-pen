from dataclasses import dataclass

import pytweening
from genio.tween import Mutator


@dataclass
class XY:
    x: float
    y: float


def test_mutator_compound():
    thingie = XY(0, 0)
    tween = Mutator(
        30,
        pytweening.easeInBack,
        thingie,
        "x y",
        (100, 100),
    )
    for _ in tween:
        pass
    assert thingie.x == 100
    assert thingie.y == 100


def test_mutator_simple():
    thingie = XY(0, 0)
    tween = Mutator(
        30,
        pytweening.easeInBack,
        thingie,
        "x",
        100,
    )
    for _ in tween:
        pass
    assert thingie.x == 100
