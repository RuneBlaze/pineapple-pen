from __future__ import annotations

import contextlib
import math

import numpy as np
import pyxel
from pyxelxl import Font, LayoutOpts, layout

from genio.battle import (
    Battler,
    CardBundle,
    PlayerBattler,
    setup_battle_bundle,
)
from genio.card import Card
from genio.core.base import slurp_toml

predef = slurp_toml("assets/strings.toml")

retro_text = Font("assets/retro-pixel-petty-5h.ttf").specialize(font_size=5)
display_text = Font("assets/DMSerifDisplay-Regular.ttf").specialize(
    font_size=18, threshold=100
)
cute_text = Font("assets/retro-pixel-cute-prop.ttf").specialize(font_size=11)


class CardSprite:
    def __init__(self, index, card: Card, app: App, selected=False):
        self.index = index
        self.app = app
        self.change_index(index)
        self.x = self.target_x
        self.y = self.target_y
        self.card = card
        self.width = app.CARD_WIDTH
        self.height = app.CARD_HEIGHT
        self.hovered = False
        self.selected = selected
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

    def draw(self):
        if self.selected:
            pyxel.rectb(self.x - 2, self.y - 2, self.width + 4, self.height + 4, 8)
        pyxel.blt(self.x, self.y, 0, 0, 0, self.width, self.height, colkey=0)
        if not self.hovered:
            pyxel.dither(0.5)
            pyxel.fill(self.x + 10, self.y + 10, 3)
            pyxel.dither(1.0)
        retro_text(self.x + 5, self.y + 10, self.card.name, 0)

    def is_mouse_over(self):
        return (
            self.x <= pyxel.mouse_x <= self.x + self.width
            and self.y <= pyxel.mouse_y <= self.y + self.height
        )

    def update(self):
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if self.is_mouse_over():
                self.dragging = True
                self.drag_offset_x = pyxel.mouse_x - self.x
                self.drag_offset_y = pyxel.mouse_y - self.y
                self.selected = not self.selected

        if pyxel.btnr(pyxel.MOUSE_BUTTON_LEFT):
            if self.dragging:
                self.dragging = False
                self.snap_to_grid()

        if self.dragging:
            self.x = pyxel.mouse_x - self.drag_offset_x
            self.y = pyxel.mouse_y - self.drag_offset_y

        # Tweening for smooth transition
        if not self.dragging:
            self.x += (self.target_x - self.x) * self.app.TWEEN_SPEED
            self.y += (self.target_y - self.y) * self.app.TWEEN_SPEED

        if self.is_mouse_over():
            self.hovered = True
            self.app.tooltip.reset(self.card.name, self.card.description or "")
        else:
            self.hovered = False

    def snap_to_grid(self):
        new_index = (
            int(self.x) - self.app.GRID_X_START + self.app.GRID_SPACING_X // 2
        ) // self.app.GRID_SPACING_X
        new_index = max(0, min(self.app.TOTAL_CARDS - 1, new_index))

        self.app.card_sprites.remove(self)
        self.app.card_sprites.insert(new_index, self)

        for i, card in enumerate(self.app.card_sprites):
            card.change_index(i)

    def change_index(self, new_index: int):
        self.index = new_index
        self.target_x = self.app.GRID_X_START + new_index * self.app.GRID_SPACING_X
        self.target_y = self.app.GRID_Y_START


def vertical_gradient(x, y, w, h, c0, c1):
    num_chunks = 12
    chunks = np.linspace(y, y + h, num_chunks)
    dithering = np.linspace(0, 1, num_chunks)
    pyxel.rect(x, y, w, h, c0)
    for i in range(num_chunks - 1):
        pyxel.rect(x, int(chunks[i]), w, int(chunks[i + 1]) - int(chunks[i]), c1)
        pyxel.dither(1.0 - dithering[i + 1])
    pyxel.dither(1.0)


