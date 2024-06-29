from __future__ import annotations

import contextlib
import functools
import random
from itertools import cycle
from typing import Literal

import numpy as np
import pyxel
from pyxelxl import Font, LayoutOpts, blt_rot, layout
from pyxelxl.font import _image_as_ndarray

from genio.base import asset_path
from genio.battle import (
    Battler,
    CardBundle,
    PlayerBattler,
    setup_battle_bundle,
)
from genio.card import Card
from genio.predef import access_predef, refresh_predef
from genio.ps import Anim
from genio.semantic_search import SerializedCardArt, search_closest_document

WINDOW_WIDTH, WINDOW_HEIGHT = 427, 240


# predef = slurp_toml("assets/strings.toml")

retro_text = Font(asset_path("retro-pixel-petty-5h.ttf")).specialize(font_size=5)
display_text = Font("assets/DMSerifDisplay-Regular.ttf").specialize(
    font_size=18, threshold=100
)
cute_text = Font("assets/retro-pixel-cute-prop.ttf").specialize(font_size=11)


def center_crop(img: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    # size in h, w
    # img in h, w, c
    h, w = img.shape[:2]
    if h < size[0] or w < size[1]:
        raise ValueError("Image is smaller than the crop size")
    x = (w - size[1]) // 2
    y = (h - size[0]) // 2
    return img[y : y + size[0], x : x + size[1]]


def paste_center(src: np.ndarray, target: np.ndarray, offset: int = 0) -> None:
    x = (target.shape[1] - src.shape[1]) // 2
    y = (target.shape[0] - src.shape[0]) // 2
    target[y + offset : y + src.shape[0] + offset, x : x + src.shape[1]] = src[:]


def ndarray_to_image(img: np.ndarray) -> pyxel.Image:
    image = pyxel.Image(img.shape[1], img.shape[0])
    data_ptr = image.data_ptr()
    np.frombuffer(data_ptr, dtype=np.uint8)[:] = img.flatten()
    return image


class CardArtSet:
    unfaded: np.ndarray
    faded: np.ndarray

    def __init__(self, base_image: pyxel.Image, document: SerializedCardArt) -> None:
        self.unfaded = document.unfaded
        self.faded = document.unfaded
        self.base_image = base_image

    def imprint(self, card_name: str, rarity: Literal[0, 1, 2]) -> pyxel.Image:
        w, h = self.base_image.width, self.base_image.height
        base = _image_as_ndarray(self.base_image)
        buffer = np.full((h, w), 254, dtype=np.uint8)
        buffer[:] = base
        buffer[buffer == 0] = 254
        if rarity >= 1:
            center_crop_size = (60 - 2 * 2, 43 - 2 * 2)
            unfaded_cropped = center_crop(self.unfaded, center_crop_size)
            paste_center(unfaded_cropped, buffer)
            buffer[2, 2] = 7
            buffer[2, 40] = 7
            buffer[57, 2] = 7
            buffer[57, 40] = 7
        else:
            center_crop_size = (30, 43 - 2 * 4)
            faded_cropped = center_crop(self.faded, center_crop_size)
            paste_center(faded_cropped, buffer, offset=2)
        img = ndarray_to_image(buffer)
        self._print_card_name(img, card_name, rarity)
        return img

    def _print_card_name(self, image: pyxel.Image, card_name: str, rarity: int) -> None:
        shadowed_retro_text = functools.partial(
            retro_text,
            s=card_name,
            layout=layout(w=33, ha="center", break_words=True),
            target=image,
        )
        if rarity >= 1:
            shadowed(shadowed_retro_text, 5, 10 - 2, 7)
        else:
            retro_text(
                5,
                10 - 2,
                card_name,
                0,
                layout=layout(w=33, ha="center", break_words=True),
                target=image,
            )


def shadowed(fn, x, y, col):
    for dx, dy in [[1, 0], [-1, 0], [0, 1], [0, -1]]:
        fn(dx + x, dy + y, col=0)
    fn(x, y, col=col)


def clip_magnitude(x, max_magnitude):
    return max(-max_magnitude, min(max_magnitude, x))


class Peekable:
    def __init__(self, iterable):
        self.iterator = iter(iterable)
        self._next = next(self.iterator, None)

    def __iter__(self):
        return self

    def __next__(self):
        if self._next is None:
            raise StopIteration
        result = self._next
        self._next = next(self.iterator, None)
        return result

    def peek(self):
        return self._next


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
        base_image = pyxel.Image(43, 60)
        base_image.blt(0, 0, 0, 0, 0, 43, 60, colkey=0)
        self.card_art = CardArtSet(base_image, search_closest_document(card.name))
        self.is_rare = rarity = bool(card.description)
        self.image = self.card_art.imprint(card.name, int(rarity))

    def draw(self):
        if self.index >= self.deck_length:
            return
        angle = fan_out_for_N(self.deck_length)[self.index]
        blt_rot(
            self.x,
            self.y,
            self.image,
            0,
            0,
            self.width,
            self.height,
            colkey=0,
            rot=angle,
        )
        pyxel.pal()
        if not self.selected and any(
            card for card in self.app.card_sprites if card.selected
        ):
            with pal_single_color(5):
                with dithering(0.5):
                    blt_rot(
                        self.x,
                        self.y,
                        self.image,
                        0,
                        0,
                        self.width,
                        self.height,
                        colkey=0,
                        rot=angle,
                    )

    @property
    def deck_length(self) -> int:
        return len(self.app.bundle.card_bundle.hand)

    def is_mouse_over(self):
        return (
            self.x <= pyxel.mouse_x <= self.x + self.width
            and self.y <= pyxel.mouse_y <= self.y + self.height
        )

    def update(self):
        if self.index >= self.deck_length:
            for i, card in enumerate(self.app.card_sprites):
                card.change_index(i)
            return
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
            target_x, target_y = self.adjusted_target_coords()
            dx = (target_x - self.x) * self.app.TWEEN_SPEED
            dy = (target_y - self.y) * self.app.TWEEN_SPEED
            dx = clip_magnitude(dx, 13)
            dy = clip_magnitude(dy, 13)

            self.x += dx
            self.y += dy

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
        self.target_x, self.target_y = self.calculate_target_coords()

    def adjusted_target_coords(self) -> tuple[int, int]:
        x, y = self.calculate_target_coords()
        return x, y - 10 if self.selected else y

    def calculate_target_coords(self) -> tuple[int, int]:
        fanout = fan_out_for_N(self.deck_length)[min(self.index, self.deck_length - 1)]
        return (
            self.app.GRID_X_START + self.index * self.app.GRID_SPACING_X,
            self.app.GRID_Y_START + pyxel.sin(abs(fanout)) * 60,
        )


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
    shadowed_text(x + 2, y + 2, text, 7, layout_opts=layout(w=w, ha="left"))


def shadowed_text(
    x, y, text, color, layout_opts: LayoutOpts | None = None, dither_mult: float = 1.0
):
    pyxel.dither(0.5 * dither_mult)
    retro_text(x + 1, y + 1, text, 0, layout=layout_opts)
    pyxel.dither(1.0 * dither_mult)
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
            cute_text(
                amx - 50,
                amy - offset + 5,
                self.title,
                7,
                layout=layout(w=100, ha="left"),
            )
            if self.description:
                retro_text(
                    amx - 50,
                    amy - offset + 20,
                    self.description,
                    7,
                    layout=layout(w=100, ha="left"),
                )

    def update(self):
        self.counter -= 3
        if self.counter <= 0:
            self.title = ""
            self.description = ""

    def reset(self, title: str, description: str):
        self.title = title
        self.description = description
        self.counter = 60


@contextlib.contextmanager
def pal_single_color(col: int):
    for i in range(16):
        pyxel.pal(i, col)
    yield
    pyxel.pal()


camera_stack = []


@contextlib.contextmanager
def camera_shift(x: int, y: int):
    global camera_stack
    base_coord = camera_shift[-1] if camera_stack else (0, 0)
    pyxel.camera(x + base_coord[0], y + base_coord[1])
    camera_stack.append((x, y))
    yield
    camera_stack.pop()
    pyxel.camera(base_coord[0], base_coord[1])


def button(
    x: int, y: int, w: int, h: int, text: str, color: int, hover_color: int
) -> None:
    if x <= pyxel.mouse_x <= x + w and y <= pyxel.mouse_y <= y + h:
        pyxel.rect(x, y, w, h, hover_color)
    else:
        pyxel.rect(x, y, w, h, color)
    pyxel.rectb(x, y, w, h, 0)
    retro_text(x + 2, y + 2, text, 0, layout=layout(w=w, h=h, ha="center", va="center"))
    retro_text(x, y, text, 7, layout=layout(w=w, h=h, ha="center", va="center"))


class DrawDeck:
    def __init__(self, card_bundle: CardBundle):
        self.deck_background = pyxel.Image.from_image(asset_path("card-back.png"))
        self.card_bundle = card_bundle

    def draw(self, x: int, y: int) -> None:
        num_shadow = max(1, len(self.card_bundle.deck) // 5)
        if len(self.card_bundle.deck) == 1:
            num_shadow = 0
        with pal_single_color(13):
            for i in range(num_shadow):
                pyxel.blt(
                    x - i - 1, y + i + 1, self.deck_background, 0, 0, 43, 60, colkey=0
                )
        pyxel.blt(x, y, self.deck_background, 0, 0, 43, 60, colkey=0)
        width = 43
        label_width = 22
        label_x = x + (width - label_width) // 2
        label_y = y - 3
        pyxel.rect(label_x, label_y, label_width, 7, 7)
        retro_text(
            label_x,
            label_y,
            str(len(self.card_bundle.deck)),
            0,
            layout=layout(w=label_width, ha="center", h=7, va="center"),
        )


@functools.cache
def calculate_fan_out_angles_symmetry(
    N: int, max_angle: int, max_difference: int
) -> list[int]:
    if N == 0:
        return []

    angles = [0] * N
    middle_index = N // 2

    # Generate angles for one side
    for i in range(1, middle_index + 1):
        target_angle = min(i * max_difference, max_angle)
        angles[middle_index - i] = -target_angle  # Left side
        angles[
            middle_index + (i - 1) + (0 if N % 2 == 0 else 0)
        ] = target_angle  # Right side

    return angles


fan_out_for_N = functools.partial(
    calculate_fan_out_angles_symmetry, max_angle=15, max_difference=1.5
)


class Popup:
    def __init__(self, text: str, x: int, y: int, color: int):
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.counter = 60
        self.dx = random.randint(-10, 10)
        self.dy = random.randint(-65, -55)

    def draw(self):
        if self.counter <= 0:
            return
        t = 1 - self.counter / 60
        t = t**0.8
        if self.counter >= 45:
            if self.counter % 10 <= 5:
                pyxel.pal(self.color, 10)
        shadowed_text(
            self.x + self.dx * t,
            self.y + self.dy * t,
            self.text,
            self.color,
            layout_opts=layout(w=30, h=20, ha="center", va="center"),
            dither_mult=(1 - t) if self.counter <= 30 else 1.0,
        )
        pyxel.pal()

    def update(self):
        self.counter -= 1


class App:
    CARD_WIDTH = 43
    CARD_HEIGHT = 60
    CARD_COLOR = 7
    GRID_X_START = 85
    GRID_Y_START = 180
    GRID_SPACING_X = 40
    GRID_SPACING_Y = 10
    TOTAL_CARDS = 6
    TWEEN_SPEED = 0.5

    card_bundle: CardBundle
    anims: list[Anim]

    def __init__(self):
        pyxel.init(427, 240, title="Genio")
        pyxel.load("/Users/lbq/goof/genio/assets/sprites.pyxres")
        self.bundle = setup_battle_bundle(
            "initial_deck", "players.starter", ["enemies.slime"] * 2
        )
        self.card_sprites = []
        self.sync_sprites()
        self.tooltip = Tooltip("", "")
        self.draw_deck = DrawDeck(self.bundle.card_bundle)
        self.anims = []
        self.popups = []
        self.timer = 0
        self.particle_configs = Peekable(cycle(access_predef("anims").items()))
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

        if pyxel.btnr(pyxel.KEY_R):
            refresh_predef()
            self.particle_configs = Peekable(cycle(access_predef("anims").items()))
            print(self.particle_configs.peek())

        if pyxel.btnp(pyxel.KEY_E):
            next(self.particle_configs)

        self.tooltip.update()
        for anim in self.anims:
            anim.update()
        for popup in self.popups:
            popup.update()
        if self.timer % 30 == 0:
            self.add_anim(self.particle_configs.peek()[1], 100, 100, 1.0)
            self.add_popup("Hello", 100, 100, 11)
        self.anims = [anim for anim in self.anims if not anim.dead]
        self.timer += 1

    def play_selected(self):
        selected_card_sprites = [card for card in self.card_sprites if card.selected]
        if not selected_card_sprites:
            return
        selected_cards = [card.card for card in selected_card_sprites]
        self.bundle.card_bundle.hand_to_resolving(selected_cards)
        self.resolve_selected_cards(selected_cards)

    def add_anim(self, name: str, x: int, y: int, play_speed: float = 1.0):
        self.anims.append(Anim.from_predef(name, x, y, play_speed))

    def resolve_selected_cards(self, selected_cards: list[Card]):
        self.bundle.resolve_player_cards(selected_cards)

    def add_popup(self, text: str, x: int, y: int, color: int):
        self.popups.append(Popup(text, x, y, color))

    def draw_battler(self, battler: Battler, x: int, y: int) -> None:
        pyxel.blt(x, y, 0, 0, 64, self.CARD_HEIGHT, self.CARD_WIDTH, colkey=0)
        pyxel.pal()
        first_line = f"{battler.name_stem}"
        if battler.status_effects:
            first_line += " " + " ".join(
                f"({status.name} {status.counter})" for status in battler.status_effects
            )
        pyxel.camera(-9, -35)
        pyxel.dither(0.5)
        display_text(x + 1, y + 1, first_line, 0, threshold=70)
        pyxel.dither(1.0)
        display_text(x, y, first_line, 7, threshold=70)
        gauge(
            x,
            y + 20,
            w=40,
            h=7,
            c0=4,
            c1=8,
            value=battler.hp,
            max_value=battler.max_hp,
            label="HP",
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
        self.draw_deck.draw(10, 190)
        for card in self.card_sprites:
            card.draw()

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

        button(WINDOW_WIDTH - 70, WINDOW_HEIGHT - 20, 55, 15, "End Turn", 7, 5)
        button(WINDOW_WIDTH - 70, WINDOW_HEIGHT - 50, 55, 15, "Play Cards", 7, 5)
        self.tooltip.draw()
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)
        if self.anims:
            self.anims[0].draw()
        for popup in self.popups:
            popup.draw()
        current_name = self.particle_configs.peek()[0]
        shadowed_text(5, 5, current_name, 7)

    def draw_crosshair(self, x, y):
        pyxel.line(x - 5, y, x + 5, y, 7)
        pyxel.line(x, y - 5, x, y + 5, 7)

    def end_player_turn(self):
        self.bundle.end_player_turn()


app = App()
