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


class Video:
    def __init__(self, *args: str) -> None:
        self.raw = np.load(asset_path(*args))
        self.num_frames = self.raw.shape[0]
        self.timer = 0
        self.images = [buffer_to_image(frame) for frame in self.raw]
        self.actual_timer = 0
        self.masks = [
            buffer_to_image(self.generate_mask(thres))
            for thres in [0.7, 0.6, 0.8, 0.5, 0.3]
        ]
        self.appearance = np.random.rand(WINDOW_HEIGHT, WINDOW_WIDTH)

    def update(self):
        self.actual_timer += 1
        self.timer += self.actual_timer % 3
        if self.timer == self.num_frames:
            self.timer = 0

    @property
    def current_image(self):
        return self.images[self.timer]

    def generate_mask(self, threshold) -> np.ndarray:
        mask = np.zeros((WINDOW_HEIGHT, WINDOW_WIDTH), dtype=np.float32)
        for i in range(0, WINDOW_HEIGHT):
            for j in range(0, WINDOW_WIDTH):
                u = ((i / WINDOW_HEIGHT) - 0.5) / 0.5
                v = ((j / WINDOW_WIDTH) - 0.5) / 0.5
                mask[i, j] = u**2 * 0.5 + v**2 * 0.5
        mask = np.clip(mask, 0, 1)
        buffer = np.full((WINDOW_HEIGHT, WINDOW_WIDTH), 254, dtype=np.uint8)
        buffer[mask > threshold] = 0
        return buffer


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


def load_as_buffer(*asset_args: str) -> np.ndarray:
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
                    raise ValueError(
                        f"Unexpected color: {r}, {g}, {b}; closest: {closest_color} at {rgb2paletteix[closest_color]} when loading {image_path}"
                    )
    return buffer


@cache
def load_image(*asset_args: str) -> pyxel.Image:
    buffer = load_as_buffer(*asset_args)
    pimage = pyxel.Image(buffer.shape[1], buffer.shape[0])
    _image_as_ndarray(pimage)[:] = buffer
    return pimage


def buffer_to_image(buffer: np.ndarray) -> pyxel.Image:
    pimage = pyxel.Image(buffer.shape[1], buffer.shape[0])
    _image_as_ndarray(pimage)[:] = buffer
    return pimage


def resize_image_breathing(image: pyxel.Image, num_cut: int) -> pyxel.Image:
    rows_to_takeout = np.linspace(0, image.height, num_cut + 2, dtype=int)[1:-1]
    empty_rows = np.full((num_cut, image.width), 254, dtype=np.uint8)
    buffer = np.delete(_image_as_ndarray(image), rows_to_takeout, axis=0)
    buffer = np.concatenate((empty_rows, buffer), axis=0)
    pimage = pyxel.Image(image.width, image.height)
    _image_as_ndarray(pimage)[:] = buffer
    return pimage


if __name__ == "__main__":
    import numpy as np
    from PIL import Image
    # img = Image.open("assets/mask.png").convert("RGB")
    # luminance = np.zeros((img.height, img.width), dtype=np.uint8)
    # # each pixel
    # for i in range(img.height):
    #     for j in range(img.width):
    #         r, g, b = img.getpixel((j, i))
    #         r, g, b = r / 255.0, g / 255.0, b / 255.0
    #         luminance[i, j] = min(int((0.299 * r + 0.587 * g + 0.114 * b) * 255), 255)
    # np.save("assets/mask.npy", luminance)

    # load mask.npy and visualize it

    mask = np.load("assets/mask.npy")
    img = Image.fromarray(mask)
    img.show()

# import glob

# ok = sorted(glob.glob("assets/background/*.png"))
# if __name__ == "__main__":
#     pyxel.init(WINDOW_WIDTH, WINDOW_HEIGHT)
#     buffers = []
#     for file in ok:
#         image = load_as_buffer("background", file.split("/")[-1])
#         buffers.append((int(file.split("/")[-1].split(".")[0]), image))
#     sorted_buffers = sorted(buffers, key=lambda x: x[0])
#     stack = np.stack([x[1] for x in sorted_buffers])
#     np.save("background.npy", stack)
