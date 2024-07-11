import itertools
import math
from collections import defaultdict
from enum import Enum
from functools import cache

import numpy as np
import pytweening
import pyxel
from pyxelxl import blt_rot

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, load_image
from genio.battle import setup_battle_bundle
from genio.card import Card
from genio.components import blt_burning
from genio.constants import CARD_HEIGHT, CARD_WIDTH
from genio.gui import (
    CardArtSet,
    CardSprite,
    CardState,
    ResolvingFraming,
    camera_shift,
)
from genio.layout import layout_center_for_n
from genio.ps import Anim, HasPos
from genio.scene import Scene
from genio.semantic_search import search_closest_document
from genio.tween import Instant, Mutator, Tweener


class BoosterPackType(Enum):
    SPY_THEMED = 0
    STANDARDIZED_TEST_THEMED = 1


class BoosterPackState(Enum):
    CLOSED = 0
    OPENING = 1
    OPENED = 2


@cache
def perlin_noise(width: int, height: int, scale: float, replica: int = 0) -> np.ndarray:
    res = np.zeros((height, width), dtype=np.float32)
    for j in range(height):
        for i in range(width):
            res[j, i] = pyxel.noise(i * scale, j * scale, replica)
    # normalize it
    res -= res.min()
    res /= res.max()
    res = np.clip(res, 0, 1)
    return res


class BoosterCardSpriteState(Enum):
    APPEARING = 0
    ACTIVE = 1
    CHOSEN = 2
    DISAPPEARING = 3
    DEAD = 4


class BoosterCardSprite:
    def __init__(self, x: int, y: int, ix: int, card: Card) -> None:
        base_image = pyxel.Image(43, 60)
        base_image.blt(0, 0, 0, 0, 0, 43, 60, colkey=0)
        self.card_art = CardArtSet(base_image, search_closest_document(card.name))

        self.x = x
        self.y = y
        self.image = self.card_art.imprint(card.name, 0)
        self.ix = ix

        self.state_timers = defaultdict(int)

        self.state = BoosterCardSpriteState.APPEARING
        self.tweens = Tweener()

        self.tweens.append(
            itertools.chain(
                range(31),
                Instant(lambda: self.set_state(BoosterCardSpriteState.ACTIVE)),
            )
        )

    def draw(self):
        match self.state:
            case BoosterCardSpriteState.APPEARING | BoosterCardSpriteState.DISAPPEARING as state:
                in_or_out = "in" if state == BoosterCardSpriteState.APPEARING else "out"
                blt_burning(
                    self.x,
                    self.y,
                    self.image,
                    perlin_noise(self.image.width, self.image.height, 0.1, self.ix),
                    # np.full((self.image.height, self.image.width), 0.5),
                    self.state_timers[self.state],
                    in_or_out,
                )
            case BoosterCardSpriteState.ACTIVE | BoosterCardSpriteState.CHOSEN:
                shift = math.sin((self.state_timers[self.state] + 103 * self.ix) / 10) * 3
                with camera_shift(0, shift):
                    blt_rot(
                        self.x,
                        self.y,
                        self.image,
                        0,
                        0,
                        self.image.width,
                        self.image.height,
                        colkey=254,
                    )

    def set_state(self, state: BoosterCardSpriteState) -> None:
        if self.state == state:
            return
        self.transition_out_state(self.state)
        self.state = state
        self.transition_in_state(self.state)

    def transition_out_state(self, state: BoosterCardSpriteState) -> None:
        ...

    def transition_in_state(self, state: BoosterCardSpriteState) -> None:
        ...

    def update(self):
        self.state_timers[self.state] += 1
        self.tweens.update()


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
        self.noise = perlin_noise(self.image.width, self.image.height, 0.1)
        self.events = []
        self.timer = 0
        self.state_timers = defaultdict(int)

    def screen_pos(self) -> tuple[float, float]:
        return self.x + self.image.width // 2, self.y + self.image.height // 2

    def draw(self):
        match self.state:
            case BoosterPackState.CLOSED | BoosterPackState.OPENING:
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
            case BoosterPackState.OPENED:
                blt_burning(
                    self.x,
                    self.y,
                    self.image,
                    self.noise,
                    self.state_timers[self.state],
                    "out",
                )

    def update(self):
        self.tweener.update()
        self.timer += 1
        self.state_timers[self.state] += 1

        if self.state == BoosterPackState.CLOSED:
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
                    self.tweener.append(
                        Mutator(5, pytweening.easeInCirc, self, "angle", 0)
                    )
                self.hovering = False

        if (
            pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
            and self.state == BoosterPackState.CLOSED
        ):
            self.state = BoosterPackState.OPENING
            tx, ty = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
            tx, ty = tx - self.image.width // 2, ty - self.image.height // 2
            self.tweener.append(
                itertools.zip_longest(
                    Mutator(30, pytweening.easeInCirc, self, "x", tx),
                    Mutator(30, pytweening.easeInCirc, self, "y", ty),
                    itertools.chain(
                        range(30),
                        Instant(self.on_explode),
                    ),
                )
            )

            self.events.append("open_pack")

    def set_state(self, state: BoosterPackState) -> None:
        if self.state == state:
            return
        self.transition_out_state(self.state)
        self.state = state
        self.transition_in_state(self.state)

    def transition_out_state(self, state: BoosterPackState) -> None:
        ...

    def transition_in_state(self, state: BoosterPackState) -> None:
        match state:
            case BoosterPackState.OPENED:
                self.tweener.append(
                    itertools.zip_longest(
                        itertools.chain(
                            range(30),
                            Instant(self.on_faded_out),
                        ),
                    )
                )

    def on_explode(self) -> None:
        self.set_state(BoosterPackState.OPENED)
        self.events.append("explode")

    def on_faded_out(self) -> None:
        self.events.append("faded_out")

    def generate_cards(self) -> list[Card]:
        return [Card("OK", "good") for i in range(5)]


class BoosterPackScene(Scene):
    card_sprites: list[BoosterCardSprite]

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
        self.anims = []

    def update(self):
        self.framing.update()
        for spr in self.card_sprites:
            spr.update()
        for anim in self.anims:
            anim.update()
        self.anims = [anim for anim in self.anims if not anim.dead]
        for pack in self.booster_packs:
            pack.update()
            while pack.events:
                event = pack.events.pop()
                if event == "open_pack":
                    self.framing.putup()
                elif event == "explode":
                    cards = pack.generate_cards()
                    self.show_cards(cards)
                elif event == "faded_out":
                    self.add_anim("anims.burst", *pack.screen_pos())
        self.timer += 1

    def draw(self):
        pyxel.cls(9)
        for pack in self.booster_packs:
            pack.draw()
        for i, spr in enumerate(self.card_sprites):
            spr.draw()
                
        Anim.draw()
        self.framing.draw()
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def show_cards(self, cards: list[Card]) -> None:
        for i, card in enumerate(cards):
            target_x = layout_center_for_n(len(cards), 400)[i] - CARD_WIDTH // 2
            target_y = WINDOW_HEIGHT // 2 - CARD_HEIGHT // 2
            spr = BoosterCardSprite(target_x, target_y, i, card)
            self.card_sprites.append(spr)

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
        self.anims.append(
            result := Anim.from_predef(name, x, y, play_speed, attached_to)
        )
        return result


def gen_scene() -> Scene:
    return BoosterPackScene()
