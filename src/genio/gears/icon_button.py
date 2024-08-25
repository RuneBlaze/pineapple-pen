import pyxel
from pyxelxl import layout

from genio.components import dithering, draw_icon, pal_single_color
from genio.gears.fontpack import fonts
from genio.gears.maths_utils import sin_01


class IconButton:
    def __init__(self, x: int, y: int, icon: int, label: str = "") -> None:
        self.hovering = False
        self.btnp = False
        self.hovering_timer = 0

        self.x = x
        self.y = y
        self.icon = icon
        self.label = label

    def update(self) -> None:
        from genio.scene import MouseDownEvent, input_events

        w = 16
        h = 16
        if self.label:
            w += 36
        if (
            pyxel.mouse_x >= self.x
            and pyxel.mouse_x < self.x + w
            and pyxel.mouse_y >= self.y
            and pyxel.mouse_y < self.y + h
        ):
            self.hovering = True
            self.btnp = False
            for event in input_events():
                match event:
                    case MouseDownEvent(_mouse_x, _mouse_y, False) as event:
                        self.btnp = True
                        event.stop_propagation()
        else:
            self.hovering = False
            self.btnp = False

        if self.hovering:
            self.hovering_timer += 1
        else:
            self.hovering_timer = 0

    def draw(self) -> None:
        if label := self.label:
            pyxel.rect(self.x, self.y, 36 + 16, self.y + 16, 1)
            if self.hovering:
                with dithering(0.5):
                    pyxel.rect(self.x, self.y, 36 + 16, self.y + 16, 7)
            for shift in [(0, 1), (0, -1), (-1, 0), (1, 0)]:  # shadow
                fonts.capital_hill(
                    self.x + 16 + shift[0],
                    self.y + shift[1],
                    label,
                    1,
                    layout=layout(36, 16, ha="center", va="center"),
                )
            fonts.capital_hill(
                self.x + 16,
                self.y,
                label,
                7,
                layout=layout(36, 16, ha="center", va="center"),
            )
        draw_icon(self.x, self.y, self.icon)
        if self.hovering:
            with dithering(0.5 * sin_01(self.hovering_timer, 0.15)):
                with pal_single_color(7):
                    draw_icon(self.x, self.y, self.icon)
