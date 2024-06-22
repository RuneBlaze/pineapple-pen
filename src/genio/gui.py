from __future__ import annotations

import pyxel
from pyxelunicode import PyxelUnicode

from genio.battle import (
    Card,
    CardBundle,
    EnemyBattler,
    PlayerBattler,
    setup_battle_bundle,
)
from genio.core.base import slurp_toml

predef = slurp_toml("assets/strings.toml")

# Initialize pyuni at the module level
pyuni = PyxelUnicode("assets/Roboto-Medium.ttf", 14)
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
        self.color = app.CARD_COLOR
        self.selected = selected
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

    def draw(self):
        if self.selected:
            pyxel.rectb(self.x - 2, self.y - 2, self.width + 4, self.height + 4, 8)
        pyxel.rect(self.x, self.y, self.width, self.height, self.color)
        pyuni.text(self.x + 5, self.y + 10, self.card.name, 7)

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
            self.color = 12  # Change color on hover
        else:
            self.color = self.app.CARD_COLOR  # Default color

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


class App:
    CARD_WIDTH = 40
    CARD_HEIGHT = 60
    CARD_COLOR = 11
    GRID_X_START = 10
    GRID_Y_START = 180
    GRID_SPACING_X = 50
    GRID_SPACING_Y = 10
    TOTAL_CARDS = 6
    TWEEN_SPEED = 0.2

    card_bundle: CardBundle

    def __init__(self):
        pyxel.init(320, 240)
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
        self.bundle.card_bundle.hand_to_graveyard(selected_cards)
        self.resolve_selected_cards(selected_cards)

    def resolve_selected_cards(self, selected_cards: list[Card]):
        self.bundle.resolve_player_cards(selected_cards)

    def draw(self):
        pyxel.cls(0)
        for card in self.card_sprites:
            card.draw()

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        pyxel.line(mx - 5, my, mx + 5, my, 7)
        pyxel.line(mx, my - 5, mx, my + 5, 7)

        pyuni.text(5, 5, f"Deck: {len(self.bundle.card_bundle.deck)}", 7)
        pyuni.text(5, 15, f"Graveyard: {len(self.bundle.card_bundle.graveyard)}", 7)

        for i, battler in enumerate(self.bundle.battlers()):
            if isinstance(battler, PlayerBattler):
                str_repr = f"{battler.name}: HP {battler.hp} S {battler.shield_points}"
            elif isinstance(battler, EnemyBattler):
                str_repr = f"{battler.name}: HP {battler.hp} S {battler.shield_points} Intent: {battler.current_intent}"
            else:
                str_repr = f"{battler.name}"
            logtext.text(
                5,
                30 + i * 12,
                str_repr,
                7,
            )

    def end_player_turn(self):
        self.bundle.end_player_turn()


app = App()