def horizontal_gradient(x, y, w, h, c0, c1):
    num_chunks = 12
    chunks = np.linspace(x, x + w, num_chunks)
    dithering = np.linspace(0, 1, num_chunks)
    pyxel.rect(x, y, w, h, c0)
    for i in range(num_chunks - 1):
        pyxel.rect(int(chunks[i]), y, int(chunks[i + 1]) - int(chunks[i]), h, c1)
        pyxel.dither(1.0 - dithering[i + 1])
    pyxel.dither(1.0)


def gauge(x, y, w, h, c0, c1, value, max_value, label=None):
    pyxel.rect(x, y, w, h, c0)
    pyxel.rect(x, y, min(w * value // max_value, w), h, c1)
    pyxel.dither(0.5)
    pyxel.rectb(x, y, w, h, 0)
    pyxel.dither(1.0)
    text = f"{value}/{max_value}"
    if label:
        text = f"{label} {text}"
    shadowed_text(
        x + 2, y + 2, text, 7, layout_opts=layout(w=w, ha="left")
    )


def shadowed_text(x, y, text, color, layout_opts: LayoutOpts | None = None):
    pyxel.dither(0.5)
    retro_text(x + 1, y + 1, text, 0, layout=layout_opts)
    pyxel.dither(1.0)
    retro_text(x, y, text, color, layout=layout_opts)


@contextlib.contextmanager
def dithering(f: float):
    pyxel.dither(f)
    yield
    pyxel.dither(1.0)


class Tooltip:
    def __init__(self, title: str, description: str):
        self.title = title
        self.description = description
        self.counter = 60

    def draw(self):
        if (not self.title and not self.description) or self.counter <= 0:
            return
        # Draw on mouse, and fade with counter if counter < 50
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        amx, amy = mx, my
        t = 0.6
        amx = mx * t + ((1 - t) * pyxel.width / 2)
        amy = my * t + ((1 - t) * pyxel.height / 2)
        dither_amount = 1.0 if self.counter > 50 else (self.counter / 50) ** 2
        with dithering(dither_amount):
            rect_width = 125
            rect_height = 60
            offset = 60
            pyxel.rect(amx - rect_width // 2, amy - offset, rect_width, rect_height, 0)
            pyxel.tri(
                mx,
                my,
                amx - 10,
                amy - offset,
                amx + 10,
                amy - offset,
                0,
            )
            cute_text(amx - 50, amy - offset + 5, self.title, 7, layout = layout(w=100, ha="left"))
            if self.description:
                retro_text(amx - 50, amy - offset + 20, self.description, 7, layout = layout(w=100, ha="left"))

    def update(self):
        self.counter -= 3
        if self.counter <= 0:
            self.title = ""
            self.description = ""

    def reset(self, title: str, description: str):
        self.title = title
        self.description = description
        self.counter = 60


class App:
    CARD_WIDTH = 43
    CARD_HEIGHT = 60
    CARD_COLOR = 7
    GRID_X_START = 10
    GRID_Y_START = 180
    GRID_SPACING_X = 50
    GRID_SPACING_Y = 10
    TOTAL_CARDS = 6
    TWEEN_SPEED = 0.2

    card_bundle: CardBundle

    def __init__(self):
        pyxel.init(427, 240, title="Genio")
        pyxel.load("/Users/lbq/goof/genio/assets/sprites.pyxres")
        self.bundle = setup_battle_bundle(
            "initial_deck", "players.starter", ["enemies.slime"] * 2
        )
        self.card_sprites = []
        self.sync_sprites()
        self.tooltip = Tooltip("", "")
        pyxel.run(self.update, self.draw)

    def sync_sprites(self):
        existing_card_sprites = {
            card_sprite.card.id: card_sprite for card_sprite in self.card_sprites
        }
        self.card_sprites = [
            existing_card_sprites.get(card.id, CardSprite(i, card, self))
            for i, card in enumerate(self.bundle.card_bundle.hand)
        ]

        for i, card_sprite in enumerate(self.card_sprites):
            card_sprite.change_index(i)

    def reorder_card_as_sprites(self):
        # sprites might be reordered, so we reorder the cards too
        self.bundle.card_bundle.hand = [
            card_sprite.card for card_sprite in self.card_sprites
        ]

    def update(self):
        while self.bundle.card_bundle.events:
            _ev = self.bundle.card_bundle.events.pop()
            self.sync_sprites()

        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        if pyxel.btnp(pyxel.KEY_SPACE):
            self.play_selected()

        if pyxel.btnp(pyxel.KEY_Z):
            self.end_player_turn()

        for card in self.card_sprites:
            card.update()

        self.tooltip.update()

    def play_selected(self):
        selected_card_sprites = [card for card in self.card_sprites if card.selected]
        if not selected_card_sprites:
            return
        selected_cards = [card.card for card in selected_card_sprites]
        self.bundle.card_bundle.hand_to_resolving(selected_cards)
        self.resolve_selected_cards(selected_cards)

    def resolve_selected_cards(self, selected_cards: list[Card]):
        self.bundle.resolve_player_cards(selected_cards)

    def draw_battler(self, battler: Battler, x: int, y: int) -> None:
        pyxel.blt(x, y, 0, 0, 64, self.CARD_HEIGHT, self.CARD_WIDTH, colkey=0)
        pyxel.pal()
        first_line = f"{battler.name_stem}"
        if battler.status_effects:
            first_line += " " + " ".join(
                f"({status.name} {status.counter})" for status in battler.status_effects
            )
        second_line = f"HP: {battler.hp} S: {battler.shield_points}"
        third_line = (
            ""
            if isinstance(battler, PlayerBattler)
            else f"Intent: {battler.current_intent}"
        )
        offset = self.CARD_WIDTH + 5
        pyxel.camera(-9, -35)
        pyxel.dither(0.5)
        display_text(x + 1, y + 1, first_line, 0, threshold=70)
        pyxel.dither(1.0)
        display_text(x, y, first_line, 7, threshold=70)
        gauge(
            x, y + 20, w=40, h=7, c0=4, c1=8, value=battler.hp, max_value=battler.max_hp, label="HP"
        )
        latest_y = y + 20
        if isinstance(battler, PlayerBattler):
            gauge(
                x,
                y + 30,
                w=40,
                h=7,
                c0=1,
                c1=5,
                value=battler.mp,
                max_value=battler.max_mp,
                label="MP",
            )
            latest_y = y + 30
        gauge(
            x,
            latest_y + 10,
            w=40,
            h=7,
            c0=2,
            c1=6,
            value=battler.shield_points,
            max_value=battler.max_hp,
            label="S",
        )
        pyxel.camera()

    def draw(self):
        vertical_gradient(0, 0, 427, 240, 5, 12)
        for card in self.card_sprites:
            card.draw()

        # cutefont.text(5, 5, f"Deck: {len(self.bundle.card_bundle.deck)}", 7)
        # pyuni.text(5, 15, f"Graveyard: {len(self.bundle.card_bundle.graveyard)}", 7)

        num_players_seen = 0
        num_enemies_seen = 0
        for i, battler in enumerate(self.bundle.battlers()):
            if isinstance(battler, PlayerBattler):
                self.draw_battler(battler, 5, 30 + num_players_seen * 50)
                num_players_seen += 1
            else:
                self.draw_battler(
                    battler,
                    200 + 100 * (num_enemies_seen % 2),
                    30 + num_enemies_seen * 50,
                )
                num_enemies_seen += 1

        # mx, my = pyxel.mouse_x, pyxel.mouse_y
        # pyxel.line(mx - 5, my, mx + 5, my, 7)
        # pyxel.line(mx, my - 5, mx, my + 5, 7)
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)
        self.tooltip.draw()

    def draw_crosshair(self, x, y):
        pyxel.line(x - 5, y, x + 5, y, 7)
        pyxel.line(x, y - 5, x, y + 5, 7)

    def end_player_turn(self):
        self.bundle.end_player_turn()


app = App()
