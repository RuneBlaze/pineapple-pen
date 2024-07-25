import itertools
from dataclasses import dataclass
from functools import cache
from random import randrange

import pytweening
import pyxel
from pyxelxl import blt_rot

from genio.base import load_image
from genio.components import dithering
from genio.scene import Scene
from genio.tween import Mutator, Tweener


@cache
def calculate_rgb2paletteix() -> dict:
    palette = pyxel.colors.to_list()
    rgb2paletteix = {}
    for i, rgb in enumerate(palette):
        r = rgb >> 16 & 0xFF
        g = rgb >> 8 & 0xFF
        b = rgb & 0xFF
        rgb2paletteix[(r, g, b)] = i
    return rgb2paletteix


@cache
def calculate_paletteix2rgb() -> dict:
    return {v: k for k, v in calculate_rgb2paletteix().items()}


def median_color(arr: list[int]) -> int:
    if not arr:
        raise ValueError("Empty array")
    forward = calculate_paletteix2rgb()

    def ix2brightness(ix: int) -> float:
        return rgb_u8_to_brightness_f32(forward[ix])

    arr.sort(key=ix2brightness)
    return arr[len(arr) // 2]


def rgb_u8_to_brightness_f32(rgb: tuple[int, int, int]) -> float:
    return 0.299 * rgb[0] / 255 + 0.587 * rgb[1] / 255 + 0.114 * rgb[2] / 255


@dataclass
class Patch:
    image: pyxel.Image
    patch_x: int
    patch_y: int

    grid_w: int
    grid_h: int


def patchify(image: pyxel.Image, grid_w: int, grid_h: int) -> list[Patch]:
    patches = []
    image_w, image_h = image.width, image.height
    if not image_w % grid_w == 0:
        raise ValueError("Image width must be a multiple of grid width")
    if not image_h % grid_h == 0:
        raise ValueError("Image height must be a multiple of grid height")
    for y in range(0, image.height, grid_h):
        for x in range(0, image.width, grid_w):
            patch = Patch(image, x, y, grid_w, grid_h)
            patches.append(patch)
    return patches


class ImagePiece:
    vel_x: int
    vel_y: int

    def __init__(self, x: int, y: int, patch: Patch):
        self.x = x
        self.y = y
        self.patch = patch
        self.rotation = 0.0
        self.tweener = Tweener()
        self.opacity = 1.0

        self.vel_x = randrange(2, 6)
        self.vel_y = randrange(-2, 2)

        target_rot = randrange(-180, 180)

        self.timer = 0

        total_duration = 60

        self.tweener.append(
            itertools.zip_longest(
                Mutator(
                    lens="x",
                    duration=total_duration,
                    target=self.x + self.vel_x * 8,
                    inner=pytweening.easeInQuad,
                    this=self,
                ),
                Mutator(
                    lens="y",
                    duration=total_duration,
                    target=self.y + self.vel_y * 8,
                    inner=pytweening.easeInQuad,
                    this=self,
                ),
                Mutator(
                    lens="rotation",
                    duration=total_duration,
                    target=target_rot,
                    inner=pytweening.easeInOutQuad,
                    this=self,
                ),
                Mutator(
                    lens="opacity",
                    duration=total_duration,
                    target=0.0,
                    inner=pytweening.easeInOutQuad,
                    this=self,
                ),
            )
        )

    def update(self):
        self.tweener.update()
        self.timer += 1

    def is_dead(self) -> bool:
        return self.timer >= 60

    def draw(self):
        with dithering(self.opacity):
            blt_rot(
                self.x,
                self.y,
                self.patch.image,
                self.patch.patch_x,
                self.patch.patch_y,
                self.patch.grid_w,
                self.patch.grid_h,
                254,
                self.rotation,
            )


def sprite_to_pieces(x: int, y: int, image: pyxel.Image) -> list[ImagePiece]:
    patches = patchify(image, 8, 8)
    pieces = []
    for patch in patches:
        piece = ImagePiece(patch.patch_x + x, patch.patch_y + y, patch)
        pieces.append(piece)
    return pieces


class ScenePieceThing(Scene):
    def __init__(self) -> None:
        self.pieces = []
        image = load_image("char", "enemy_killer_flower.png")
        self.pieces.extend(sprite_to_pieces(100, 100, image))

    def update(self) -> None:
        for piece in self.pieces:
            piece.update()

    def draw(self) -> None:
        pyxel.cls(0)
        for piece in self.pieces:
            piece.draw()


def gen_scene() -> Scene:
    return ScenePieceThing()
