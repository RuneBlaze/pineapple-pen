from enum import Enum

import numpy as np
import pyxel

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH
from genio.components import CanAddAnim, HasPos
from genio.ps import Anim
from genio.scene import Scene


class WeatherType(Enum):
    BORDER_RIGHT_WIND = 1
    RAINY = 2


rng = np.random.default_rng()


class WeatherEffect:
    def __init__(
        self,
        parent: CanAddAnim,
        weather_type: WeatherType,
        frequency: float,
        anim_pool: list[str],
        randomize_energy: bool = True,
    ) -> None:
        self.parent = parent
        self.weather_type = weather_type
        self.frequency = frequency
        self.energy = 0.0
        self.anim_pool = anim_pool

    def update(self, dt: float = 1 / 30) -> None:
        self.energy += np.random.poisson(self.frequency * dt)
        while self.energy > 1 / self.frequency:
            self.energy -= 1 / self.frequency
            self.fire()

    def fire(self) -> None:
        match self.weather_type:
            case WeatherType.RAINY:
                position_xy = rng.standard_normal(2)
                position_xy *= 0.5
                position_xy += np.array([0.5, 0.5])
                position_xy[0] *= WINDOW_WIDTH
                position_xy[1] *= WINDOW_HEIGHT
                # position_xy[0] = np.clip(position_xy[0], 0, WINDOW_WIDTH)
                # position_xy[1] = np.clip(position_xy[1], 0, WINDOW_HEIGHT)
                # warp around
                position_xy[0] = position_xy[0] % WINDOW_WIDTH
                position_xy[1] = position_xy[1] % WINDOW_HEIGHT
            case WeatherType.BORDER_RIGHT_WIND:
                position_xy = np.array(
                    [
                        rng.uniform(WINDOW_WIDTH * 0.98, WINDOW_WIDTH),
                        rng.uniform(-20, WINDOW_HEIGHT * 0.7),
                    ]
                )
        chosen_anim = rng.choice(self.anim_pool)
        self.parent.add_anim(chosen_anim, *position_xy)


class WeatherTestScene:
    def __init__(self) -> None:
        self.anims = []
        self.weather = WeatherEffect(self, WeatherType.RAINY, 4, ["anims.fallen_leaf"])

    def update(self) -> None:
        self.weather.update()
        for anim in self.anims:
            anim.update()
        self.anims = [anim for anim in self.anims if not anim.dead]

    def draw(self) -> None:
        pyxel.cls(0)
        Anim.draw()

    def request_next_scene(self) -> Scene | None | str:
        return None

    def add_anim(
        self,
        anim_name: str,
        x: float,
        y: float,
        play_speed: float = 1,
        attached_to: HasPos | None = None,
    ) -> None:
        self.anims.append(Anim.from_predef(anim_name, x, y))


def gen_scene() -> WeatherTestScene:
    return WeatherTestScene()
