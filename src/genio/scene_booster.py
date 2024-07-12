import itertools
import math
from collections import defaultdict
from enum import Enum
from functools import cache

import numpy as np
import pytweening
import pyxel
from pyxelxl import blt_rot, layout
from typing_extensions import assert_never

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, load_image
from genio.battle import setup_battle_bundle
from genio.card import Card
from genio.components import DrawDeck, blt_burning, cute_text, retro_text
from genio.constants import CARD_HEIGHT, CARD_WIDTH
from genio.gui import (
    CardArtSet,
    ResolvingFraming,
    camera_shift,
    card_back,
    dithering,
)
from genio.layout import layout_center_for_n
from genio.ps import Anim, HasPos
from genio.scene import Scene
from genio.semantic_search import search_closest_document
from genio.tween import Instant, Mutator, Tweener


class BoosterPackType(Enum):
    SPY_THEMED = 0
    STANDARDIZED_TEST_THEMED = 1

    def humanized_name(self) -> str:
        match self:
            case BoosterPackType.SPY_THEMED:
                return "Spyware Pack"
            case BoosterPackType.STANDARDIZED_TEST_THEMED:
                return "SAT Vocabulary Pack"
            case _:
                assert_never()


class BoosterPackState(Enum):
    CLOSED = 0
    OPENING = 1
    OPENED = 2


def draw_rounded_rectangle(x: int, y: int, w: int, h: int, r: int, col: int) -> None:
    pyxel.rect(x + r, y, w - 2 * r + 1, h + 1, col)
    pyxel.rect(x, y + r, r, h - 2 * r, col)
    pyxel.rect(x + w - r + 1, y + r, r, h - 2 * r, col)
    pyxel.circ(x + r, y + r, r, col)
    pyxel.circ(x + w - r, y + r, r, col)
    pyxel.circ(x + r, y + h - r, r, col)
    pyxel.circ(x + w - r, y + h - r, r, col)


def draw_window_frame(x: int, y: int, w: int, h: int, col: int) -> None:
    draw_rounded_rectangle(x - 1, y - 1, w + 2, h + 2, 4, 7)
    draw_rounded_rectangle(x, y, w, h, 4, col)


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
    """A card appearing in a booster pack."""

    def __init__(self, x: int, y: int, ix: int, card: Card) -> None:
        base_image = pyxel.Image(43, 60)
        base_image.blt(0, 0, 0, 0, 0, 43, 60, colkey=0)
        self.card_art = CardArtSet(base_image, search_closest_document(card.name))

        self.x = x
        self.y = y
        self.image = self.card_art.imprint(card.name, 0)
        self.ix = ix

        self.wave_mag = 1.0
        self.card = card

        self.state_timers = defaultdict(int)

        self.state = BoosterCardSpriteState.APPEARING
        self.tweens = Tweener()

        self.tweens.append(
            itertools.chain(
                range(31 + 3 * ix),
                Instant(lambda: self.set_state(BoosterCardSpriteState.ACTIVE)),
            )
        )

        self.state_timers[self.state] -= 3 * ix

        self.hovering = False
        self.fade_out = 0
        self.events = []
        self.inconsequential = False

    def add_event(self, event: str) -> None:
        self.events.append(event)
        if event == "chosen":
            self.inconsequential = True

    def draw(self):
        match self.state:
            case (
                BoosterCardSpriteState.APPEARING
                | BoosterCardSpriteState.DISAPPEARING as state
            ):
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
                shift = (
                    math.sin((self.state_timers[self.state] + 103 * self.ix) / 10) * 3
                )
                with camera_shift(0, shift * self.wave_mag):
                    blt_rot(
                        self.x,
                        self.y,
                        card_back(),
                        0,
                        0,
                        self.image.width,
                        self.image.height,
                        colkey=0,
                    )
                    with dithering(1 - self.fade_out):
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
        if state == BoosterCardSpriteState.DISAPPEARING:
            self.inconsequential = True
            self.tweens.append(
                range(31),
                Instant(lambda: self.set_state(BoosterCardSpriteState.DEAD)),
            )
        elif state == BoosterCardSpriteState.CHOSEN:
            self.tweens.append(
                itertools.zip_longest(
                    Mutator(8, pytweening.easeInCirc, self, "x", 10),
                    Mutator(8, pytweening.easeInCirc, self, "y", 190 - 5),
                ),
                Instant(lambda: self.add_event("chosen")),
                Mutator(5, pytweening.easeInCirc, self, "fade_out", 1),
                Instant(lambda: self.add_event(("added", self.card))),
                Mutator(3, pytweening.easeInCirc, self, "y", 190 - 10),
                Mutator(5 - 2, pytweening.easeInCirc, self, "y", 190),
                range(2),
                Instant(lambda: self.set_state(BoosterCardSpriteState.DEAD)),
            )

    def update(self):
        self.state_timers[self.state] += 1
        self.tweens.update()

        self.update_hovering()

        if self.hovering and pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.set_state(BoosterCardSpriteState.CHOSEN)

    def update_hovering(self):
        if self.state != BoosterCardSpriteState.ACTIVE:
            self.hovering = False
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        if (
            self.x < mx < self.x + self.image.width
            and self.y < my < self.y + self.image.height
        ):
            if not self.hovering:
                self.tweens.append(
                    Mutator(10, pytweening.easeInOutBounce, self, "wave_mag", 0)
                )
            self.hovering = True
        else:
            if self.hovering:
                self.tweens.append(
                    Mutator(10, pytweening.easeInCirc, self, "wave_mag", 1)
                )
            self.hovering = False


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
        self.allowed_cards = 2

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
        self.draw_label()
            

    def draw_label(self) -> None:
        label_width = 46
        x_offset = self.image.width // 2 - label_width // 2
        mult = 1.0
        if self.state not in [BoosterPackState.CLOSED, BoosterPackState.OPENING]:
            return
        if self.state == BoosterPackState.OPENING:
            mult = 1.0 - pytweening.easeInOutCubic(min(self.state_timers[self.state] / 20, 1))
        with dithering(0.5 * mult):
            draw_rounded_rectangle(
                self.x + x_offset, self.y + 80, label_width, 10, 3, 0
            )
        with dithering(1.0 * mult):
            retro_text(
                self.x + x_offset + 2,
                self.y + 80 + 1,
                "$10.00",
                7,
                layout=layout(w=label_width - 4, h=10, ha="center"),
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
                ),
                itertools.chain(
                    range(5),
                    Instant(self.on_explode),
                ),
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
                            range(20),
                            Instant(self.on_faded_out),
                        ),
                        itertools.chain(
                            range(30), Instant(lambda: self.events.append("explode"))
                        ),
                    ),
                )

    def on_explode(self) -> None:
        self.set_state(BoosterPackState.OPENED)

    def on_faded_out(self) -> None:
        self.events.append("faded_out")

    def generate_cards(self) -> list[Card]:
        return [Card("OK", "good") for i in range(5)]


