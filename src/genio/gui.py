from __future__ import annotations

import contextlib
import functools
import itertools
import math
from collections import deque
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

import numpy as np
import pytweening
import pyxel
from pyxelxl import blt_rot, layout
from pyxelxl.font import _image_as_ndarray

from genio.base import Video, asset_path, load_image, resize_image_breathing
from genio.battle import (
    BattleBundle,
    CardBundle,
    EnemyBattler,
    MainSceneLike,
    ResolvedEffects,
)
from genio.card import Card
from genio.components import (
    CanAddAnim,
    DrawDeck,
    EnergyRenderer,
    GoldRenderer,
    HasPos,
    MouseHasPos,
    Popup,
    camera_shift,
    capital_hill_text,
    cute_text,
    dithering,
    draw_mixed_rounded_rect,
    pal_single_color,
    retro_font,
    retro_text,
    shadowed_text,
    willow_branch,
)
from genio.constants import (
    CARD_HEIGHT,
    CARD_WIDTH,
    GRID_SPACING_X,
    GRID_X_START,
    GRID_Y_START,
    TOTAL_CARDS,
)
from genio.effect import SinglePointEffect, SinglePointEffectType, StatusDefinition
from genio.follower_tooltip import FollowerTooltip
from genio.gamestate import game_state
from genio.gears.card_printer import CardPrinter
from genio.gears.config_menu import ConfigMenuScene
from genio.gears.icon_button import IconButton
from genio.gears.median_filter import ImagePiece, sprite_to_pieces
from genio.gears.signpost import SignPost
from genio.gears.spritesheet import Spritesheet
from genio.gears.weather import WeatherEffect, WeatherType
from genio.layout import (
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    fan_out_for_N,
    layout_center_for_n,
    pingpong,
)
from genio.ps import Anim
from genio.scene import EmitSound, Scene, emit_sound_event
from genio.sound_events import SoundEv
from genio.tween import Instant, MutableTweening, Mutator, Shake, Tweener
from genio.utils.weaklist import WeakList


def round_off_rating(number):
    return round(number * 2) / 2


class CardState(Enum):
    ACTIVE = 0
    RESOLVING = 1
    RESOLVED = 2
    INITIALIZE = 3


def sin_01(t: float, dilation: float) -> float:
    return (math.sin(t * dilation) + 1) / 2


