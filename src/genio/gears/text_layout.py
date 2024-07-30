import textwrap

import pyxel
from pyxel import Image
from pyxelxl import LayoutOpts
from pyxelxl.font import DrawTextLike


def text_width(s: str) -> int:
    return len(s) * 4


class PyxelDefaultFont(DrawTextLike):
    def __call__(
        self,
        x: int,
        y: int,
        s: str,
        col: int,
        layout: LayoutOpts | None = ...,
        target: Image | None = ...,
    ) -> None:
        if target:
            raise ValueError("PyxelDefaultFont does not support target")
        if not layout:
            pyxel.text(x, y, s, col)
            return
        wrapped = textwrap.wrap(s, width=layout.max_width // 4)
        for i, line in enumerate(wrapped):
            x_pad = 0
            if layout.horizontal_align == "center":
                x_pad = (layout.max_width - text_width(line)) // 2
            elif layout.horizontal_align == "right":
                x_pad = layout.max_width - text_width(line)
            pyxel.text(x + x_pad, y + i * 6, line, col)


pyxel_text = PyxelDefaultFont()
