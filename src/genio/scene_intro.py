import math
from collections import Counter, deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Annotated

import numpy as np
import pytweening
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
from genio.constants import CARD_HEIGHT, CARD_WIDTH, WINDOW_HEIGHT, WINDOW_WIDTH
from genio.core.base import promptly
from genio.gears.card_printer import CardPrinter
from genio.gui import ResolvingFraming, Tooltip
from genio.ps import Anim
from genio.scene import Scene, module_scene
from genio.tween import Instant, Mutator, Tweener


class RagdollCardSpriteState:
    APPEARING = 0
    IDLE = 1


rng = np.random.default_rng()


class RagdollCardSprite:
    def __init__(self, x: int, y: int, card: Card, card_printer: CardPrinter) -> None:
        self.x = x
        self.y = y
        self.card = card
        self.img = card_printer.print_card(card)
        self.rotation = 0
        self.timer = 0
        self.state = RagdollCardSpriteState.APPEARING

        self.hovering = False
        self.tweens = Tweener()
        self.card_printer = card_printer

        self.state_timer = Counter()
        self.highlight_timer = 0
        self.flashing_energy = 0

    def flash(self) -> None:
        self.tweens.append_mutate(self, "flashing_energy", 5, 1, "ease_in_out_quad")
        self.tweens.append_mutate(self, "flashing_energy", 5, 0, "ease_in_out_quad")

    def screen_pos(self) -> tuple[int, int]:
        return self.x + CARD_WIDTH // 2, self.y + CARD_HEIGHT // 2

    def draw(self) -> None:
        shift_y = math.sin(self.timer * 0.1) * 2 * math.exp(-self.highlight_timer * 0.1)
        with camera_shift(0, shift_y):
            self._draw()

    def _draw(self):
        if self.state == RagdollCardSpriteState.APPEARING:
            blt_burning(
                self.x,
                self.y,
                self.img,
                perlin_noise(
                    self.img.width, self.img.height, 0.1, hash(self.card) % 10
                ),
                self.state_timer[self.state],
                "in",
            )
            return
        self.draw_shadow()
        if self.flashing_energy > 0.5:
            flash_color = 7
        else:
            flash_color = None
        with pal_single_color(flash_color):
            blt_rot(
                self.x,
                self.y,
                self.img,
                0,
                0,
                self.img.width,
                self.img.height,
                colkey=254,
                rot=self.rotation,
            )

    def becomes(self, card: Card) -> None:
        self.card = card
        self.img = self.card_printer.print_card(card)

    def update(self) -> None:
        self.timer += 1
        self.state_timer[self.state] += 1
        self.tweens.update()

        if self.state == RagdollCardSpriteState.APPEARING:
            if self.state_timer[self.state] >= 30:
                self.state = RagdollCardSpriteState.IDLE
                self.state_timer[self.state] = 0
        else:
            # judge hovering
            if (
                self.x <= pyxel.mouse_x <= self.x + CARD_WIDTH
                and self.y <= pyxel.mouse_y <= self.y + CARD_HEIGHT
            ):
                if not self.hovering:
                    self.on_hovering_to_true()
                self.hovering = True
                self.highlight_timer += 1
            else:
                self.hovering = False
                self.highlight_timer = 0

    def on_hovering_to_true(self):
        if rng.random() < 0.5:
            next_rot = rng.uniform(-4, -2)
        else:
            next_rot = rng.uniform(2, 4)
        self.tweens.append(
            Mutator(10, pytweening.easeInOutQuad, self, "rotation", next_rot),
            range(18),
            Mutator(10, pytweening.easeInOutQuad, self, "rotation", 0),
        )

    def draw_shadow(self):
        with dithering(0.5):
            with pal_single_color(1):
                blt_rot(
                    self.x + 2,
                    self.y + 2,
                    self.img,
                    0,
                    0,
                    self.img.width,
                    self.img.height,
                    colkey=254,
                    rot=self.rotation,
                )


@dataclass
class CardOutput:
    """A card output, vaguely inspired by slay the spire."""

    name: Annotated[str, "The name of the card, vaguely inspired by slay the spire."]
    description: Annotated[
        str,
        "The description of the card, vaguely inspired by slay the spire. The description should always reflect the name. If the name has changed, redesign the description. Align your description *strongly* with the name.",
    ]


