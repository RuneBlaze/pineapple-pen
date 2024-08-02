import functools

import numpy as np
import pyxel
from pyxelxl import Font, layout
from pyxelxl.font import _image_as_ndarray

from genio.base import asset_path, load_image
from genio.card import Card
from genio.components import retro_font
from genio.constants import CARD_HEIGHT, CARD_WIDTH
from genio.gears.spritesheet import Spritesheet
from genio.scene import Scene, module_scene

card_text = Font(asset_path("Capital_Hill.ttf")).specialize(font_size=8)


def copy_image(image: pyxel.Image) -> pyxel.Image:
    img = pyxel.Image(image.width, image.height)
    img.blt(0, 0, image, 0, 0, image.width, image.height)
    return img


def center_crop(img: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    h, w = img.shape[:2]
    if h < size[0] or w < size[1]:
        raise ValueError("Image is smaller than the crop size")
    x = (w - size[1]) // 2
    y = (h - size[0]) // 2
    return img[y : y + size[0], x : x + size[1]]


def paste_center(
    src: np.ndarray, target: np.ndarray, offset: int = 0, ignore: int | None = None
) -> None:
    x = (target.shape[1] - src.shape[1]) // 2
    y = (target.shape[0] - src.shape[0]) // 2
    if ignore is not None:
        target[y + offset : y + src.shape[0] + offset, x : x + src.shape[1]] = np.where(
            src == ignore,
            target[y + offset : y + src.shape[0] + offset, x : x + src.shape[1]],
            src,
        )
    else:
        target[y + offset : y + src.shape[0] + offset, x : x + src.shape[1]] = src[:]


@functools.cache
def empty_card() -> pyxel.Image:
    return pyxel.Image.from_image(asset_path("card.png"))


def printable_tokens(word: str) -> list[str] | None:
    if len(word) <= 9:
        return [word]
    if " " not in word:
        return None
    tokens = word.split()
    if len(tokens) > 2:
        return None
    if all(printable_tokens(token) for token in tokens):
        return tokens


class CardPrinter:
    def __init__(self) -> None:
        self.spritesheet = Spritesheet(
            [asset_path("preprocess.json"), asset_path("card_art.json")],
            build_search_index=True,
        )

    def print_card(self, card: Card) -> pyxel.Image:
        card_name = card.name
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
                return image
            case "The Emperor":
                image = copy_image(load_image("cards", "the-emperor.png"))
                return image
            case "Block":
                image = copy_image(load_image("cards", "block.png"))
                return image
            case "Slash":
                image = copy_image(load_image("cards", "slash.png"))
                return image
            case "left":
                image = copy_image(load_image("cards", "left.png"))
                return image
            case "right":
                image = copy_image(load_image("cards", "right.png"))
                return image
            case "Smash":
                image = copy_image(load_image("cards", "smash.png"))
                return image
            case _:
                return self._print_card(card)

    def _print_card(self, card: Card) -> pyxel.Image:
        if card.is_flashcard_like():
            image = copy_image(load_image("card_flash.png"))
            self.add_flashcard_text_to_card(card.name, image)
            return image
        image = copy_image(empty_card())
        background = self.spritesheet.search_image(card.name)
        return self.render_card_image(card, image, background)

    def render_card_image(
        self, card: Card, image: pyxel.Image, background: pyxel.Image
    ) -> pyxel.Image:
        bg_arr = _image_as_ndarray(background)
        bg_arr = center_crop(bg_arr, (CARD_HEIGHT - 4, CARD_WIDTH - 4))
        paste_center(bg_arr, _image_as_ndarray(image), ignore=254)
        image.pset(2, 2, 7)
        image.pset(CARD_WIDTH - 3, 2, 7)
        image.pset(2, CARD_HEIGHT - 3, 7)
        image.pset(CARD_WIDTH - 3, CARD_HEIGHT - 3, 7)
        single_word = card.name
        printables = printable_tokens(single_word)
        if printables:
            for rot180_i, single_word in enumerate(printables):
                rot180 = bool(rot180_i)
                self.print_text(image, single_word, rot180)
        return image

    def print_text(self, image: pyxel.Image, single_word: str, rot180: bool):
        skip = False
        if len(single_word) <= 5:
            compression = 0
            y_mult = 9
        elif len(single_word) <= 7:
            compression = 1
            y_mult = 8
        elif len(single_word) <= 9:
            compression = 2
            y_mult = 6
        else:
            skip = True
        if not skip:
            for i, ch in enumerate(single_word):
                y_offset = y_mult * i + 4
                if compression >= 1:
                    y_offset -= 1
                bx = 2
                if compression >= 2:
                    bx += 3 * (i % 2)
                self.apply_serif_text(image, i, ch, y_offset, bx, compression, rot180)

    def add_flashcard_text_to_card(self, text: str, image: pyxel.Image) -> None:
        rasterized = retro_font.rasterize(
            text,
            5,
            254,
            fg_col=0,
            bg_col=7,
            layout=layout(
                w=CARD_HEIGHT,
                ha="center",
                h=CARD_WIDTH,
                va="center",
            ),
        )
        rasterized = _image_as_ndarray(rasterized)
        pad_width = CARD_HEIGHT - rasterized.shape[1]
        rasterized = np.pad(rasterized, ((0, pad_width), (0, 0)), constant_values=7)
        rasterized = np.rot90(rasterized)
        rasterized = np.pad(rasterized, ((pad_width, 0), (0, 0)), constant_values=7)
        # blt manually
        for y, row in enumerate(rasterized):
            for x, col in enumerate(row):
                if col != 0:
                    continue
                image.pset(x, y, col)

    def apply_serif_text(
        self,
        image: pyxel.Image,
        i: int,
        ch: str,
        y_offset: int,
        bx: int,
        compression: int = 0,
        rot180: bool = False,
    ) -> None:
        if compression <= 0:
            ch = ch.upper()
        elif compression >= 1:
            ch = ch.lower()
        copied = pyxel.Image(CARD_WIDTH, CARD_HEIGHT)
        copied_data = _image_as_ndarray(copied)
        copied_data[:] = 254
        for dx, dy in [(-1, 0), (1, 0), (0, 1), (0, -1)]:
            card_text(
                bx + dx,
                y_offset + dy,
                ch,
                0,
                layout=layout(w=11, ha="center"),
                target=copied,
            )
        card_text(
            bx,
            y_offset,
            ch,
            7,
            layout=layout(w=11, ha="center"),
            target=copied,
        )
        if rot180:
            copied_data[:] = np.rot90(copied_data, 2)
        paste_center(
            _image_as_ndarray(copied),
            _image_as_ndarray(image),
            offset=0,
            ignore=254,
        )


@module_scene
class CardPrinterTestScene(Scene):
    def __init__(self) -> None:
        super().__init__()
        self.card = Card(name="Inland Empire")
        self.card_image = CardPrinter().print_card(self.card)
        self.another_image = load_image("card_smash.png")

    def update(self) -> None:
        pass

    def draw(self) -> None:
        pyxel.cls(0)
        pyxel.blt(0, 0, self.card_image, 0, 0, CARD_WIDTH, CARD_HEIGHT)
        pyxel.blt(50, 0, self.another_image, 0, 0, CARD_WIDTH, CARD_HEIGHT, colkey=254)

    def on_exit(self) -> None:
        pass

    def on_enter(self) -> None:
        pass
