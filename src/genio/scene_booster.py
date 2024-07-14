import itertools
import math
import textwrap
from collections import Counter, defaultdict, deque
from concurrent.futures import Future
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, TypeAlias

import numpy as np
import pytweening
import pyxel
from pyxelxl import blt_rot, layout
from typing_extensions import assert_never

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, load_image
from genio.battle import setup_battle_bundle
from genio.card import Card
from genio.components import (
    DrawDeck,
    arcade_text,
    blt_burning,
    cute_text,
    perlin_noise,
    retro_text,
)
from genio.constants import CARD_HEIGHT, CARD_WIDTH
from genio.core.base import promptly
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
from genio.scene_stages import draw_lush_background
from genio.semantic_search import search_closest_document
from genio.tween import Instant, Mutator, Tweener


@dataclass
class GenerateSATFlashCardResult:
    """A set of precisely 5 flashcards for SAT preparation."""

    flashcards: Annotated[
        list[dict],
        (
            "A list of flashcards, objects containing two keys: 'word' and 'definition', "
            "each corresponding to the word and its definition from dictionary. Definition "
            "should be in dictionary form, like (noun) a person who is very interested in [...]"
        ),
    ]


@promptly
def generate_sat_flashcards() -> GenerateSATFlashCardResult:
    """\
    Act as an excellent tutor and a test prep professional by designing
    a set of 5 flashcards for SAT preparation, as if pulled from a dictionary.

    Write words in their entire form, and provide their definitions.
    Choose words that are no longer than 9 characters.

    {{ formatting_instructions }}
    """


class BoosterPackType(Enum):
    SPY_THEMED = 0
    STANDARDIZED_TEST_THEMED = 1

    def humanized_name(self) -> str:
        match self:
            case BoosterPackType.SPY_THEMED:
                return "Spyware Booster Pack"
            case BoosterPackType.STANDARDIZED_TEST_THEMED:
                return "SAT Vocabulary Pack"
            case _:
                assert_never()

    def short_humanized_name(self) -> str:
        match self:
            case BoosterPackType.SPY_THEMED:
                return "Spyware"
            case BoosterPackType.STANDARDIZED_TEST_THEMED:
                return "SAT Vocab"
            case arg:
                return "SAT Vocab"

    def humanized_description(self) -> str:
        match self:
            case BoosterPackType.SPY_THEMED:
                return "Choose 2 among 5 cards; James Bond, word synthesizers, covert and linguistic manipulations."
            case BoosterPackType.STANDARDIZED_TEST_THEMED:
                return (
                    "Choose 2 among 5 flash cards to help you achieve a higher SAT score! "
                    "Study with the most effective flashcards available. "
                )
            case _:
                return (
                    "Choose 2 among 5 flash cards to help you achieve a higher SAT score! "
                    "Study with the most effective flashcards available. "
                )


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
        self.image = (
            load_image("ui", "card-spy.png")
            if pack_type == BoosterPackType.SPY_THEMED
            else load_image("ui", "card-sat.png")
        )
        self.tweener = Tweener()
        self.state = BoosterPackState.CLOSED
        self.angle = 0
        self.hovering = False
        self.noise = perlin_noise(self.image.width, self.image.height, 0.1)
        self.events = []
        self.timer = 0
        self.state_timers = defaultdict(int)
        self.allowed_cards = 2
        self.dead = False

    def screen_pos(self) -> tuple[float, float]:
        return self.x + self.image.width // 2, self.y + self.image.height // 2

    def draw(self):
        with dithering(1.0):
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
        if (
            self.state == BoosterPackState.OPENED
            and self.state_timers[self.state] >= 35
        ):
            self.dead = True
        label_width = 46
        x_offset = self.image.width // 2 - label_width // 2
        mult = 1.0
        if self.state not in [BoosterPackState.CLOSED, BoosterPackState.OPENING]:
            return
        if self.state == BoosterPackState.OPENING:
            mult = 1.0 - pytweening.easeInOutCubic(
                min(self.state_timers[self.state] / 20, 1)
            )
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
                self.x + 10 < mx < self.x + self.image.width - 10
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
            and self.hovering
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
        generated = generate_sat_flashcards()
        return [
            Card(name=card["word"], description=card["definition"])
            for card in generated.flashcards
        ]


@dataclass
class ColorScheme:
    primary: int
    secondary: int


