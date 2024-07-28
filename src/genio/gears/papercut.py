import numba
import numpy as np
import pyxel
from pyxelxl.font import _image_as_ndarray


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
    image: np.ndarray, bg_color: int, radius: int = 1, fill_color: int | None = None
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
        cleaned_image, bg_color, fill_color=fill_color
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
