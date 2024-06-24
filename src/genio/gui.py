from __future__ import annotations

import numpy as np
import pyxel
from pyxelunicode import PyxelUnicode

from genio.battle import (
    Battler,
    CardBundle,
    PlayerBattler,
    setup_battle_bundle,
)
from genio.card import Card
from genio.core.base import slurp_toml

predef = slurp_toml("assets/strings.toml")

# Initialize pyuni at the module level
pyuni = PyxelUnicode("assets/Roboto-Medium.ttf", 14)
# emoji = PyxelUnicode("/Users/lbq/goof/genio/assets/NotoColorEmoji.ttf", 109, multipler=1)
display = PyxelUnicode("/Users/lbq/goof/genio/assets/DMSerifDisplay-Regular.ttf", 18)
logtext = PyxelUnicode("assets/Roboto-Medium.ttf", 12)


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
        pyuni.text(self.x + 5, self.y + 10, self.card.name, color=0)

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


def gauge(x, y, w, h, c0, c1, value, max_value):
    pyxel.rect(x, y, w, h, c0)
    pyxel.rect(x, y, w * value // max_value, h, c1)
    pyxel.dither(0.5)
    pyxel.rectb(x, y, w, h, 0)
    pyxel.dither(1.0)
    pyxel.dither(0.5)
    pyxel.text(x + 3, y + 3, f"{value}/{max_value}", 0)
    pyxel.dither(1.0)
    pyxel.text(x + 2, y + 2, f"{value}/{max_value}", 7)


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
        pyxel.init(427, 240)
        pyxel.load("/Users/lbq/goof/genio/assets/sprites.pyxres")
        self.bundle = setup_battle_bundle(
            "initial_deck", "players.starter", ["enemies.slime"] * 2
        )
        self.card_sprites = []
        self.sync_sprites()
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
        # pyxel.pal(6, 9)
        # pyxel.pal(7, 15)
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
        display.text(x + 1, y + 1, first_line, 0)
        pyxel.dither(1.0)
        display.text(x, y, first_line, 7)
        gauge(
            x, y + 20, w=40, h=7, c0=4, c1=8, value=battler.hp, max_value=battler.max_hp
        )
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
            )
        pyxel.camera()
        # logtext.text(x, y + 12 + offset, second_line, 7)
        # logtext.text(x, y + 24 + offset, third_line, 7)

    def draw(self):
        vertical_gradient(0, 0, 427, 240, 5, 12)
        for card in self.card_sprites:
            card.draw()

        pyuni.text(5, 5, f"Deck: {len(self.bundle.card_bundle.deck)}", 7)
        pyuni.text(5, 15, f"Graveyard: {len(self.bundle.card_bundle.graveyard)}", 7)

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
            # break
            # emoji.text(5, 30 + i * 37 + 12, "🚘", 7)
            # break
            # if isinstance(battler, PlayerBattler):
            #     str_repr = f"[{battler.name_stem}]: HP {battler.hp} S {battler.shield_points}"
            # elif isinstance(battler, EnemyBattler):
            #     str_repr = f"[{battler.name}]: HP {battler.hp} S {battler.shield_points} Intent: {battler.current_intent}"
            # else:
            #     str_repr = f"{battler.name}"
            # logtext.text(
            #     5,
            #     30 + i * 12,
            #     str_repr,
            #     7,
            # )

        # mx, my = pyxel.mouse_x, pyxel.mouse_y
        # pyxel.line(mx - 5, my, mx + 5, my, 7)
        # pyxel.line(mx, my - 5, mx, my + 5, 7)
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def draw_crosshair(self, x, y):
        pyxel.line(x - 5, y, x + 5, y, 7)
        pyxel.line(x, y - 5, x, y + 5, 7)

    def end_player_turn(self):
        self.bundle.end_player_turn()


app = App()
