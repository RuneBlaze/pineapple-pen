import math
from collections import Counter, deque
from concurrent.futures import Future, ThreadPoolExecutor
from enum import Enum
from typing import Literal

import numpy as np
import pyxel
from pyxelxl import blt_rot
from pyxelxl.font import _image_as_ndarray

from genio.base import Video, load_image
from genio.card import Card
from genio.components import (
    HasPos,
    blt_burning,
    camera_shift,
    dithering,
    pal_single_color,
    perlin_noise,
)
from genio.constants import CARD_HEIGHT, CARD_WIDTH
from genio.gears.button import COLOR_SCHEME_PRIMARY, ButtonElement, vec2
from genio.gears.card_printer import CardPrinter
from genio.gears.fontpack import fonts
from genio.ps import Anim
from genio.scene import Scene, module_scene
from genio.stagegen import (
    CardsLike,
    generate_sat_flashcards,
    generate_spyware_cards,
)
from genio.tween import Tweener


class CardState(Enum):
    APPEARING = 0
    IDLE = 1


class CollectionCardSprite:
    def __init__(
        self, x: int, y: int, card: Card, printer: CardPrinter, appear_delay: int = 0
    ) -> None:
        self.x = x
        self.y = y
        self.card = card
        self.img = printer.print_card(card)
        self.timer = 0

        self.state = CardState.APPEARING
        self.state_timer = Counter()

        self.tweener = Tweener()
        self.appear_delay = appear_delay

    def update(self) -> None:
        if self.appear_delay:
            self.appear_delay -= 1
            return
        self.tweener.update()
        self.timer += 1
        self.state_timer[self.state] += 1

        if self.state == CardState.APPEARING and self.state_timer[self.state] > 30:
            self.state = CardState.IDLE

    def draw_shadow(self):
        with dithering(0.5):
            with pal_single_color(1):
                blt_rot(
                    self.x + 2,
                    self.y + 2,
                    self.img,
                    0,
                    0,
                    CARD_WIDTH,
                    CARD_HEIGHT,
                    colkey=254,
                    rot=0,
                )

    def draw(self) -> None:
        if self.appear_delay:
            return
        match self.state:
            case CardState.APPEARING:
                blt_burning(
                    self.x,
                    self.y,
                    self.img,
                    perlin_noise(
                        self.img.width, self.img.height, 0.1, (self.x + self.y * 7) % 32
                    ),
                    self.state_timer[self.state],
                    "in",
                )
            case CardState.IDLE:
                shift = math.sin(self.timer / 15) * 3
                with camera_shift(0, shift):
                    self.draw_shadow()
                    blt_rot(
                        self.x,
                        self.y,
                        self.img,
                        0,
                        0,
                        CARD_WIDTH,
                        CARD_HEIGHT,
                        254,
                    )


PADDING = 10


def grid_layout(ix: int) -> tuple[int, int]:
    return ix % 5 * (CARD_WIDTH + PADDING), ix // 5 * (CARD_HEIGHT + PADDING)


class GenerateCardsType(Enum):
    SAT = 0
    GENERIC_STS = 1


@module_scene
class SceneCollection(Scene):
    cards: list[CollectionCardSprite]
    mailbox: deque[Future[CardsLike]]
    anims: list[Anim]

    def __init__(self) -> None:
        self.cards = []
        self.printer = CardPrinter()
        self.anims = []
        self.cards.append(
            CollectionCardSprite(
                0, 0, Card("Rivers", "This is a test card"), self.printer
            ),
        )
        self.timer = 0
        self.current_page = 0
        self.generate_buttons = [
            ButtonElement(
                "Generate",
                COLOR_SCHEME_PRIMARY,
                vec2(100, 100),
                "",
            ),
            ButtonElement(
                "Generate",
                COLOR_SCHEME_PRIMARY,
                vec2(100, 150),
                "",
            ),
        ]
        self.mailbox = deque()
        self.executor = ThreadPoolExecutor(2)
        self.background_video = Video("background/*.png")

        self.add_card(
            Card(
                "Letter Remover",
                "Strip away one letter from each card in your hand, preferring to remove the initial letter.",
                card_art_name="sun moon",
            ),
        )

        self.add_card(
            Card(
                "Pluralize",
                "Transform each card's name in your hand into its plural form.",
                card_art_name="web of intrigue",
            )
        )

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

    def update(self) -> None:
        self.background_video.update()
        for card in self.cards:
            card.update()

        for button in self.generate_buttons:
            button.update()

        if self.generate_buttons[0].btnp:
            self.generate_new_cards(GenerateCardsType.SAT)

        if self.generate_buttons[1].btnp:
            self.generate_new_cards(GenerateCardsType.GENERIC_STS)

        for anim in self.anims:
            anim.update()

        self.anims = [anim for anim in self.anims if not anim.dead]
        self.check_mailbox()
        self.timer += 1

    def check_mailbox(self) -> None:
        if self.mailbox and self.mailbox[0].done():
            result = self.mailbox.popleft().result()
            next_ix = len(self.cards)
            for i, card in enumerate(result.to_cards()):
                x, y = grid_layout(i + next_ix)
                self.cards.append(
                    CollectionCardSprite(x, y, card, self.printer, len(self.cards) * 10)
                )

    def add_card(self, card: Card) -> None:
        next_ix = len(self.cards)
        x, y = grid_layout(next_ix)
        self.cards.append(CollectionCardSprite(x, y, card, self.printer, 0))

    def generate_new_cards(self, typ: GenerateCardsType) -> None:
        match typ:
            case GenerateCardsType.SAT:
                self.mailbox.append(
                    self.executor.submit(
                        generate_sat_flashcards, avoid=self.words_in_collection()
                    )
                )
            case GenerateCardsType.GENERIC_STS:
                self.mailbox.append(self.executor.submit(generate_spyware_cards))

    def draw(self) -> None:
        pyxel.cls(0)
        self.background_video.draw_image()
        for card in self.cards:
            card.draw()
        for button in self.generate_buttons:
            button.draw()

        for anim in self.anims:
            anim.draw_myself()
        self.draw_page_turner(100, 120)
        Anim.draw()
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def draw_page_turner(self, x: int, y: int) -> None:
        self.draw_page_number(x, y)
        mag = math.sin(self.timer / 15) * 1
        self.draw_clickable_arrow(x + 28 - mag, y + 4)
        self.draw_clickable_arrow(x - 13 + mag, 124, direction="left")

    def draw_page_number(self, x: int, y: int) -> None:
        fonts.willow_branch(x, y, "1/", 7)
        inverted_8 = pyxel.Image(15, 15)
        fonts.willow_branch(0, 0, "8", 7, target=inverted_8)
        _image_as_ndarray(inverted_8)[:] = np.rot90(_image_as_ndarray(inverted_8), 1)
        pyxel.blt(x + 12, y - 3, inverted_8, 0, 0, 100, 100, 0)

    def draw_clickable_arrow(
        self, x: int, y: int, direction: Literal["left", "right"] = "right"
    ) -> None:
        if direction == "right":
            pyxel.tri(x, y, x + 8, y + 4, x, y + 8, 7)
        else:
            pyxel.tri(x + 8, y, x, y + 4, x + 8, y + 8, 7)

    def words_in_collection(self) -> list[str]:
        return [card.card.name for card in self.cards]

    def draw_crosshair(self, x: int, y: int):
        cursor = load_image("cursor.png")
        pyxel.blt(x, y, cursor, 0, 0, 16, 16, colkey=254)