class CardSprite:
    def __init__(
        self, index: int, card: Card, app: MainSceneLike, selected: bool = False
    ) -> None:
        self.index = index
        self.app = app
        self.change_index(index)
        self.x = 10
        self.y = 190
        self.card = card
        self.width = CARD_WIDTH
        self.height = CARD_HEIGHT
        self.dragging_time = 0
        self.hovered = False
        self.highlight_timer = 0
        self.selected = selected
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.card_printer = app.card_printer
        self.is_rare = False
        self.refresh_art()
        self.state = CardState.INITIALIZE
        self.update_delay = 8 * index + 5
        self.tweens = Tweener()
        self.xy_tweens = Tweener()
        self.rotation = 0
        self.fade_timer = 0
        self.tweens.append(
            itertools.chain(
                EmitSound(SoundEv.CARD_MOVE),
                MutableTweening(
                    12, pytweening.easeInOutQuad, self, (self.target_x, self.target_y)
                ),
                Instant(self.transition_to_active),
            )
        )
        self.hover_timer = -1

    def refresh_art(self):
        self.image = self.card_printer.print_card(self.card)

    def transition_to_active(self):
        self.state = CardState.ACTIVE

    def screen_pos(self) -> tuple[float, float]:
        return self.x + self.width // 2, self.y + self.height // 2

    def add_anim(self, lens: str) -> None:
        self.app.add_anim(lens, *self.screen_pos(), 1.0, self)

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

        target_x = layout_center_for_n(num_total_cards, 400)[my_index] - self.width // 2
        target_y = WINDOW_HEIGHT // 2 - self.height // 2
        self.tweens.flush()
        self.tweens.append(
            itertools.chain(
                range(10 + 4 * my_index),
                EmitSound(SoundEv.CARD_MOVE),
                MutableTweening(
                    15, pytweening.easeInOutQuad, self, (target_x, target_y)
                ),
                range(4),
                Instant(self.on_reach_hovering_location),
            )
        )

    def try_transitioning_to_resolved(self, i: int = 0, baseline: float = 1) -> None:
        self.state = CardState.RESOLVED
        self.tweens.append(
            itertools.chain(
                range(int((10 + i * 5) * baseline)),
                EmitSound(SoundEv.CARD_MOVE),
                MutableTweening(
                    15,
                    pytweening.easeInOutQuad,
                    self,
                    (WINDOW_WIDTH + 10, WINDOW_HEIGHT - self.height - 2),
                ),
            )
        )

    def z_order(self) -> int:
        if self.dragging:
            return 1000
        return self.index

    def on_reach_hovering_location(self):
        self.hover_timer = 0

    def schedule_shake(self):
        self.tweens.append(Shake(self, 5, 15))

    def schedule_small_shake(self):
        self.tweens.append(Shake(self, 20, 5))

    def draw(self):
        shift = 0
        if self.hover_timer > 0:
            shift = math.sin(self.hover_timer / 10) * 5
        with camera_shift(0, shift):
            if self.dragging or self.state == CardState.RESOLVING:
                self.draw_shadow()
            self._draw()

    def draw_shadow(self):
        with dithering(0.5):
            with pal_single_color(1):
                blt_rot(
                    self.x + 2,
                    self.y + 2,
                    self.image,
                    0,
                    0,
                    self.width,
                    self.height,
                    colkey=254,
                    rot=self.rotation,
                )

    def is_dead(self) -> bool:
        return self.state == CardState.RESOLVED and not self.tweens

    def _draw(self):
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
            if (
                not self.selected
                and any(card for card in self.app.card_sprites if card.selected)
            ) or (
                self.app.should_all_cards_disabled()
                and not self.selected
                and self.state != CardState.RESOLVING
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

    def draw_highlighted_edges(self):
        if self.highlight_timer > 0:
            with dithering(0.5 * sin_01(self.highlight_timer, 0.1)):
                blt_rot(
                    self.x,
                    self.y,
                    load_image("card_flashing_overlay.png"),
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
        self.xy_tweens.update()
        if self.hover_timer >= 0:
            self.hover_timer += 1

    def update_active(self):
        if self.index >= self.deck_length:
            for i, card in enumerate(self.app.card_sprites):
                card.change_index(i)
            return
        if self.dragging:
            self.dragging_time += 1
        else:
            self.dragging_time = 0
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if self.is_mouse_over():
                self.dragging = True
                self.drag_offset_x = pyxel.mouse_x - self.x
                self.drag_offset_y = pyxel.mouse_y - self.y

        if pyxel.btnr(pyxel.MOUSE_BUTTON_LEFT):
            if self.dragging:
                self.dragging = False
                ix_changed = self.snap_to_grid()
                if (
                    not ix_changed
                    and self.dragging_time < 10
                    and not self.app.should_all_cards_disabled()
                ):
                    self.selected = not self.selected

        if self.dragging:
            self.x = pyxel.mouse_x - self.drag_offset_x
            self.y = pyxel.mouse_y - self.drag_offset_y

        inverse_index = self.deck_length - self.index - 1
        # Tweening for smooth transition
        if not self.dragging and (
            10 + inverse_index * 4 >= self.app.should_wait_until_animation()
        ):
            target_x, target_y = self.adjusted_target_coords()
            if (self.x != target_x or self.y != target_y) and not self.xy_tweens:
                distance = math.sqrt(
                    (self.x - target_x) ** 2 + (self.y - target_y) ** 2
                )
                t = int(distance / 6)
                t = max(t, 6)
                if self.app.should_wait_until_animation():
                    t = max(t, 15)
                self.xy_tweens.append(
                    MutableTweening(
                        t,
                        pytweening.easeInOutQuad,
                        self,
                        (target_x, target_y),
                    )
                )

        if self.is_mouse_over():
            if self.hovered:
                self.highlight_timer += 1
            else:
                self.highlight_timer = 0
                if rng.random() < 0.5:
                    next_rot = rng.uniform(-5, -2)
                else:
                    next_rot = rng.uniform(2, 5)
                self.tweens.append(
                    Mutator(10, pytweening.easeInOutQuad, self, "rotation", next_rot),
                    range(28),
                    Mutator(10, pytweening.easeInOutQuad, self, "rotation", 0),
                )
            self.hovered = True
            self.app.tooltip.pump_energy(self.card.name, self.card.description or "")
        else:
            if self.hovered:
                self.tweens.clear()
                self.tweens.append(
                    Mutator(6, pytweening.easeInOutQuad, self, "rotation", 0)
                )
            self.hovered = False

    def snap_to_grid(self) -> bool:
        any_index_changed = False
        new_index = (int(self.x) - GRID_X_START + GRID_SPACING_X // 2) // GRID_SPACING_X
        new_index = max(0, min(TOTAL_CARDS - 1, new_index))

        if new_index != self.index:
            any_index_changed = True

        self.app.card_sprites.remove(self)
        self.app.card_sprites.insert(new_index, self)

        for i, card in enumerate(self.app.card_sprites):
            card.change_index(i)
        return any_index_changed

    def change_index(self, new_index: int):
        self.index = new_index
        self.target_x, self.target_y = self.calculate_target_coords()

    def adjusted_target_coords(self) -> tuple[int, int]:
        x, y = self.calculate_target_coords()
        return x, y - 10 if self.selected else y

    def calculate_target_coords(self) -> tuple[int, int]:
        fanout = fan_out_for_N(self.deck_length)[min(self.index, self.deck_length - 1)]
        return (
            GRID_X_START + self.index * GRID_SPACING_X,
            GRID_Y_START + pyxel.sin(abs(fanout)) * 60,
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


class Tooltip:
    """The help box."""

    def __init__(self, title: str = "", description: str = "") -> None:
        self.title = title
        self.description = description
        self.counter = 60

    def draw(self) -> None:
        if (not self.title and not self.description) or self.counter <= 0:
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        amx, amy = mx, my
        t = 0.05
        amx = mx * t + ((1 - t) * pyxel.width / 2)
        amy = my * t + ((1 - t) * pyxel.height * 0.9) - 60
        dither_amount = 1.0 if self.counter > 50 else (self.counter / 50) ** 2
        rect_width = 80
        rect_height = 15
        if self.description:
            rect_width *= 2
            rect_height *= 2 if not game_state.should_use_large_font() else 2.5
            rect_height = int(rect_height)
        if len(self.description) > 45:
            rect_height += 17
        draw_mixed_rounded_rect(dither_amount, amx, amy, w=rect_width, h=rect_height)
        with dithering(dither_amount):
            cute_text(
                amx - rect_width // 2,
                amy,
                self.title,
                7,
                layout=layout(w=rect_width, ha="center", va="center", h=14),
            )
            if self.description:
                font = (
                    capital_hill_text
                    if game_state.should_use_large_font()
                    else retro_text
                )
                extra_y_padding = 3 if game_state.should_use_large_font() else 0
                font(
                    amx - rect_width // 2 + 8,
                    amy + 11 + extra_y_padding,
                    self.description,
                    7,
                    layout=layout(
                        w=rect_width - 16, ha="left", va="top", h=rect_height - 11
                    ),
                )

    def update(self) -> None:
        self.counter -= 3
        if self.counter <= 0:
            self.title = ""
            self.description = ""
            self.counter = 0

    def pump_energy(self, title: str, description: str) -> None:
        if self.counter >= 40 and (
            self.title != title or self.description != description
        ):
            return
        self.counter += 10
        self.counter = min(60, self.counter)
        self.title = title
        self.description = description


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


class EnemyBattlerSprite:
    def __init__(self, x: int, y: int, battler: EnemyBattler, scene: MainScene) -> None:
        self.x = x
        self.y = y
        self.battler = battler
        self.scene = scene
        raw_image = scene.enemy_spritesheet.search_image(battler.chara)
        self.image = WrappedImage(
            raw_image,
            0,
            0,
            64,
            64,
            self,
            has_breathing=True,
            user_data=battler.uuid,
        )
        self.image.x = x - 32
        self.image.y = y - 32
        self.hp = battler.hp
        self.max_hp = battler.max_hp
        self.flash_state = FlashState()
        self.tweens = Tweener()
        self.opacity = 1.0
        self.rotation = 0
        self.played_dead = False

    def play_death_animation(self) -> None:
        if self.played_dead:
            return
        self.played_dead = True
        self.scene.pieces.extend(
            sprite_to_pieces(self.x - 32, self.y, self.image.image)
        )

        self.tweens.append_mutate(self, "opacity", 30, 0.0, "ease_in_out_quad")

    def is_dead(self) -> bool:
        return self.opacity <= 0

    def update(self) -> None:
        self.image.x = self.x - 32
        self.image.y = self.y
        self.image.update()
        self.tweens.update()

    def draw(self) -> None:
        e = self.battler
        short_holder = load_image("ui", "short-holder.png")
        if self.opacity >= 1.0:
            self.image.draw(self.x - 32, self.y)
        with dithering(self.opacity):
            pyxel.blt(10 + self.x - 36, 126, short_holder, 0, 0, 80, 64, colkey=254)
            shadowed_text(
                10 + self.x - 30,
                121,
                e.name,
                7,
                layout(w=80, ha="left"),
                dither_mult=self.opacity,
            )
            self.scene._draw_hearts_and_shields(
                10 + self.x - 31, 131, e.hp, e.shield_points
            )
            pyxel.clip(10 + self.x - 30 - 5, 141, 68, 7)
            text_width = retro_font.rasterize(e.current_intent, 5, 255, 0, 0).width + 14
            pyxel.dither(self.opacity)
            for i in range(2):
                retro_text(
                    -25 + self.x - (self.scene.timer) % text_width + i * text_width,
                    141,
                    self.battler.current_intent,
                    col=7,
                )
            pyxel.clip()
            for i, s in enumerate(self.battler.status_effects):
                turns_left = s.counter
                icon = s.icon_id
                self.scene.draw_stats_icon(
                    icon_x := 15 + self.x + i * 14, icon_y := 107, icon, turns_left
                )
                self.scene.follower_tooltip_areas.append(
                    FollowerTooltipArea(
                        icon_x,
                        icon_y,
                        16,
                        16,
                        s.name,
                        s.description,
                    )
                )

    @property
    def user_data(self) -> str:
        return self.battler.uuid

    def flash(self) -> None:
        self.image.flash()

    def is_flashing(self) -> bool:
        return self.image.is_flashing()

    def add_popup(self, text: str, color: int) -> None:
        self.scene.add_popup(text, self.x, self.y + 32, color)

    def add_animation(self, lens: str) -> None:
        self.scene.add_anim(lens, self.x, self.y + 32, 1.0)


@functools.cache
def card_back() -> pyxel.Image:
    return pyxel.Image.from_image(asset_path("card-back.png"))


rng = np.random.default_rng()


class FramingState(Enum):
    INACTIVE = 0
    PUT_UP = 1
    ACTIVE = 2
    PUT_DOWN = 3


class ResolvingFraming:
    """A frame that shows up when resolving cards."""

    anim_handles: WeakList[Anim]

    def __init__(self, scene: CanAddAnim) -> None:
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
            ...

    def on_rarity_determined(self, rarity: int) -> None:
        self.rarity = rarity
        if self.rarity == 2:
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
        elif self.rarity >= 3:
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


class ImageButtonState(Enum):
    NORMAL = 0
    FLASHING = 1
    DISABLED = 2


class ImageButton:
    def __init__(self, x: int, y: int, image: pyxel.Image):
        self.x = x
        self.y = y
        self.image = image
        self.hovering = False
        self.state = ImageButtonState.NORMAL
        self.pingpong_flashing = pingpong(8, 3)
        self.pingpong_state = 0

    def draw(self) -> None:
        if self.state == ImageButtonState.DISABLED:
            with dithering(0.75):
                pyxel.blt(
                    self.x,
                    self.y,
                    self.image,
                    0,
                    0,
                    self.image.width,
                    self.image.height,
                    colkey=254,
                )
            with dithering(0.5):
                with pal_single_color(13):
                    pyxel.blt(
                        self.x,
                        self.y,
                        self.image,
                        0,
                        0,
                        self.image.width,
                        self.image.height,
                        colkey=254,
                    )
            return
        if self.hovering and not self.state == ImageButtonState.DISABLED:
            pyxel.pal(1, 5)
        pyxel.blt(
            self.x,
            self.y,
            self.image,
            0,
            0,
            self.image.width,
            self.image.height,
            colkey=254,
        )
        pyxel.pal()

        if not self.hovering and self.state == ImageButtonState.FLASHING:
            with dithering((self.pingpong_state / 7) * 0.25):
                with pal_single_color(6):
                    pyxel.blt(
                        self.x,
                        self.y,
                        self.image,
                        0,
                        0,
                        self.image.width,
                        self.image.height,
                        colkey=254,
                    )

        if self.hovering:
            with dithering(0.25):
                with pal_single_color(1):
                    pyxel.blt(
                        self.x,
                        self.y,
                        self.image,
                        0,
                        0,
                        self.image.width,
                        self.image.height,
                        colkey=254,
                    )

        if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT) and self.hovering:
            with dithering(0.5):
                with pal_single_color(1):
                    pyxel.blt(
                        self.x,
                        self.y,
                        self.image,
                        0,
                        0,
                        self.image.width,
                        self.image.height,
                        colkey=254,
                    )

    def update(self) -> bool:
        if self.state == ImageButtonState.DISABLED:
            self.hovering = False
            return False

        if self.state == ImageButtonState.FLASHING:
            self.pingpong_state = next(self.pingpong_flashing)

        if (
            self.x <= pyxel.mouse_x <= self.x + self.image.width
            and self.y <= pyxel.mouse_y <= self.y + self.image.height
        ):
            self.hovering = True
        else:
            self.hovering = False

        if pyxel.btnr(pyxel.MOUSE_BUTTON_LEFT) and self.hovering:
            return True
        return False


class ResolvingSide(Enum):
    PLAYER = 0
    ENEMY = 1


def draw_icon(x: int, y: int, icon_id: int) -> None:
    icons = load_image("icons.png")
    icon_w, icon_h = 16, 16
    num_horz = icons.width // icon_w

    icon_x = icon_id % num_horz
    icon_y = icon_id // num_horz

    pyxel.blt(x, y, icons, icon_x * icon_w, icon_y * icon_h, icon_w, icon_h, colkey=254)


@dataclass(frozen=True)
class FollowerTooltipArea:
    x: int
    y: int
    w: int
    h: int
    title: str
    description: str

    def is_in_bounds(self, x: int, y: int) -> bool:
        return self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h


class Updatable(Protocol):
    def update(self) -> None:
        ...

    def is_dead(self) -> bool:
        ...


class Drawable(Updatable):
    def draw(self) -> None:
        ...


class MainScene(Scene):
    card_bundle: CardBundle
    anims: list[Anim]
    futures: deque[Future[ResolvedEffects]]

    card_sprites: list[CardSprite]
    bundle: BattleBundle

    follower_tooltip_areas: list[FollowerTooltipArea]
    pieces: list[ImagePiece]

    updatables: list[Updatable | Drawable]
    subscenes: list[Scene]
    card_printer: CardPrinter

    def __init__(self):
        self.bundle = game_state.battle_bundle
        self.subscenes = []
        self.enemy_spritesheet = Spritesheet(
            asset_path("enemies.json"), build_search_index=True
        )
        self.card_printer = CardPrinter()
        self.card_sprites = []
        self.tmp_card_sprites = []
        self.background_video = Video("background/*.png")
        self.sync_sprites(None)
        self.tooltip = Tooltip("", "")
        self.draw_deck = DrawDeck(self.bundle.card_bundle)
        self.anims = []
        self.popups = []
        self.timer = 0
        self.tweener = Tweener()
        self.energy_renderer = EnergyRenderer(self.bundle, self)
        self.enemy_sprites = [
            EnemyBattlerSprite(100, 100, e, self) for e in self.bundle.enemies
        ]
        self.weather = WeatherEffect(
            self, WeatherType.BORDER_RIGHT_WIND, 1.3, ["anims.space_particle"]
        )
        self.wait_anim_countdown = 0
        self.pieces = []
        self.follower_tooltip = FollowerTooltip(MouseHasPos())
        self.zero_energy_timer = 0
        self.gold_renderer = GoldRenderer(game_state, self, 100, 0)
        self.updatables = []
        self.tweens_signpost = Tweener()
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

        self.follower_tooltip_areas = []

        self.player_sprite.x = 0
        self.player_sprite.y = 110

        for s, x in zip(
            self.enemy_sprites, layout_center_for_n(len(self.bundle.enemies), 6 * 50)
        ):
            s.x = x
            s.y = 60

        self.futures = deque()
        self.buffer = pyxel.Image(427, 240)
        self.framing = ResolvingFraming(self)
        self.framing.rarity = 2
        self.executor = ThreadPoolExecutor(max_workers=2)

        self.image_buttons = [
            ImageButton(
                WINDOW_WIDTH - 85,
                WINDOW_HEIGHT - 52,
                load_image("ui", "play-button.png"),
            ),
            ImageButton(
                WINDOW_WIDTH - 90,
                WINDOW_HEIGHT - 27,
                load_image("ui", "end-button.png"),
            ),
        ]

        self.end_button = self.image_buttons[1]
        self.play_button = self.image_buttons[0]
        self.resolving_side = ResolvingSide.PLAYER
        self.bundle.card_bundle.events.register_listener(self.on_new_event)

        self.config_button = IconButton(WINDOW_WIDTH - 18 - 2 - 4, 2, 41)
        self.about_button = IconButton(WINDOW_WIDTH - 18 - 18 - 2 - 4, 2, 20)
        self.putup_player_signpost()

    def sprites(self):
        yield self.player_sprite
        yield from self.enemy_sprites

    def sync_sprites(self, ev: str, *userdata: Any):
        existing_card_sprites = {
            card_sprite.card.id: card_sprite for card_sprite in self.card_sprites
        }

        card_sprites = []
        to_move_to_target: list[CardSprite] = []

        for i, card in enumerate(self.bundle.card_bundle.hand):
            if existing_spr := existing_card_sprites.get(card.id):
                card_sprites.append(existing_spr)
                if ev == "transform_card" and userdata[0] == existing_spr.card.id:
                    existing_spr.refresh_art()
                    existing_spr.add_anim("anims.transform_card")
            else:
                card_sprites.append(spr := CardSprite(i, card, self))
                if ev == "add_to_hand":
                    spr.add_anim("anims.create_card")
                    to_move_to_target.append(spr)
        self.card_sprites = card_sprites

        for i, card_sprite in enumerate(self.card_sprites):
            card_sprite.change_index(i)

        for card_sprite in to_move_to_target:
            tx, ty = card_sprite.calculate_target_coords()
            card_sprite.x = tx
            card_sprite.y = ty
            card_sprite.tweens.clear()
            card_sprite.state = CardState.ACTIVE

    def reorder_card_as_sprites(self):
        self.bundle.card_bundle.hand = [
            card_sprite.card for card_sprite in self.card_sprites
        ]

    def can_resolve_new_cards(self) -> bool:
        if self.bundle.energy - self.bundle.tentative_energy_cost() < 0:
            return False
        return (
            all(
                card_sprite.can_transition_to_resolving()
                for card_sprite in self.card_sprites
            )
            and not self.futures
        )

    def on_new_event(self, ev: str, *others: Any) -> None:
        self.sync_sprites(ev, *others)

    def should_wait_until_animation(self) -> bool:
        if self.wait_anim_countdown > 0:
            return self.wait_anim_countdown
        return 0

    def update(self):
        if self.subscenes:
            for subscene in self.subscenes:
                subscene.update()
            self.subscenes = [
                subscene
                for subscene in self.subscenes
                if not subscene.request_next_scene()
            ]
            return
        if self.wait_anim_countdown > 0:
            if not self.tmp_card_sprites:
                self.wait_anim_countdown = 0
            else:
                self.wait_anim_countdown -= 1
        if pyxel.btnp(pyxel.KEY_SPACE) and self.can_resolve_new_cards():
            self.play_selected()

        if pyxel.btnp(pyxel.KEY_Z):
            self.end_player_turn()

        for card in self.card_sprites:
            card.update()

        for card in self.tmp_card_sprites:
            card.update()

        for piece in self.pieces:
            piece.update()

        self.pieces = [piece for piece in self.pieces if not piece.is_dead()]
        self.weather.update()

        if self.image_buttons[0].update():
            self.play_selected()

        if self.image_buttons[1].update():
            self.end_player_turn()

        self.energy_renderer.update()
        self.gold_renderer.update()

        if self.bundle.energy <= 0 and not self.bundle.card_bundle.resolving:
            self.zero_energy_timer += 1
        else:
            self.zero_energy_timer = 0

        self.tmp_card_sprites = [
            card for card in self.tmp_card_sprites if not card.is_dead()
        ]

        self.bundle.proposed_cards = [
            card.card for card in self.card_sprites if card.selected
        ]

        self.tweener.update()
        self.tooltip.update()
        self.follower_tooltip.update()
        for tooltip_area in self.follower_tooltip_areas:
            if tooltip_area.is_in_bounds(pyxel.mouse_x, pyxel.mouse_y):
                self.follower_tooltip.pump2(
                    tooltip_area.title, tooltip_area.description
                )
                break
        self.follower_tooltip_areas.clear()
        for anim in self.anims:
            anim.update()
        for popup in self.popups:
            popup.update()
        for updatable in self.updatables:
            updatable.update()
        self.updatables = [
            updatable for updatable in self.updatables if not updatable.is_dead()
        ]
        self.popups = [popup for popup in self.popups if not popup.is_dead()]
        self.anims = [anim for anim in self.anims if not anim.dead]
        for sprite in self.sprites():
            sprite.update()
        self.enemy_sprites = [s for s in self.enemy_sprites if not s.is_dead()]
        self.sync_enemy_sprites()
        self.framing.update()
        self.check_mailbox()
        self.update_buttons_state()
        self.tweens_signpost.update()
        self.background_video.update()

        self.config_button.update()
        self.about_button.update()
        self.timer += 1

    def add_signpost(self, text: str) -> None:
        self.updatables.append(SignPost(WINDOW_WIDTH // 2, 50, text, self))

    def sync_enemy_sprites(self):
        if self.tmp_card_sprites:
            return
        for s in self.enemy_sprites:
            if s.battler.is_dead():
                s.play_death_animation()

    def update_buttons_state(self):
        if self.bundle.energy <= 0:
            self.play_button.state = ImageButtonState.DISABLED
            self.end_button.state = ImageButtonState.FLASHING
        else:
            self.play_button.state = ImageButtonState.NORMAL
            self.end_button.state = ImageButtonState.NORMAL

        if self.bundle.energy - self.bundle.tentative_energy_cost() < 0:
            self.play_button.state = ImageButtonState.DISABLED

    def schedule_in(self, delay: int, fn: Callable[[], None]) -> None:
        self.tweener.append(range(delay), Instant(fn))

    def play_selected(self) -> None:
        emit_sound_event(SoundEv.CONFIRM)
        self.wait_anim_countdown = 30
        selected_card_sprites = [card for card in self.card_sprites if card.selected]
        if not selected_card_sprites:
            return
        selected_cards = [card.card for card in selected_card_sprites]
        self.bundle.card_bundle.hand_to_resolving(selected_cards)
        self.tmp_card_sprites.extend(selected_card_sprites)

        self.card_sprites = [card for card in self.card_sprites if not card.selected]
        self.framing.putup()
        for i, card in enumerate(selected_card_sprites):
            card.try_transition_to_resolving()
        self.futures.append(
            self.executor.submit(self.resolve_selected_cards, selected_cards)
        )

    def check_mailbox(self):
        while self.futures and self.futures[0].done():
            effects = self.futures.popleft().result()
            self.on_receive_mail(effects)

    def on_receive_mail(self, effects: ResolvedEffects) -> None:
        if self.resolving_side == ResolvingSide.PLAYER:
            for in_progress_card in self.tmp_card_sprites:
                in_progress_card.schedule_shake()

        self.framing.on_rarity_determined(effects.rarity)
        self.play_effects(effects)
        self.bundle.record_to_battle_logs(effects)
        self.schedule_in(30, lambda: self.framing.teardown())
        if self.resolving_side == ResolvingSide.PLAYER:
            self.schedule_in(0, lambda: self.move_away_cards())
        else:
            self.schedule_in(0, self.start_new_turn)

    def move_away_cards(self):
        for i, card in enumerate(self.tmp_card_sprites):
            card.try_transitioning_to_resolved(i)
        self.bundle.card_bundle.resolving.clear()

    def play_effects(self, effects: ResolvedEffects) -> None:
        for target_effect in effects:
            battler, effect = target_effect
            if isinstance(effect, SinglePointEffect):
                if not battler:
                    raise ValueError("No battler found")
                sprite = self.sprite_by_id(battler.uuid)
                sprite.flash()
                match effect.classify_type():
                    case SinglePointEffectType.DAMAGE:
                        sprite.add_popup(str(int(effect.damage)), 7)
                        sprite.add_animation("anims.burst")
                        emit_sound_event(SoundEv.HIT)
                    case SinglePointEffectType.HEAL:
                        sprite.add_popup(str(int(effect.heal)), 11)
                        sprite.add_animation("anims.heal")
                    case SinglePointEffectType.SHIELD_GAIN:
                        sprite.add_animation("anims.shield_gain")
                        emit_sound_event(SoundEv.DEFEND)
                    case SinglePointEffectType.SHIELD_LOSS:
                        sprite.add_popup(f"shield {effect.delta_shield}", 7)
                        sprite.add_animation("anims.debuff")
                    case SinglePointEffectType.STATUS:
                        status_effect, counter = effect.add_status
                        if not isinstance(status_effect, StatusDefinition):
                            raise ValueError("Status effect not valid")
                        sprite.add_popup(f"+ {status_effect.name}", 7)
                        sprite.add_animation("anims.debuff")

    def sprite_by_id(self, id: str) -> WrappedImage:
        for sprite in self.sprites():
            if sprite.user_data == id:
                return sprite
        raise ValueError(f"Sprite with id {id} not found")

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

    def resolve_selected_cards(self, selected_cards: list[Card]) -> ResolvedEffects:
        return self.bundle.resolve_player_cards(selected_cards)

    def add_popup(self, text: str, x: int, y: int, color: int):
        self.popups.append(Popup(text, x, y, color))

    def request_next_scene(self) -> str | None:
        if pyxel.btnp(pyxel.KEY_Q):
            return "genio.scene_booster"

    def should_all_cards_disabled(self) -> bool:
        if self.bundle.card_bundle.resolving:
            return True
        return self.zero_energy_timer > 30

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
        self.follower_tooltip_areas.append(
            FollowerTooltipArea(
                10,
                190,
                64,
                80,
                "Deck",
                "The cards you can draw from. The number indicate the amount of cards left.",
            )
        )

        self.draw_battlers()
        card_draw_order = np.argsort([card.z_order() for card in self.card_sprites])
        for card_ix in card_draw_order:
            self.card_sprites[card_ix].draw()
        for card in self.tmp_card_sprites:
            card.draw()

        for piece in self.pieces:
            piece.draw()

        self.draw_deck.draw_card_label(10, 190)

        for button in self.image_buttons:
            button.draw()
        self.tooltip.draw()
        self.follower_tooltip.draw()
        for anim in self.anims:
            anim.draw_myself()
        Anim.draw()
        for updatable in self.updatables:
            if hasattr(updatable, "draw"):
                updatable.draw()
        self.energy_renderer.draw()
        for popup in self.popups:
            popup.draw()
        self.draw_hud()
        self.framing.draw()
        for scene in self.subscenes:
            scene.draw()
        if self.config_button.btnp and not self.subscenes:
            self.config_button.btnp = False
            self.subscenes.append(ConfigMenuScene())
        self.draw_crosshair(pyxel.mouse_x, pyxel.mouse_y)

    def draw_hud(self):
        stop = WINDOW_WIDTH // 5
        pyxel.rect(0, 0, stop, 20, 0)
        pyxel.tri(stop, 0, stop + 12, 0, stop, 20, 0)
        pyxel.rect(WINDOW_WIDTH - 18 - 20 - 4 - 2, 0, WINDOW_WIDTH, 20, 0)
        pyxel.tri(
            WINDOW_WIDTH - 18 - 20 - 4 - 2 - 12,
            0,
            WINDOW_WIDTH - 18 - 20 - 4 - 2,
            0,
            WINDOW_WIDTH - 18 - 20 - 4 - 2,
            20,
            0,
        )
        with dithering(0.5):
            pyxel.rect(0, 0, stop, 20, 1)
            pyxel.tri(
                WINDOW_WIDTH - 18 - 20 - 4 - 2 - 12,
                0,
                WINDOW_WIDTH - 18 - 20 - 4 - 2,
                0,
                WINDOW_WIDTH - 18 - 20 - 4 - 2,
                20,
                1,
            )
            pyxel.rect(WINDOW_WIDTH - 18 - 20 - 4 - 2, 0, WINDOW_WIDTH, 20, 1)
            pyxel.tri(stop, 0, stop + 12, 0, stop, 20, 1)
        with camera_shift(0, -2):
            willow_branch(
                4 + 4, 0, game_state.stage.name, 7, layout=layout(h=16, va="center")
            )
            retro_text(
                26 + 4,
                1,
                f"Turn {self.bundle.turn_counter + 1}",
                7,
                layout=layout(h=16, va="center"),
            )
            # draw_icon(WINDOW_WIDTH - 18 - 2 - 4, 0, 41)
            # draw_icon(WINDOW_WIDTH - 18 - 18 - 2 - 4, 0, 20)

        self.config_button.draw()
        self.about_button.draw()

    def draw_background(self):
        buffer_as_arr = _image_as_ndarray(self.buffer)
        pyxel.cls(0)
        pyxel.pal(3, 5)
        pyxel.pal(11, 12)
        buffer_as_arr[:] = 0
        self.background_video.draw_image()

    def draw_stats_icon(
        self, x: int, y: int, icon: int, turns_counter: int | None = None
    ) -> None:
        draw_icon(x, y, icon)
        if turns_counter is not None:
            retro_text(
                x + 10, y + 6, f"{turns_counter}", 7, layout=layout(w=20, ha="left")
            )

    def draw_battlers(self):
        long_holder = load_image("ui", "long-holder.png")
        self.draw_player_info(long_holder)
        for i, sprite in enumerate(self.enemy_sprites):
            sprite.draw()

    def render_enemy_sprite(
        self, short_holder: pyxel.Image, i: int, x: int, e: EnemyBattler
    ) -> None:
        self.enemy_sprites[i].draw()
        pyxel.blt(10 + x - 36, 126, short_holder, 0, 0, 80, 64, colkey=254)
        shadowed_text(10 + x - 30, 121, e.name, 7, layout(w=80, ha="left"))
        self._draw_hearts_and_shields(10 + x - 31, 131, e.hp, e.shield_points)
        pyxel.clip(10 + x - 30 - 5, 141, 68, 7)
        text_width = retro_font.rasterize(e.current_intent, 5, 255, 0, 0).width + 14
        retro_text(
            -25 + x - (self.timer) % text_width,
            141,
            e.current_intent,
            col=7,
        )
        retro_text(
            -25 + x - (self.timer) % text_width + text_width,
            141,
            e.current_intent,
            col=7,
        )
        pyxel.clip()
        for i, s in enumerate(e.status_effects):
            turns_left = s.counter
            icon = s.icon_id
            self.draw_stats_icon(
                icon_x := 15 + x + i * 14, icon_y := 107, icon, turns_left
            )
            self.follower_tooltip_areas.append(
                FollowerTooltipArea(
                    icon_x,
                    icon_y,
                    16,
                    16,
                    s.name,
                    s.description,
                )
            )

    def draw_player_info(self, long_holder: pyxel.Image):
        player = self.bundle.player
        pyxel.blt(-10, 147 + 10, long_holder, 0, 0, 130, 30, colkey=254)
        self.player_sprite.draw()
        shadowed_text(51, 147 + 5, player.name_stem, 7, layout(w=80, ha="left"))
        self._draw_hearts_and_shields(50, 162, player.hp, player.shield_points)

    def draw_crosshair(self, x, y):
        cursor = load_image("cursor.png")
        pyxel.blt(x, y, cursor, 0, 0, 16, 16, colkey=254)

    def end_player_turn(self):
        self.tweens_signpost.append(
            range(6), Instant(lambda: self.add_signpost("Enemy Turn"))
        )
        for card_sprite in self.card_sprites:
            card_sprite.selected = False
        self.resolving_side = ResolvingSide.ENEMY
        for i, sprite in enumerate(self.card_sprites):
            sprite.try_transitioning_to_resolved(i, baseline=0.8)
        self.bundle.end_player_turn()
        self.framing.putup()
        self.futures.append(self.executor.submit(self.bundle.resolve_enemy_actions))

    def queue_up_future(self, *args, **kwargs):
        self.futures.append(self.executor.submit(*args, **kwargs))

    def start_new_turn(self):
        self.putup_player_signpost()
        self.bundle.start_new_turn()
        self.resolving_side = ResolvingSide.PLAYER

    def putup_player_signpost(self):
        self.tweens_signpost.append(
            range(6), Instant(lambda: self.add_signpost("Player Turn"))
        )


def gen_scene() -> Scene:
    return MainScene()
