import pyxel
from pyxelunicode import PyxelUnicode

from genio.battle import (
    BattleBundle,
    BattlePrelude,
    Card,
    CardBundle,
    EnemyBattler,
    PlayerBattler,
)
from genio.core.base import slurp_toml

predef = slurp_toml("assets/strings.toml")

# Initialize pyuni at the module level
pyuni = PyxelUnicode("assets/Roboto-Medium.ttf", 14)
logtext = PyxelUnicode("assets/Roboto-Medium.ttf", 12)


class CardSprite:
    def __init__(self, index, card: Card, app, selected=False):
        self.index = index
        self.target_x = app.GRID_X_START + index * app.GRID_SPACING_X
        self.target_y = app.GRID_Y_START
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
        self.app = app

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

        self.app.cards.remove(self)
        self.app.cards.insert(new_index, self)

        for i, card in enumerate(self.app.cards):
            card.index = i
            card.target_x = self.app.GRID_X_START + i * self.app.GRID_SPACING_X
            card.target_y = self.app.GRID_Y_START


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

    def __init__(self):
        pyxel.init(320, 240)
        card_bundle = CardBundle.from_predef("initial_deck")
        card_bundle.draw_to_hand()
        player = PlayerBattler.from_predef("players.starter")
        enemy1 = EnemyBattler.from_predef("enemies.slime", 1)
        enemy2 = EnemyBattler.from_predef("enemies.slime", 2)
        self.bundle = BattleBundle(
            player, [enemy1, enemy2], BattlePrelude.default(), card_bundle
        )
        self.init_sprites()
        pyxel.run(self.update, self.draw)

    def init_sprites(self):
        self.cards = [
            CardSprite(i, card, self)
            for i, card in enumerate(self.bundle.card_bundle.hand)
        ]

    def update(self):
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        if pyxel.btnp(pyxel.KEY_SPACE):
            self.play_selected()

        for card in self.cards:
            card.update()

    def play_selected(self):
        selected_card_sprites = [card for card in self.cards if card.selected]
        if not selected_card_sprites:
            return
        selected_cards = [card.card for card in selected_card_sprites]
        self.cards = [card for card in self.cards if not card.selected]
        self.resolve_selected_cards(selected_cards)

    def resolve_selected_cards(self, selected_cards: list[Card]):
        self.bundle.resolve_player_cards(selected_cards)

    def draw(self):
        pyxel.cls(0)
        for card in self.cards:
            card.draw()

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        pyxel.line(mx - 5, my, mx + 5, my, 7)
        pyxel.line(mx, my - 5, mx, my + 5, 7)

        pyuni.text(5, 5, f"Deck: {len(self.bundle.card_bundle.deck)}", 7)
        pyuni.text(5, 15, f"Graveyard: {len(self.bundle.card_bundle.graveyard)}", 7)

        for i, battler in enumerate(self.bundle.battlers()):
            logtext.text(
                5,
                30 + i * 12,
                f"{battler.name}: HP {battler.hp} S {battler.shield_points}",
                7,
            )

    def draw_bundle(self):
        ...


app = App()
