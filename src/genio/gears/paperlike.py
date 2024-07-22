from functools import cache

import numba
import numpy as np
import pyxel
from pyxelxl.font import _image_as_ndarray
from pyxelxl.pyxelxl import rotate

from genio.base import load_image
from genio.ps import uv_for_16


def rotate_image(image: pyxel.Image, angle: int) -> pyxel.Image:
    buffer = _image_as_ndarray(image)
    new_buffer = rotate(buffer, 0, angle)
    new_image = pyxel.Image(new_buffer.shape[1], new_buffer.shape[0])
    _image_as_ndarray(new_image)[:] = new_buffer
    return new_image


def zoom_2x(image: pyxel.Image) -> pyxel.Image:
    buffer = _image_as_ndarray(image)
    new_buffer = np.zeros(
        (buffer.shape[0] * 2, buffer.shape[1] * 2), dtype=buffer.dtype
    )
    for i in range(buffer.shape[0]):
        for j in range(buffer.shape[1]):
            new_buffer[i * 2, j * 2] = buffer[i, j]
            new_buffer[i * 2 + 1, j * 2] = buffer[i, j]
            new_buffer[i * 2, j * 2 + 1] = buffer[i, j]
            new_buffer[i * 2 + 1, j * 2 + 1] = buffer[i, j]
    new_image = pyxel.Image(new_buffer.shape[1], new_buffer.shape[0])
    _image_as_ndarray(new_image)[:] = new_buffer
    return new_image


GRANULARITY = 20


class PrerotatedImage:
    def __init__(self, spr: int) -> None:
        self.images = []
        source_image = pyxel.Image(8, 8)
        source_image.blt(0, 0, 1, *uv_for_16(spr), 8, 8)
        source_image = zoom_2x(source_image)
        for i in range(0, 360, GRANULARITY):
            self.images.append(rotate_image(source_image, i))

    def image_for_angle(self, angle: int) -> pyxel.Image:
        angle = int(angle)
        angle -= GRANULARITY // 2
        if angle < 0:
            angle += 360
        angle = angle % 360
        return self.images[round(angle / GRANULARITY) % len(self.images)]

    def draw_centered(self, x: int, y: int, angle: int) -> None:
        image = self.image_for_angle(angle)
        pyxel.blt(
            x - image.width // 2,
            y - image.height // 2,
            image,
            0,
            0,
            image.width,
            image.height,
            0,
        )


def draw_icon(x: int, y: int, icon_id: int) -> None:
    icons = load_image("icons.png")
    icon_w, icon_h = 16, 16
    num_horz = icons.width // icon_w

    icon_x = icon_id % num_horz
    icon_y = icon_id // num_horz

    pyxel.blt(x, y, icons, icon_x * icon_w, icon_y * icon_h, icon_w, icon_h, colkey=254)


def draw_rounded_rectangle(x: int, y: int, w: int, h: int, r: int, col: int) -> None:
    pyxel.rect(x + r, y, w - 2 * r + 1, h + 1, col)
    pyxel.rect(x, y + r, r, h - 2 * r, col)
    pyxel.rect(x + w - r + 1, y + r, r, h - 2 * r, col)
    pyxel.circ(x + r, y + r, r, col)
    pyxel.circ(x + w - r, y + r, r, col)
    pyxel.circ(x + r, y + h - r, r, col)
    pyxel.circ(x + w - r, y + h - r, r, col)


@numba.jit(nopython=True)
def remove_isolated_pixels(image: np.ndarray, bg_color: int) -> np.ndarray:
    h, w = image.shape
    output = image.copy()
    for i in range(1, h - 1):
        for j in range(1, w - 1):
            if image[i, j] != bg_color:
                # Check 8-neighbors
                is_isolated = True
                for di in range(-1, 2):
                    for dj in range(-1, 2):
                        if (di != 0 or dj != 0) and image[i + di, j + dj] != bg_color:
                            is_isolated = False
                            break
                    if not is_isolated:
                        break
                if is_isolated:
                    output[i, j] = bg_color
    return output


@numba.jit(nopython=True)
def apply_paper_cut_effect(
    image: np.ndarray, bg_color: int, radius: int = 3, fill_color: int | None = None
) -> np.ndarray:
    h, w = image.shape
    if fill_color is None:
        fill_color = bg_color
    output = np.full_like(image, 254)
    for i in range(h):
        for j in range(w):
            if image[i, j] != bg_color:
                output[i, j] = image[i, j]
            else:
                # Calculate if this bg pixel is within 3 pixels distance to any non-bg pixel
                for di in range(-3, 4):
                    for dj in range(-3, 4):
                        ni, nj = i + di, j + dj
                        if (
                            0 <= ni < h
                            and 0 <= nj < w
                            and np.sqrt(di**2 + dj**2) <= radius
                        ):
                            if image[ni, nj] != bg_color:
                                output[i, j] = fill_color
                                break
    return output


def _paper_cut_effect(
    image: np.ndarray, bg_color: int, fill_color: int | None = None
) -> np.ndarray:
    cleaned_image = remove_isolated_pixels(image, bg_color)
    result_image = apply_paper_cut_effect(
        cleaned_image, bg_color, fill_color=fill_color, radius=2
    )
    return result_image


def paper_cut_effect(
    image: pyxel.Image, bg_color: int = 7, fill_color: int | None = None
) -> pyxel.Image:
    buffer = _image_as_ndarray(image)
    new_buffer = _paper_cut_effect(buffer, bg_color, fill_color=fill_color)
    new_image = pyxel.Image(new_buffer.shape[1], new_buffer.shape[0])
    _image_as_ndarray(new_image)[:] = new_buffer
    return new_image


@cache
def paper_cut_asset(*asset_path: str) -> pyxel.Image:
    """Load an image asset and apply the paper cut effect to it."""

    image = load_image(*asset_path)
    return paper_cut_effect(image)
