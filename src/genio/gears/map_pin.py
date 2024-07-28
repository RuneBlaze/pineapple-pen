import numpy as np
import pyxel

from genio.base import load_image
from genio.components import CanAddAnim, dithering
from genio.scene import Scene
from genio.tween import Tweener

rng = np.random.default_rng()


class MapPin:
    def __init__(self, x: int, y: int, parent: CanAddAnim) -> None:
        self.image = load_image("pin.png")
        self.x = x
        self.y = y
        self.tweener = Tweener()
        self.opacity = 0.0
        self.parent = parent

    def screen_pos(self) -> tuple[int, int]:
        return self.x, self.y

    def update(self) -> None:
        self.tweener.update()

    def draw(self) -> None:
        screen_x = self.x - 8
        screen_y = self.y - 8
        with dithering(self.opacity):
            pyxel.blt(screen_x, screen_y, self.image, 0, 0, 16, 16, 254)
            pyxel.rectb(screen_x - 1, screen_y - 1, 18, 18, 0)

    def appear(self, t: int = 30) -> None:
        self.tweener.append_mutate(self, "opacity", 1.0, t, "ease_in_out_quad")

    def move_to(self, x: int, y: int, t: int = 40) -> None:
        self.tweener.append_simple_bezier(self, (x, y), t, "ease_in_out_quad")
        self.parent.add_anim("anims.walking", self.x, self.y, attached_to=self)


class SceneMapPin(Scene):
    def __init__(self) -> None:
        super().__init__()
        self.map_pin = MapPin(100, 100)

    def update(self) -> None:
        self.map_pin.update()

        if pyxel.btnp(pyxel.KEY_SPACE):
            self.map_pin.move_to(*rng.integers(0, 230, size=2))

    def draw(self) -> None:
        pyxel.cls(1)
        self.map_pin.draw()


def gen_scene() -> Scene:
    return SceneMapPin()
