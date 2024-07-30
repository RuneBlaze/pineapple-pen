import math

import numpy as np
import pyxel
from pyxelxl import layout

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH, load_image
from genio.components import (
    camera_shift,
    capital_hill_text,
    dithering,
    draw_rounded_rectangle,
    draw_window_frame,
)
from genio.gamestate import GameConfig
from genio.gears.button import (
    COLOR_SCHEME_PRIMARY,
    COLOR_SCHEME_SECONDARY,
    ButtonElement,
    vec2,
)
from genio.scene import Scene, module_scene
from genio.tween import Instant, Tweener

from genio.gamestate import game_state


def sin_01(t: float, dilation: float) -> float:
    return (math.sin(t * dilation) + 1) / 2


class RadioGroup:
    hovering: int | None

    def __init__(
        self, x: int, y: int, width: int, choices: list[str], chosen: int = 0
    ) -> None:
        self.c0 = 0
        self.c1 = 1
        self.x = x
        self.y = y
        self.width = width
        self.choices = choices
        self.chosen = chosen
        self.hovering = None
        self.last_hovering = None
        self.apparent_hovering = None
        self.apparent_chosen = chosen
        self.last_chosen = chosen
        self.tweener = Tweener()
        self.hovering_timer = 0

    def update(self) -> None:
        endpoints = np.linspace(self.x, self.x + self.width, len(self.choices) + 1)
        any_hovering = False
        for i, (start, end) in enumerate(zip(endpoints[:-1], endpoints[1:])):
            start, end = int(start), int(end)
            if (
                pyxel.mouse_x >= start
                and pyxel.mouse_x <= end
                and pyxel.mouse_y >= self.y
                and pyxel.mouse_y <= self.y + 11
            ):
                self.hovering = i
                if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                    self.chosen = i
                any_hovering = True
                break
        if not any_hovering:
            self.hovering = None
        self.tweener.update()
        if self.hovering is not None:
            self.hovering_timer += 1
        else:
            self.hovering_timer = 0

        if self.last_chosen != self.chosen:
            self.last_chosen = self.chosen
            self.tweener.append_mutate(
                self, "apparent_chosen", 8, self.chosen, "ease_in_out_cubic"
            )

    def draw(self) -> None:
        draw_rounded_rectangle(self.x, self.y, self.width, 11, 5, self.c1)
        endpoints = np.linspace(self.x, self.x + self.width, len(self.choices) + 1)
        start = self.x + self.apparent_chosen * (self.width // len(self.choices))
        draw_rounded_rectangle(
            start, self.y, self.width // len(self.choices), 11, 5, 14
        )
        if self.hovering is not None:
            with dithering(0.5 * sin_01(self.hovering_timer, 0.15)):
                start = self.x + self.hovering * (self.width // len(self.choices))
                draw_rounded_rectangle(
                    start, self.y, self.width // len(self.choices), 11, 5, 14
                )
        for i, (start, end) in enumerate(zip(endpoints[:-1], endpoints[1:])):
            start, end = int(start), int(end)
            w = end - start
            if self.apparent_chosen and i == round(self.apparent_chosen):
                capital_hill_text(
                    start + 1,
                    self.y,
                    self.choices[i],
                    1,
                    layout=layout(h=16, va="center", w=w, ha="center"),
                )
            else:
                capital_hill_text(
                    start + 1,
                    self.y,
                    self.choices[i],
                    7,
                    layout=layout(h=16, va="center", w=w, ha="center"),
                )


class ConfigMenu:
    def __init__(self, x: int, y: int, game_config: GameConfig) -> None:
        self.game_config = game_config
        self.x = x
        self.y = y
        self.opacity = 1.0
        self.radios = []
        self.radios.append(RadioGroup(self.x + 100, self.y + 5, 80, ["Off", "On"]))
        self.radios.append(
            RadioGroup(self.x + 100, self.y + 5 + 16, 80, ["0", "1", "2", "3", "4"])
        )
        self.radios.append(
            RadioGroup(self.x + 100, self.y + 5 + 16 * 2, 80, ["0", "1", "2", "3", "4"])
        )
        self.confirm_button = ButtonElement(
            "Confirm", COLOR_SCHEME_PRIMARY, vec2(self.x + 102, self.y + 6 + 16 * 3), ""
        )
        self.reset_button = ButtonElement(
            "Reset",
            COLOR_SCHEME_SECONDARY,
            vec2(self.x + 100 - 57, self.y + 6 + 16 * 3),
            "",
        )
        self.sync()
    
    def sync(self) -> None:
        game_config = self.game_config
        self.radios[0].chosen = 1 if game_config.larger_font else 0
        self.radios[1].chosen = game_config.music_volume
        self.radios[2].chosen = game_config.sfx_volume

    def draw(self) -> None:
        width = 200
        height = 75
        col1_width = 80
        draw_window_frame(self.x, self.y, width, height, 5)
        default_layout = layout(h=16, va="center", w=col1_width, ha="right")
        capital_hill_text(
            self.x + 5, self.y + 5, "Larger Font", 7, layout=default_layout
        )
        capital_hill_text(
            self.x + 5, self.y + 5 + 16, "Music Volume", 7, layout=default_layout
        )
        capital_hill_text(
            self.x + 5, self.y + 5 + 16 * 2, "Sfx Volume", 7, layout=default_layout
        )
        self.confirm_button.draw_at()
        self.reset_button.draw_at()
        for radio in self.radios:
            radio.draw()

    def update(self) -> None:
        for radio in self.radios:
            radio.update()
        self.confirm_button.update()
        self.reset_button.update()


@module_scene
class ConfigMenuScene(Scene):
    def __init__(self) -> None:
        self.tweener = Tweener()
        self.background_opacity = 0.0
        self.config_menu = ConfigMenu((WINDOW_WIDTH - 200) // 2, 70, game_state.config)
        self.tweener.append_mutate(
            self,
            "background_opacity",
            30,
            0.5,
            "ease_in_quad",
        )
        self.dead = False

    def mark_dead(self) -> None:
        self.dead = True

    def draw(self) -> None:
        with dithering(0.5 * self.background_opacity):
            pyxel.rect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, 1)
        with dithering(2 * self.background_opacity):
            with camera_shift(0, 2.5 - 5 * self.background_opacity):
                self.config_menu.draw()
        self.draw_mouse_cursor(pyxel.mouse_x, pyxel.mouse_y)

    def sync(self) -> None:
        config = game_state.config
        config.larger_font = self.config_menu.radios[0].chosen == 1
        config.music_volume = self.config_menu.radios[1].chosen
        config.sfx_volume = self.config_menu.radios[2].chosen
    
    def reset(self) -> None:
        game_state.config.reset()
        self.config_menu.sync()

    def update(self) -> None:
        self.tweener.update()
        self.config_menu.update()
        if self.config_menu.confirm_button.btnp and not self.tweener:
            self.sync()
            self.tweener.append_mutate(
                self,
                "background_opacity",
                30,
                0.0,
                "ease_in_quad",
            )
            self.tweener.append(Instant(self.mark_dead))
        if self.config_menu.reset_button.btnp:
            self.reset()

    def request_next_scene(self) -> Scene | None | str:
        if self.dead:
            return "title"
        return None

    def draw_mouse_cursor(self, x: int, y: int) -> None:
        cursor = load_image("cursor.png")
        pyxel.blt(x, y, cursor, 0, 0, 16, 16, colkey=254)