class BoosterPackScene(Scene):
    card_sprites: list[BoosterCardSprite]
    chosen_pack: BoosterPack | None

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
        self.draw_deck = DrawDeck(self.bundle.card_bundle)
        self.chosen_pack = None

    def update(self):
        self.framing.update()
        aggregate_events = []
        for spr in self.card_sprites:
            spr.update()
            aggregate_events.extend(spr.events)
            spr.events.clear()
        for event in aggregate_events:
            match event:
                case "chosen":
                    self.chosen_pack.allowed_cards -= 1
                    if self.chosen_pack.allowed_cards <= 0:
                        self.rearrange_cards(should_disappear=True)
                    else:
                        self.rearrange_cards()
                case ("added", card):
                    self.bundle.card_bundle.add_into_deck_top(card)
                
        if self.card_sprites and all(spr.state == BoosterCardSpriteState.DEAD for spr in self.card_sprites):
            self.card_sprites.clear()
            self.chosen_pack = None
            self.framing.teardown()
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
                    self.chosen_pack = pack
                elif event == "faded_out":
                    self.add_anim("anims.burst", *pack.screen_pos())
        self.timer += 1

        if pyxel.btnp(pyxel.KEY_SPACE):
            self.destroy_rest_cards()

    def draw(self):
        pyxel.cls(9)
        self.draw_deck.draw(10, 190)
        for pack in self.booster_packs:
            pack.draw()
        for i, spr in enumerate(self.card_sprites):
            spr.draw()
        self.draw_deck.draw_card_label(10, 190)
        if self.chosen_pack:
            self.draw_info_box()
        Anim.draw()
        self.framing.draw()
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def draw_info_box(self):
        from pyxelxl import layout

        with camera_shift(-(WINDOW_WIDTH - 100) // 2, -15):
            draw_window_frame(0, 10, 100, 30, 5)
            cute_text(
                0,
                10 + 2,
                self.chosen_pack.pack_type.humanized_name(),
                7,
                layout=layout(w=100, h=11, ha="center"),
            )
            if (ncards := self.chosen_pack.allowed_cards) <= 1:
                pyxel.text(22, 26 + 2, "Choose 1 card", 7)
            else:
                ncards = max(1, ncards)  # 0 card on the UI seems really weird
                pyxel.text(20, 26 + 2, f"Choose {ncards} cards", 7)

    def show_cards(self, cards: list[Card]) -> None:
        for i, card in enumerate(cards):
            target_x = layout_center_for_n(len(cards), 400)[i] - CARD_WIDTH // 2
            target_y = WINDOW_HEIGHT // 2 - CARD_HEIGHT // 2
            spr = BoosterCardSprite(target_x, target_y, i, card)
            self.card_sprites.append(spr)

    def make_cards_disappear(self) -> None:
        for spr in self.card_sprites:
            if spr.state == BoosterCardSpriteState.ACTIVE and not spr.inconsequential:
                spr.set_state(BoosterCardSpriteState.DISAPPEARING)

    def rearrange_cards(self, should_disappear: bool = False) -> None:
        consequential_cards = [
            spr for spr in self.card_sprites if not spr.inconsequential
        ]
        for i, spr in enumerate(consequential_cards):
            target_x = (
                layout_center_for_n(len(consequential_cards), 400)[i] - CARD_WIDTH // 2
            )
            target_y = WINDOW_HEIGHT // 2 - CARD_HEIGHT // 2
            spr.tweens.append(
                itertools.zip_longest(
                    Mutator(12, pytweening.easeInCirc, spr, "x", target_x),
                    Mutator(12, pytweening.easeInCirc, spr, "y", target_y),
                )
            )

            if should_disappear:
                spr.tweens.append(
                    itertools.chain(
                        range(12 + i * 3),
                        Instant(
                            (
                                lambda spr: lambda: spr.set_state(
                                    BoosterCardSpriteState.DISAPPEARING
                                )
                            )(spr)
                        ),
                    )
                )

    def draw_crosshair(self, x, y):
        pyxel.line(x - 5, y, x + 5, y, 7)
        pyxel.line(x, y - 5, x, y + 5, 7)

    def destroy_rest_cards(self) -> None:
        for spr in self.card_sprites:
            if spr.state == BoosterCardSpriteState.ACTIVE:
                spr.set_state(BoosterCardSpriteState.DISAPPEARING)

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
