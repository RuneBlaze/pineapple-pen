from enum import Enum

import pytweening
import pyxel
from pyxelxl import blt_rot

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, load_image
from genio.card import Card
from genio.gui import ResolvingFraming
from genio.ps import Anim, HasPos
from genio.scene import Scene
from genio.tween import Mutator, Tweener


class BoosterPackType(Enum):
    SPY_THEMED = 0
    STANDARDIZED_TEST_THEMED = 1


class BoosterPackState(Enum):
    CLOSED = 0
    OPENING = 1
    OPENED = 2


class BoosterPack:
    def __init__(self, x: int, y: int, pack_type: BoosterPackType) -> None:
        self.x = x
        self.y = y
        self.pack_type = pack_type
        self.image = load_image("ui", "card-spy.png")
        self.tweener = Tweener()
        self.state = BoosterPackState.CLOSED
        self.angle = 0
        self.hovering = False

        self.events = []

    def draw(self):
        blt_rot(
            self.x,
            self.y,
            self.image,
            0,
            0,
            self.image.width,
            self.image.height,
            colkey=254,
            rot=self.angle,
        )

    def update(self):
        self.tweener.update()

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        if (
            self.x < mx < self.x + self.image.width
            and self.y < my < self.y + self.image.height
        ):
            if not self.hovering:
                self.tweener.append(
                    Mutator(5, pytweening.easeInOutBounce, self, "angle", 5)
                )
                self.tweener.append(
                    Mutator(5, pytweening.easeInOutBounce, self, "angle", -5)
                )
                self.tweener.append(
                    Mutator(5, pytweening.easeInOutBounce, self, "angle", 0)
                )
            self.hovering = True
        else:
            if self.hovering:
                self.tweener.append(Mutator(5, pytweening.easeInCirc, self, "angle", 0))
            self.hovering = False

        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.state = BoosterPackState.OPENING
            tx, ty = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
            tx, ty = tx - self.image.width // 2, ty - self.image.height // 2
            self.tweener.append(
                zip(
                    Mutator(30, pytweening.easeInCirc, self, "x", tx),
                    Mutator(30, pytweening.easeInCirc, self, "y", ty),
                )
            )

            self.events.append("open_pack")

    def generate_cards(self) -> list[Card]:
        return [Card("OK", "good") for i in range(5)]


class BoosterPackScene(Scene):
    def __init__(self) -> None:
        super().__init__()

        self.framing = ResolvingFraming(self)

        self.booster_packs = []
        self.booster_packs.append(BoosterPack(10, 10, BoosterPackType.SPY_THEMED))

    def update(self):
        self.framing.update()
        for pack in self.booster_packs:
            pack.update()
            while pack.events:
                event = pack.events.pop()
                if event == "open_pack":
                    self.framing.putup()

    def draw(self):
        pyxel.cls(9)

        for pack in self.booster_packs:
            pack.draw()
        self.framing.draw()
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def draw_crosshair(self, x, y):
        pyxel.line(x - 5, y, x + 5, y, 7)
        pyxel.line(x, y - 5, x, y + 5, 7)

    def add_anim(
        self,
        name: str,
        x: int,
        y: int,
        play_speed: float = 1.0,
        attached_to: HasPos | None = None,
    ) -> Anim:
        ...


def gen_scene() -> Scene:
    return BoosterPackScene()