@promptly()
def run_card_as_input(
    input_card: Card,
    arg_card: Card,
) -> CardOutput:
    """
    Your goal is to act as a virtual DM to interpret and resolve the player's cards.

    This game is inspired by Slay the Spire. If you don't know:

    > In Slay the Spire, players use a deck of cards to battle enemies. Each turn, the player draws a hand of cards and can play them using their available energy. Cards can attack, block, or apply various effects. Blocking adds temporary shield points to absorb incoming damage. At the end of the turn, enemies execute their intents, which can include attacking, defending, or applying status effects. The goal is to reduce the enemies' health to zero while managing the player's health and resources effectively.

    The player has used the following card (the "function"):

    {{ input_card.name }}: {{ input_card.description }}

    on the following card (the "input" to the function):

    {{ arg_card.name }}: {{ arg_card.description }}

    Your goal is to return the result of the player's action, and design the result card accordingly.
    Faithfully interpret the player's action and the input card. For example, if the function card
    asks to slash one of the input card's letters, literally remove the letter and redesign the card.
    E.g., Running letter remover on "Apple" creates "pple", and design "pple" accordingly.
    E.g., if "Apple" heals the player for 3, then "Pple", while not a valid word, might sound like
    "People", and thus might be interpreted as the "might of the people" (internally), and thus
    buffs the player's damage or defense.

    However, if the new card's name has changed, its description should reflect the new name.
    Be an excellent inner GM and design the card as if it is a normal slay-the-spire game!

    Remember, your result card's description should change game-play wise compared to the original.
    Ideally, the description should *completely change* if possible. Don't keep any original text.
    For example, "{{ arg_card.description }}" should not appear in the output description.

    {{ formatting_instructions }}
    """


@module_scene
class SceneIntro(Scene):
    card_sprites: list[RagdollCardSprite]
    mailbox: deque[Future[CardOutput]]

    def __init__(self) -> None:
        self.video = Video("background/*.png")
        self.card_sprites = []
        self.card_printer = CardPrinter()

        card0 = Card("Slash", "Deal 2 damage to a target.")

        self.card_sprites.append(
            RagdollCardSprite(
                WINDOW_WIDTH // 2 - CARD_WIDTH // 2,
                WINDOW_HEIGHT // 2 - CARD_HEIGHT // 2 - 20,
                card0,
                self.card_printer,
            )
        )

        self.mailbox = deque()

        self.anims = []

        self.framing = ResolvingFraming(self)

        self.tooltip = Tooltip("", "")
        self.tweener = Tweener()
        self.executor = ThreadPoolExecutor()
        self.sequence = 0

    def request_next_scene(self) -> Scene | None | str:
        if pyxel.btnp(pyxel.KEY_Q):
            return "genio.scene_blank"

    def update(self) -> None:
        self.video.update()
        self.tweener.update()
        self.framing.update()
        for card_sprite in self.card_sprites:
            card_sprite.update()
            if card_sprite.hovering:
                self.tooltip.pump_energy(
                    card_sprite.card.name, card_sprite.card.description or ""
                )
        self.tooltip.update()

        for anim in self.anims:
            anim.update()
        self.anims = [anim for anim in self.anims if not anim.dead]

        if self.mailbox:
            if self.mailbox[0].done():
                output = self.mailbox.popleft().result()
                self.transform_the_card(Card(output.name, output.description))

        if pyxel.btnp(pyxel.KEY_SPACE):
            self.sequence += 1
            methods = {
                1: self.movement_1,
                2: self.movement_2,
            }
            methods[self.sequence]()

    def draw(self) -> None:
        pyxel.cls(0)
        self.video.draw_image()

        for card_sprite in self.card_sprites:
            card_sprite.draw()

        self.tooltip.draw()

        for anim in self.anims:
            anim.draw_myself()
        Anim.draw()
        self.framing.draw()
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def movement_1(self) -> None:
        self.tweener.append_mutate(
            self.card_sprites[0], "x", 12, self.card_sprites[0].x + 30, "ease_in_quad"
        )
        self.tweener.append(Instant(self.create_another_card))

    def movement_2(self) -> None:
        self.framing.putup()
        self.tweener.append(
            range(15),
            Instant(
                self.pre_transform_the_card,
            ),
        )

    def pre_transform_the_card(self) -> None:
        card0 = self.card_sprites[0].card
        card1 = self.card_sprites[1].card

        self.mailbox.append(self.executor.submit(run_card_as_input, card1, card0))

    def transform_the_card(self, card: Card) -> None:
        self.card_sprites[0].becomes(card)
        self.card_sprites[0].flash()
        for _ in range(3):
            self.add_anim(
                "anims.transform_card", -1, -1, attached_to=self.card_sprites[0]
            )
        self.tweener.append(
            range(15),
            Instant(
                self.framing.teardown,
            ),
        )

    def create_another_card(self) -> None:
        card1 = Card(
            "Letter Remover",
            "Remove a letter from the target card's name, prioritizes the first letter.",
        )
        self.card_sprites.append(
            RagdollCardSprite(
                WINDOW_WIDTH // 2 - CARD_WIDTH // 2 - 30,
                WINDOW_HEIGHT // 2 - CARD_HEIGHT // 2 - 20,
                card1,
                self.card_printer,
            )
        )

    def draw_crosshair(self, x, y):
        cursor = load_image("cursor.png")
        pyxel.blt(x, y, cursor, 0, 0, 16, 16, colkey=254)

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