COLOR_SCHEME_PRIMARY = ColorScheme(3, 11)
COLOR_SCHEME_SECONDARY = ColorScheme(4, 8)


Vec2: TypeAlias = np.ndarray


def vec2(x: int, y: int) -> Vec2:
    return np.array([x, y], dtype=int)


def is_mouse_in_rect(xy: Vec2, wh: Vec2) -> bool:
    return (
        xy[0] <= pyxel.mouse_x
        and pyxel.mouse_x < xy[0] + wh[0]
        and xy[1] <= pyxel.mouse_y
        and pyxel.mouse_y < xy[1] + wh[1]
    )


@dataclass
class ButtonElement:
    text: str
    color_scheme: ColorScheme
    position: Vec2

    hovering: bool = False
    btnp: bool = False

    def draw_at(self) -> Vec2:
        xy = self.position
        button_width = 55
        c1, c2 = self.color_scheme.primary, self.color_scheme.secondary
        if self.hovering:
            draw_rounded_rectangle(*(xy + vec2(0, 1)), button_width, 16, 4, c1)
            draw_rounded_rectangle(*xy, button_width, 16, 4, c1)
            if not pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
                with dithering(0.5):
                    draw_rounded_rectangle(*xy, button_width, 16, 4, c2)
            cute_text(*xy, self.text, 7, layout=layout(w=button_width, ha="center"))
        else:
            draw_rounded_rectangle(*(xy + vec2(0, 1)), button_width, 16, 4, c1)
            draw_rounded_rectangle(*xy, button_width, 16, 4, c2)
            cute_text(*xy, self.text, 7, layout=layout(w=button_width, ha="center"))
        return vec2(button_width + 2, 16)

    def update(self) -> None:
        xy = self.position
        if is_mouse_in_rect(xy, vec2(55, 16)):
            self.hovering = True
            if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                self.btnp = True
                return
        else:
            self.hovering = False
        self.btnp = False


@dataclass
class HelpBoxContents:
    title: str
    description: str

    def draw(self, dithering_mult: float = 1.0) -> None:
        width = 200
        x_offset = (WINDOW_WIDTH - width) // 2
        with dithering(dithering_mult * 0.5):
            draw_rounded_rectangle(x_offset, 175, width, 30, 5, 0)
        with dithering(dithering_mult):
            cute_text(
                x_offset + 6,
                175 - 7,
                self.title,
                7,
                layout=layout(w=200 - 6 * 2, h=11, ha="center"),
            )
            for i, l in enumerate(textwrap.wrap(self.description, 48)):
                pyxel.text(x_offset + 6, 173 + 10 + i * 7, l, 7)


def draw_tiled(img: pyxel.Image) -> None:
    w, h = img.width, img.height
    for x, y in itertools.product(
        range(0, WINDOW_WIDTH, w), range(0, WINDOW_HEIGHT, h)
    ):
        pyxel.blt(x, y, img, 0, 0, w, h, 1)


@dataclass
class ScoreItem:
    name: str
    add_mult: float

    x: int
    y: int
    opacity: float

    label: str | None = None

    tweener: Tweener = field(default_factory=Tweener)

    def draw(self) -> None:
        label_width = 80
        mult = self.opacity
        with dithering(0.5 * mult):
            draw_rounded_rectangle(self.x, self.y, label_width, 10, 3, 0)
        with dithering(1.0 * mult):
            retro_text(
                self.x + 2,
                self.y + 1,
                self.name,
                7,
                layout=layout(w=label_width - 4, h=10, ha="left"),
            )
            monetary_value = f"{self.add_mult:04.2f}"
            retro_text(
                self.x + 2,
                self.y + 1,
                f"${monetary_value}" if not self.label else self.label,
                7,
                layout=layout(w=label_width - 4, h=10, ha="right"),
            )

    def fade_in(self) -> None:
        self.opacity = 0.0
        self.tweener.append(
            itertools.zip_longest(
                Mutator(18, pytweening.easeInCirc, self, "opacity", 1.0),
                Mutator(18, pytweening.easeInCirc, self, "y", self.y + 3),
            )
        )

    def update(self) -> None:
        self.tweener.update()


