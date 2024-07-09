from __future__ import annotations

import contextlib
import functools
import itertools
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Literal

import numpy as np
import pytweening
import pyxel
from pyxelxl import blt_rot, layout
from pyxelxl.font import _image_as_ndarray

from genio.base import Video, asset_path, load_image, resize_image_breathing
from genio.battle import (
    CardBundle,
    ResolvedEffects,
    setup_battle_bundle,
)
from genio.card import Card
from genio.components import Popup, cute_text, retro_font, retro_text, shadowed_text
from genio.effect import SinglePointEffect, SinglePointEffectType
from genio.layout import (
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    fan_out_for_N,
    layout_center_for_n,
    pingpong,
)
from genio.ps import Anim
from genio.scene import Scene
from genio.semantic_search import SerializedCardArt, search_closest_document
from genio.tween import Instant, MutableTweening, Mutator, Shake, Tweener
from genio.utils.weaklist import WeakList


def center_crop(img: np.ndarray, size: tuple[int, int]) -> np.ndarray:
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


def copy_image(image: pyxel.Image) -> pyxel.Image:
    img = pyxel.Image(image.width, image.height)
    _image_as_ndarray(img)[:] = _image_as_ndarray(image)[:]
    return img


class CardArtSet:
    unfaded: np.ndarray
    faded: np.ndarray

    def __init__(self, base_image: pyxel.Image, document: SerializedCardArt) -> None:
        self.unfaded = document.unfaded
        self.faded = document.unfaded
        self.base_image = base_image

    def imprint(self, card_name: str, rarity: Literal[0, 1, 2]) -> pyxel.Image:
        match card_name:
            case "3 of Spades":
                return load_image("cards", "three-of-spades.png")
            case "6 of Hearts":
                return load_image("cards", "six-of-hearts.png")
            case "4 of Diamonds":
                return load_image("cards", "four-of-diamonds.png")
            case "4 of Spades":
                return load_image("cards", "four-of-spades.png")
            case "The Fool":
                image = copy_image(load_image("cards", "the-fool.png"))
                self.add_retro_text_to_card("O", image)
                return image
            case "The Emperor":
                image = copy_image(load_image("cards", "the-emperor.png"))
                self.add_retro_text_to_card("IV", image)
                return image
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

    def add_retro_text_to_card(self, text: str, image: pyxel.Image) -> None:
        retro_text(
            0,
            2,
            text,
            col=7,
            layout=layout(w=MainScene.CARD_WIDTH, ha="center", break_words=True),
            target=image,
        )

    def add_flashcard_text_to_card(self, text: str, image: pyxel.Image) -> None:
        rasterized = retro_font.rasterize(
            text,
            5,
            255,
            0,
            7,
            layout=layout(
                w=MainScene.CARD_HEIGHT,
                ha="center",
                h=MainScene.CARD_WIDTH,
                va="center",
            ),
        )
        rasterized = np.rot90(rasterized)
        _image_as_ndarray(image)[rasterized == 0] = 0

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


def round_off_rating(number):
    return round(number * 2) / 2


class CardState(Enum):
    ACTIVE = 0
    RESOLVING = 1
    RESOLVED = 2
    INITIALIZE = 3


