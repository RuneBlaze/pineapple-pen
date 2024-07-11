import math
from enum import Enum

import pytweening
import pyxel
from pyxelxl import blt_rot

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, load_image
from genio.battle import setup_battle_bundle
from genio.card import Card
from genio.constants import CARD_HEIGHT, CARD_WIDTH
from genio.gui import CardSprite, CardState, ResolvingFraming, camera_shift
from genio.layout import layout_center_for_n
from genio.ps import Anim, HasPos
from genio.scene import Scene
from genio.tween import Instant, Mutator, Tweener


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
                    Instant(self.on_explode),
                )
            )

            self.events.append("open_pack")

    def on_explode(self) -> None:
        self.events.append("explode")

    def generate_cards(self) -> list[Card]:
        return [Card("OK", "good") for i in range(5)]


class BoosterPackScene(Scene):
    card_sprites: list[CardSprite]

    def __init__(self) -> None:
        super().__init__()

        self.framing = ResolvingFraming(self)

        self.booster_packs = []
        self.booster_packs.append(BoosterPack(10, 10, BoosterPackType.SPY_THEMED))

        self.card_sprites = []
        self.bundle = setup_battle_bundle(
            "initial_deck", "players.starter", ["enemies.evil_mask"] * 2
        )
        self.timer = 0

    def update(self):
        self.framing.update()
        for spr in self.card_sprites:
            spr.update()
        for pack in self.booster_packs:
            pack.update()
            while pack.events:
                event = pack.events.pop()
                if event == "open_pack":
                    self.framing.putup()
                elif event == "explode":
                    cards = pack.generate_cards()
                    self.show_cards(cards)
        self.timer += 1

    def draw(self):
        pyxel.cls(9)
        for pack in self.booster_packs:
            pack.draw()
        for i, spr in enumerate(self.card_sprites):
            shift = math.sin((self.timer + 103 * i) / 10) * 3
            with camera_shift(0, shift):
                spr.draw()
        self.framing.draw()
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def show_cards(self, cards: list[Card]) -> None:
        for i, card in enumerate(cards):
            target_x = layout_center_for_n(len(cards), 400)[i] - CARD_WIDTH // 2
            target_y = WINDOW_HEIGHT // 2 - CARD_HEIGHT // 2
            spr = CardSprite(i, card, self, False)
            self.card_sprites.append(spr)
            spr.x = target_x
            spr.y = target_y
            spr.tweens.clear()
            spr.state = CardState.RESOLVING

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
