import pyxel

from genio.components import dithering, draw_icon, pal_single_color
from genio.gears.maths_utils import sin_01


class IconButton:
    def __init__(self, x: int, y: int, icon: int) -> None:
        self.hovering = False
        self.btnp = False
        self.hovering_timer = 0

        self.x = x
        self.y = y
        self.icon = icon

    def update(self) -> None:
        w = 16
        h = 16
        if (
            pyxel.mouse_x >= self.x
            and pyxel.mouse_x < self.x + w
            and pyxel.mouse_y >= self.y
            and pyxel.mouse_y < self.y + h
        ):
            self.hovering = True
            if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                self.btnp = True
            else:
                self.btnp = False
        else:
            self.hovering = False
            self.btnp = False

        if self.hovering:
            self.hovering_timer += 1
        else:
            self.hovering_timer = 0

    def draw(self) -> None:
        draw_icon(self.x, self.y, self.icon)
        if self.hovering:
            with dithering(0.5 * sin_01(self.hovering_timer, 0.15)):
                with pal_single_color(7):
                    draw_icon(self.x, self.y, self.icon)