class CardSprite:
    def __init__(self, index, card: Card, app: MainScene, selected=False):
        self.index = index
        self.app = app
        self.change_index(index)
        # 10, 190
        self.x = 10
        self.y = 190
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
        self.state = CardState.INITIALIZE
        self.update_delay = 8 * index + 5
        self.tweens = Tweener()
        self.rotation = 0
        self.fade_timer = 0
        self.tweens.append(
            itertools.chain(
                MutableTweening(
                    12, pytweening.easeInOutQuad, self, (self.target_x, self.target_y)
                ),
                Instant(self.transition_to_active),
            )
        )

    def transition_to_active(self):
        self.state = CardState.ACTIVE

    def can_transition_to_resolving(self) -> bool:
        if self.state != CardState.ACTIVE:
            return False
        if self.dragging:
            return False
        return True

    def try_transition_to_resolving(self) -> None:
        if self.can_transition_to_resolving():
            self.state = CardState.RESOLVING
        else:
            raise ValueError("Cannot transition to resolving")

        num_total_cards = len(self.app.bundle.card_bundle.resolving)
        my_index = self.app.bundle.card_bundle.resolving.index(self.card)

        self.update_delay += my_index * 6
        self.index = 0

        target_x = layout_center_for_n(num_total_cards, 400)[my_index]
        target_y = WINDOW_HEIGHT // 2 - self.height // 2

        self.tweens.append(
            itertools.chain(
                range(4 * my_index),
                MutableTweening(
                    15, pytweening.easeInOutQuad, self, (target_x, target_y)
                ),
                range(4),
                Shake(self, 5, 15),
            )
        )

    def draw(self):
        if self.index >= self.deck_length:
            return
        if self.state == CardState.INITIALIZE:
            blt_rot(
                self.x,
                self.y,
                card_back(),
                0,
                0,
                self.width,
                self.height,
                colkey=0,
                rot=self.rotation,
            )
            return
        self.fade_timer += 1
        if self.fade_timer <= 5:
            blt_rot(
                self.x,
                self.y,
                card_back(),
                0,
                0,
                self.width,
                self.height,
                colkey=0,
                rot=self.rotation,
            )
        with dithering(min(round_off_rating(self.fade_timer / 5), 1)):
            blt_rot(
                self.x,
                self.y,
                self.image,
                0,
                0,
                self.width,
                self.height,
                colkey=254,
                rot=self.rotation,
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
                            colkey=254,
                            rot=self.rotation,
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
        if self.update_delay > 0:
            self.update_delay -= 1
            return

        if self.state == CardState.ACTIVE:
            self.update_active()

        self.tweens.update()

    def update_active(self):
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


def black_gradient(x, y, w, h) -> None:
    num_chunks = 5
    chunks = np.linspace(y, y + h, num_chunks)
    dithering = np.linspace(0, 1, num_chunks)
    for i in range(num_chunks - 1):
        pyxel.rect(x, int(chunks[i]), w, int(chunks[i + 1]) - int(chunks[i]), 0)
        pyxel.dither(1.0 - dithering[i + 1])
    pyxel.dither(1.0)


def black_gradient_inverse(x, y, w, h) -> None:
    num_chunks = 5
    chunks = np.linspace(y, y + h, num_chunks)
    dithering = np.linspace(1, 0, num_chunks)
    pyxel.dither(0.0)
    for i in range(num_chunks - 1):
        pyxel.rect(x, int(chunks[i]), w, int(chunks[i + 1]) - int(chunks[i]), 0)
        pyxel.dither(1.2 - dithering[i + 1])
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


class FlashState:
    def __init__(self):
        self.counter = 0

    def flash(self):
        self.counter = 35

    @contextlib.contextmanager
    def enter(self):
        yield self.is_flashing()
        self.counter -= 1
        self.counter = max(0, self.counter)

    def is_flashing(self):
        return self.counter >= 30 and self.counter % 5 <= 1


class WrappedImage:
    def __init__(
        self,
        image: int | pyxel.Image,
        u: int,
        v: int,
        w: int,
        h: int,
        scene: MainScene,
        has_breathing: bool = False,
        user_data: str = "",
    ) -> None:
        self.image = image
        self.u = u
        self.v = v
        self.w = w
        self.h = h
        self.flash_state = FlashState()
        self.scene = scene
        self.has_breathing = has_breathing
        self.breathing_versions = [self.image] + (
            [resize_image_breathing(image, i) for i in range(1, 3)]
            if has_breathing
            else []
        )
        self.x = 0
        self.y = 0
        self.width = w
        self.height = h
        self.pingpong = pingpong(len(self.breathing_versions) if has_breathing else 1)
        self.timer = 0
        self.rng = np.random.default_rng(seed=id(image))
        self.cycle = self.rng.integers(32, 45)
        self.wait = self.rng.integers(0, 30)
        self.user_data = user_data
        self.rotation = 0

    def draw(self, x: int | None = None, y: int | None = None) -> None:
        if x is None:
            x = self.x
        if y is None:
            y = self.y
        with self.flash_state.enter() as flash:
            pyxel.blt(x, y, self.image, self.u, self.v, self.w, self.h, colkey=254)
            if flash:
                with dithering(0.5):
                    with pal_single_color(7):
                        blt_rot(
                            x,
                            y,
                            self.image,
                            self.u,
                            self.v,
                            self.w,
                            self.h,
                            colkey=254,
                            rot=self.rotation,
                        )

    def update(self) -> None:
        self.timer += 1
        if self.timer >= self.cycle + self.wait:
            self.image = self.breathing_versions[next(self.pingpong)]
            self.cycle = self.rng.integers(32, 35)
            self.timer = self.wait

    def flash(self):
        self.flash_state.flash()

    def is_flashing(self):
        return self.flash_state.is_flashing()

    def add_popup(self, text: str, color: int) -> None:
        self.scene.add_popup(
            text, self.x + self.width // 2, self.y + self.height // 2, color
        )

    def add_animation(self, lens: str) -> None:
        self.scene.add_anim(
            lens, self.x + self.width // 2, self.y + self.height // 2, 1.0
        )


@functools.cache
def card_back() -> pyxel.Image:
    return pyxel.Image.from_image(asset_path("card-back.png"))


class FramingState(Enum):
    INACTIVE = 0
    PUT_UP = 1
    ACTIVE = 2
    PUT_DOWN = 3


rng = np.random.default_rng()


class ResolvingFraming:
    """A frame that shows up when resolving cards."""

    anim_handles: WeakList[Anim]

    def __init__(self, scene: MainScene) -> None:
        self.scene = scene
        self.rarity = -1
        self.tweener = Tweener()
        self.put_up_factor = 0
        self.state = FramingState.INACTIVE
        self.anim_handles = WeakList()

    def set_state(self, state: FramingState) -> None:
        if state == self.state:
            return
        self.transition_out_state(state)
        self.state = state
        self.transition_in_state(state)

    def transition_out_state(self, state: FramingState) -> None:
        if state == FramingState.ACTIVE:
            for handle in self.anim_handles.surviving_items():
                handle.stop()
            self.anim_handles.garbage_collect()

    def transition_in_state(self, state: FramingState) -> None:
        if state == FramingState.ACTIVE:
            if self.rarity == 1:
                self.anim_handles.append(
                    self.scene.add_anim(
                        "anims.black_flames_burst_top", WINDOW_WIDTH // 2, 0
                    )
                )
                self.anim_handles.append(
                    self.scene.add_anim(
                        "anims.black_flames_burst_bottom",
                        WINDOW_WIDTH // 2,
                        WINDOW_HEIGHT,
                    )
                )
            elif self.rarity == 2:
                self.anim_handles.append(
                    self.scene.add_anim(
                        "anims.black_flames", WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
                    )
                )
                for i, x in enumerate(rng.integers(5, 10, size=8)):
                    anim_lens = (
                        "anims.confetti_left" if i % 2 == 0 else "anims.confetti_right"
                    )
                    normalized_coord = rng.normal([0.5, 0.5], [0.15, 0.1], 2)
                    normalized_coord = np.clip(normalized_coord, 0.2, 0.8)
                    if i == 0:
                        x += 30
                    self.enqueue_animation(
                        x,
                        anim_lens,
                        WINDOW_WIDTH * normalized_coord[0],
                        WINDOW_HEIGHT * normalized_coord[1],
                    )

    def enqueue_animation(self, delay: int, lens: str, x: int, y: int) -> None:
        self.tweener.append(
            range(delay),
            Instant(lambda: self.anim_handles.append(self.scene.add_anim(lens, x, y))),
        )

    def update(self):
        self.tweener.update()

    def draw(self):
        if self.state == FramingState.INACTIVE:
            return

        if self.put_up_factor:
            black_gradient(0, 0, 427, self.put_up_factor)
            black_gradient_inverse(0, 240 - self.put_up_factor, 427, self.put_up_factor)

    def putup(self):
        self.tweener.append(
            Instant(lambda: self.set_state(FramingState.PUT_UP)),
            Mutator(15, pytweening.easeInOutQuad, self, "put_up_factor", 30),
            Instant(lambda: self.set_state(FramingState.ACTIVE)),
        )

    def teardown(self):
        self.tweener.append(
            Instant(lambda: self.set_state(FramingState.PUT_DOWN)),
            Mutator(15, pytweening.easeInOutQuad, self, "put_up_factor", 0),
            Instant(lambda: self.set_state(FramingState.INACTIVE)),
        )


class MainScene(Scene):
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
        self.bundle = setup_battle_bundle(
            "initial_deck", "players.starter", ["enemies.evil_mask"] * 2
        )
        self.card_sprites = []
        self.tmp_card_sprites = []
        self.background_video = Video("background.npy")
        self.sync_sprites()
        self.tooltip = Tooltip("", "")
        self.draw_deck = DrawDeck(self.bundle.card_bundle)
        self.anims = []
        self.popups = []
        self.timer = 0
        self.enemy_sprites = [
            WrappedImage(
                load_image("char", "enemy_killer_flower.png"),
                0,
                0,
                64,
                64,
                self,
                has_breathing=True,
                user_data=e.uuid,
            )
            for e in self.bundle.enemies
        ]

        self.player_sprite = WrappedImage(
            load_image("char", "char_celine.png"),
            0,
            0,
            64,
            64,
            self,
            has_breathing=False,
            user_data=self.bundle.player.uuid,
        )

        self.player_sprite.x = 0
        self.player_sprite.y = 110

        for s, x in zip(
            self.enemy_sprites, layout_center_for_n(len(self.bundle.enemies), 6 * 50)
        ):
            s.x = x - 32
            s.y = 60

        self.futures = deque()
        self.buffer = pyxel.Image(427, 240)
        self.framing = ResolvingFraming(self)
        self.framing.rarity = 2
        self.executor = ThreadPoolExecutor(max_workers=2)

    def sprites(self):
        yield self.player_sprite
        yield from self.enemy_sprites

    def sync_sprites(self):
        existing_card_sprites = {
            card_sprite.card.id: card_sprite for card_sprite in self.card_sprites
        }
        self.card_sprites = [
            existing_card_sprites.get(card.id)
            if existing_card_sprites.get(card.id)
            else CardSprite(i, card, self)
            for i, card in enumerate(self.bundle.card_bundle.hand)
        ]

        for i, card_sprite in enumerate(self.card_sprites):
            card_sprite.change_index(i)

    def reorder_card_as_sprites(self):
        self.bundle.card_bundle.hand = [
            card_sprite.card for card_sprite in self.card_sprites
        ]

    def can_resolve_new_cards(self):
        return (
            all(
                card_sprite.can_transition_to_resolving()
                for card_sprite in self.card_sprites
            )
            and not self.futures
        )

    def update(self):
        while self.bundle.card_bundle.events:
            _ev = self.bundle.card_bundle.events.pop()
            self.sync_sprites()

        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        if pyxel.btnp(pyxel.KEY_SPACE) and self.can_resolve_new_cards():
            self.play_selected()

        if pyxel.btnp(pyxel.KEY_Z):
            self.end_player_turn()

        for card in self.card_sprites:
            card.update()

        for card in self.tmp_card_sprites:
            card.update()

        self.tooltip.update()
        for anim in self.anims:
            anim.update()
        for popup in self.popups:
            popup.update()
        self.anims = [anim for anim in self.anims if not anim.dead]
        for sprite in self.sprites():
            sprite.update()
        self.framing.update()
        self.check_mailbox()
        self.background_video.update()
        self.timer += 1

        if self.timer % 240 == 0:
            self.framing.putup()
        if self.timer % 240 == 120:
            self.framing.teardown()

        # if self.timer % 30 == 0:
        #     self.add_anim("anims.black_flames_burst_top", WINDOW_WIDTH // 2, 0)

    def play_selected(self):
        selected_card_sprites = [card for card in self.card_sprites if card.selected]
        if not selected_card_sprites:
            return
        selected_cards = [card.card for card in selected_card_sprites]
        self.bundle.card_bundle.hand_to_resolving(selected_cards)
        self.tmp_card_sprites.extend(selected_card_sprites)
        for card in selected_card_sprites:
            card.try_transition_to_resolving()

        # filter
        self.card_sprites = [card for card in self.card_sprites if not card.selected]
        self.futures.append(
            self.executor.submit(self.resolve_selected_cards, selected_cards)
        )

    def check_mailbox(self):
        while self.futures and self.futures[0].done():
            effects = self.futures.popleft().result()
            for target_effect in effects:
                battler, effect = target_effect
                if isinstance(effect, SinglePointEffect):
                    if not battler:
                        raise ValueError("No battler found")
                    sprite = self.sprite_by_id(battler.uuid)
                    sprite.flash()
                    match effect.classify_type():
                        case SinglePointEffectType.DAMAGE:
                            sprite.add_popup(str(effect.damage), 7)
                            sprite.add_animation("anims.burst")
                        case SinglePointEffectType.HEAL:
                            sprite.add_popup(str(effect.heal), 11)
                            sprite.add_animation("anims.heal")
                        case SinglePointEffectType.SHIELD_GAIN:
                            sprite.add_animation("anims.shield_gain")
                        case SinglePointEffectType.SHIELD_LOSS:
                            sprite.add_popup(f"shield {effect.delta_shield}", 7)
                            sprite.add_animation("anims.debuff")
                        case SinglePointEffectType.STATUS:
                            for status_effect, counter in effect.add_status:
                                sprite.add_popup(f"+ {status_effect.name}", 7)
                            sprite.add_animation("anims.buff")

    def sprite_by_id(self, id: str) -> WrappedImage:
        for sprite in self.sprites():
            if sprite.user_data == id:
                return sprite
        raise ValueError(f"Sprite with id {id} not found")

    def add_anim(self, name: str, x: int, y: int, play_speed: float = 1.0) -> Anim:
        self.anims.append(result := Anim.from_predef(name, x, y, play_speed))
        return result

    def resolve_selected_cards(self, selected_cards: list[Card]) -> ResolvedEffects:
        return self.bundle.resolve_player_cards(selected_cards)

    def add_popup(self, text: str, x: int, y: int, color: int):
        self.popups.append(Popup(text, x, y, color))

    def _draw_hearts_and_shields(self, x: int, y: int, hp: int, shield: int) -> None:
        icons = load_image("ui", "icons.png")
        cursor = x
        num_hp = hp
        num_shield = shield
        while num_hp and num_hp >= 2:
            pyxel.blt(cursor, y, icons, 0, 0, 8, 64, colkey=254)
            cursor += 10
            num_hp -= 2
        if num_hp:
            pyxel.blt(cursor, y, icons, 10, 0, 8, 64, colkey=254)
            cursor += 10
        while num_shield and num_shield >= 2:
            pyxel.blt(cursor, y, icons, 20, 0, 8, 64, colkey=254)
            cursor += 8
            num_shield -= 2
        if num_shield:
            cursor += 1
            pyxel.blt(cursor, y, icons, 29, 0, 8, 64, colkey=254)
            cursor += 8

    def draw(self):
        self.draw_background()
        self.draw_deck.draw(10, 190)

        self.draw_battlers()

        for card in self.card_sprites:
            card.draw()
        for card in self.tmp_card_sprites:
            card.draw()

        button(WINDOW_WIDTH - 70, WINDOW_HEIGHT - 20, 55, 15, "End Turn", 7, 5)
        button(WINDOW_WIDTH - 70, WINDOW_HEIGHT - 50, 55, 15, "Play Cards", 7, 5)
        self.tooltip.draw()

        Anim.draw()
        for popup in self.popups:
            popup.draw()
        self.framing.draw()
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def draw_background(self):
        m = self.background_video.appearance
        buffer_as_arr = _image_as_ndarray(self.buffer)
        pyxel.cls(0)
        pyxel.pal(3, 5)
        pyxel.pal(11, 12)
        buffer_as_arr[:] = 0
        pyxel.blt(0, 0, self.background_video.current_image, 0, 0, 427, 240, 0)
        t = pytweening.easeOutCirc(min(self.background_video.actual_timer / 500.0, 1))
        buffer_as_arr[m < t] = 254
        pyxel.pal()
        with dithering(0.5):
            for mask in self.background_video.masks:
                pyxel.blt(0, 0, mask, 0, 0, 427, 240, colkey=254)
        with dithering(0.5):
            pyxel.blt(0, 0, self.background_video.masks[0], 0, 0, 427, 240, colkey=254)

    def draw_battlers(self):
        short_holder = load_image("ui", "short-holder.png")
        long_holder = load_image("ui", "long-holder.png")

        pyxel.blt(-10, 147 + 10, long_holder, 0, 0, 130, 30, colkey=254)
        self.player_sprite.draw()
        player = self.bundle.player
        shadowed_text(51, 147 + 5, player.name_stem, 7, layout(w=80, ha="left"))
        self._draw_hearts_and_shields(50, 162, player.hp, player.shield_points)
        for i, (x, e) in enumerate(
            zip(layout_center_for_n(2, 6 * 50), self.bundle.enemies)
        ):
            self.enemy_sprites[i].draw()
            pyxel.blt(10 + x - 36, 126, short_holder, 0, 0, 80, 64, colkey=254)
            shadowed_text(10 + x - 30, 121, e.name, 7, layout(w=80, ha="left"))
            self._draw_hearts_and_shields(10 + x - 31, 131, e.hp, e.shield_points)
            pyxel.clip(10 + x - 30 - 5, 141, 68, 7)
            text_width = retro_font.rasterize(e.current_intent, 5, 255, 0, 0).width + 14
            retro_text(
                10 + x - 30 - 5 - (self.timer) % text_width,
                141,
                e.current_intent,
                col=7,
            )
            retro_text(
                10 + x - 30 - 5 - (self.timer) % text_width + text_width,
                141,
                e.current_intent,
                col=7,
            )
            pyxel.clip()

    def draw_crosshair(self, x, y):
        pyxel.line(x - 5, y, x + 5, y, 7)
        pyxel.line(x, y - 5, x, y + 5, 7)

    def end_player_turn(self):
        self.bundle.end_player_turn()


def gen_scene() -> Scene:
    return MainScene()