class BoosterPackSceneState(Enum):
    RESULTS = 0
    SHOP = 1
    PRE_RESULTS = 2
    PRE_SHOP = 3

    def is_results_like(self) -> bool:
        return self in [
            BoosterPackSceneState.RESULTS,
            BoosterPackSceneState.PRE_RESULTS,
        ]

    def is_shop_like(self) -> bool:
        return self in [BoosterPackSceneState.SHOP, BoosterPackSceneState.PRE_SHOP]


class BoosterPackScene(Scene):
    card_sprites: list[BoosterCardSprite]
    chosen_pack: BoosterPack | None
    mailbox: deque[Future[list[Card]]]
    check_mail_signal = deque[BoosterPack]

    booster_packs: list[BoosterPack]

    def __init__(self) -> None:
        super().__init__()

        self.framing = ResolvingFraming(self)
        self.money_accumulated = 0.0

        self.booster_packs = []
        self.booster_packs.append(
            BoosterPack(300 + 17, 47 + 30, BoosterPackType.SPY_THEMED)
        )
        self.booster_packs.append(
            BoosterPack(230 + 17, 47 + 30, BoosterPackType.STANDARDIZED_TEST_THEMED)
        )

        self.state_timers = Counter()

        self.tweener = Tweener()

        y_offset = 80
        x_offset = 260
        self.score_items = [
            ScoreItem("Overkill", 0.5, x_offset, 0 + y_offset, 1.0),
            ScoreItem("Combo", 0.2, x_offset + 20, 12 + y_offset, 1.0),
            ScoreItem("Total", 0.2, x_offset, 12 + 12 + y_offset, 1.0, "$12.00"),
        ]

        for i, item in enumerate(self.score_items):
            item.opacity = 0.0
            item.y -= 3
            self.tweener.append(
                itertools.chain(
                    range(3),
                    Instant(item.fade_in),
                )
            )
        self.tweener.append(
            itertools.chain(
                range(3),
                Mutator(60, pytweening.easeInOutCubic, self, "money_accumulated", 12.0),
            )
        )

        self.card_sprites = []
        self.bundle = setup_battle_bundle(
            "initial_deck", "players.starter", ["enemies.evil_mask"] * 2
        )
        self.timer = 0
        self.anims = []
        self.draw_deck = DrawDeck(self.bundle.card_bundle)
        self.chosen_pack = None
        self.info_box_energy = 0.0
        self.chosen_pack_dup = None
        self.help_box = HelpBoxContents("Help", "Click on a card to choose it." * 4)
        self.help_box_energy = 0.0
        self.mailbox = deque()
        self.check_mail_signal = deque()
        self.executor = ThreadPoolExecutor(2)
        self.state = BoosterPackSceneState.PRE_RESULTS
        self.next_button = ButtonElement("Next", ColorScheme(0, 1), vec2(320, 180))
        self.results_fade = 0.0
        self.shop_fade_in = 0.0

    def pump_help_box(self, title: str, description: str) -> None:
        if title != self.help_box.title or description != self.help_box.description:
            if self.help_box_energy > 0.55:
                return
        self.help_box = HelpBoxContents(title, description)
        self.help_box_energy += 0.2
        self.help_box_energy = min(self.help_box_energy, 1.2)

    def update(self):
        self.framing.update()
        self.tick_check_mail()
        self.tweener.update()
        self.next_button.update()
        if self.next_button.btnp:
            self.state = BoosterPackSceneState.PRE_SHOP
            for score_item in self.score_items:
                score_item.tweener.append(
                    Mutator(18, pytweening.easeInCirc, score_item, "opacity", 0.0)
                )
            self.tweener.append(
                itertools.chain(
                    Mutator(18, pytweening.easeInCirc, self, "results_fade", 1.0),
                )
            )
            self.tweener.append(
                Mutator(18, pytweening.easeInCirc, self, "shop_fade_in", 1.0)
            )

        aggregate_events = []
        self.state_timers[self.state] += 1
        for spr in self.card_sprites:
            spr.update()
            aggregate_events.extend(spr.events)
            if spr.hovering:
                self.pump_help_box(spr.card.name, spr.card.description or "")
            spr.events.clear()
        for score_item in self.score_items:
            score_item.update()
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

        if self.card_sprites and all(
            spr.state == BoosterCardSpriteState.DEAD for spr in self.card_sprites
        ):
            self.card_sprites.clear()
            self.chosen_pack = None
            self.framing.teardown()
        for anim in self.anims:
            anim.update()
        self.anims = [anim for anim in self.anims if not anim.dead]
        self.update_booster_packs()
        self.help_box_energy = max(self.help_box_energy - 0.1, 0.0)
        self.timer += 1

    def update_booster_packs(self):
        if self.state.is_results_like():
            return
        any_booster_pack_opening = any(
            pack.state != BoosterPackState.CLOSED for pack in self.booster_packs
        )
        any_booster_pack_opening = (
            any_booster_pack_opening
            or bool(self.chosen_pack)
            or bool(self.card_sprites)
        )
        for pack in self.booster_packs:
            if any_booster_pack_opening and pack.state == BoosterPackState.CLOSED:
                continue
            pack.update()
            while pack.events:
                event = pack.events.pop()
                if event == "open_pack":
                    self.framing.putup()
                    self.mailbox.append(self.executor.submit(pack.generate_cards))
                elif event == "explode":
                    self.check_mail_signal.append(pack)
                    self.tick_check_mail()
                elif event == "faded_out":
                    self.add_anim("anims.burst", *pack.screen_pos())
            if pack.hovering and pack.state == BoosterPackState.CLOSED:
                self.pump_help_box(
                    pack.pack_type.humanized_name(),
                    pack.pack_type.humanized_description(),
                )
        self.booster_packs = [pack for pack in self.booster_packs if not pack.dead]
        if self.chosen_pack:
            self.info_box_energy = min(self.info_box_energy + 0.1, 1.0)
        else:
            self.info_box_energy = max(self.info_box_energy - 0.1, 0.0)
        self.chosen_pack_dup = self.chosen_pack or self.chosen_pack_dup

    def tick_check_mail(self):
        if self.check_mail_signal and self.mailbox[0].done():
            pack = self.check_mail_signal.popleft()
            self.show_cards(self.mailbox.popleft().result())
            self.chosen_pack = pack

    def draw(self):
        draw_lush_background()
        pyxel.blt(
            50,
            50,
            img := load_image("ui", "window-image.png"),
            0,
            0,
            img.width,
            img.height,
            5,
        )
        self.draw_deck.draw(10, 190)
        with dithering(0.5 * (1 - self.results_fade)):
            # draw_rounded_rectangle(200, 40, 190, 160, 5, col=1)
            draw_rounded_rectangle(250, 40, 140, 160, 5, col=1)
        c1 = 7
        w = 100
        x = 270
        y = 40
        with dithering(1.0 - self.results_fade):
            arcade_text(x, y + 5, "1-1", c1, layout=layout(w=w, ha="center"))
            retro_text(x, y + 20, "Beginnings", c1, layout=layout(w=w, ha="center"))

        self.draw_results()
        self.draw_info_box()

        if not self.state.is_results_like():
            with dithering(self.shop_fade_in):
                with camera_shift(-3 * (1 - self.shop_fade_in), 0):
                    for pack in self.booster_packs:
                        pack.draw()

                    for i, spr in enumerate(self.card_sprites):
                        spr.draw()

        with camera_shift(0, min(self.help_box_energy, 1) * 3):
            self.help_box.draw(min(self.help_box_energy, 1))
        Anim.draw()
        self.framing.draw()

        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def draw_results(self):
        with dithering(1.0 - self.results_fade):
            pyxel.text(270, 40 + 20 + 10, "- Stage Cleared -", 7)

            formatted_money = f"${self.money_accumulated:04.2f}"
            arcade_text(270, 183, formatted_money, 7)
            self.next_button.draw_at()
            self.draw_deck.draw_card_label(10, 190)

        for item in self.score_items:
            item.draw()

    def draw_info_box(self):
        if not self.chosen_pack_dup:
            return
        with dithering(self.info_box_energy):
            with camera_shift(-(WINDOW_WIDTH - 100) // 2, -15):
                draw_window_frame(0, 10, 100, 30, 5)
                cute_text(
                    0,
                    10 + 2,
                    self.chosen_pack_dup.pack_type.short_humanized_name(),
                    7,
                    layout=layout(w=100, h=11, ha="center"),
                )
                if (ncards := self.chosen_pack_dup.allowed_cards) <= 1:
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

    def request_next_scene(self) -> str | None:
        if pyxel.btnp(pyxel.KEY_Q):
            return "genio.gui"

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
