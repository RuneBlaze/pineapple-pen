import os
from functools import cache

import numpy as np
import pyxel
from PIL import Image
from pyxelxl.font import _image_as_ndarray

WORKING_DIR = os.getcwd()

WINDOW_WIDTH, WINDOW_HEIGHT = 427, 240


def asset_path(*args: str):
    return os.path.join(WORKING_DIR, "assets", *args)


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
def load_image(*asset_args: str) -> pyxel.Image:
    image_path = asset_path(*asset_args)
    rgb2paletteix = calculate_rgb2paletteix()
    # Convert to ndarray
    image = Image.open(image_path).convert("RGBA")
    buffer = np.full((image.height, image.width), 254, dtype=np.uint8)

    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = image.getpixel((x, y))
            if a != 0:
                if a != 255:
                    raise ValueError(f"Unexpected alpha value: {a}")
                try:
                    buffer[y, x] = rgb2paletteix[(r, g, b)]
                except KeyError:
                    rgb = (r, g, b)
                    closest_color = min(
                        rgb2paletteix.keys(),
                        key=lambda c: sum((c[i] - rgb[i]) ** 2 for i in range(3)),
                    )
                    raise ValueError(f"Unexpected color: {r}, {g}, {b}; closest: {closest_color} at {rgb2paletteix[closest_color]}")
    pimage = pyxel.Image(image.width, image.height)
    _image_as_ndarray(pimage)[:] = buffer
    return pimage
