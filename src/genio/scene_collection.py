import math
from collections import Counter, deque
from concurrent.futures import Future, ThreadPoolExecutor
from enum import Enum

import pyxel
from pyxelxl import blt_rot

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
from genio.ps import Anim
from genio.scene import Scene, module_scene
from genio.stagegen import (
    CardsLike,
    generate_sat_flashcards,
    generate_sts_cards,
)
from genio.tween import Tweener


class CardState(Enum):
    APPEARING = 0
    IDLE = 1


class CollectionCardSprite:
    def __init__(self, x: int, y: int, card: Card, printer: CardPrinter) -> None:
        self.x = x
        self.y = y
        self.card = card
        self.img = printer.print_card(card)
        self.timer = 0

        self.state = CardState.APPEARING
        self.state_timer = Counter()

        self.tweener = Tweener()

    def update(self) -> None:
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
    return ix % 4 * (CARD_WIDTH + PADDING), ix // 4 * (CARD_HEIGHT + PADDING)


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
            )
        )
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

    def check_mailbox(self) -> None:
        if self.mailbox and self.mailbox[0].done():
            result = self.mailbox.popleft().result()
            next_ix = len(self.cards)
            for i, card in enumerate(result.to_cards()):
                x, y = grid_layout(i + next_ix)
                self.cards.append(CollectionCardSprite(x, y, card, self.printer))

    def generate_new_cards(self, typ: GenerateCardsType) -> None:
        match typ:
            case GenerateCardsType.SAT:
                self.mailbox.append(
                    self.executor.submit(
                        generate_sat_flashcards, avoid=self.words_in_collection()
                    )
                )
            case GenerateCardsType.GENERIC_STS:
                self.mailbox.append(
                    self.executor.submit(
                        generate_sts_cards, avoid=self.words_in_collection()
                    )
                )

    def draw(self) -> None:
        pyxel.cls(0)
        self.background_video.draw_image()
        for card in self.cards:
            card.draw()
        for button in self.generate_buttons:
            button.draw()

        for anim in self.anims:
            anim.draw_myself()

        Anim.draw()

        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def words_in_collection(self) -> list[str]:
        return [card.card.name for card in self.cards]

    def draw_crosshair(self, x: int, y: int):
        cursor = load_image("cursor.png")
        pyxel.blt(x, y, cursor, 0, 0, 16, 16, colkey=254)
