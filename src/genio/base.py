import os
from collections import Counter
from enum import Enum
from functools import cache
from glob import glob
from hashlib import sha256

import numpy as np
import pyxel
from PIL import Image
from pyxelxl.font import _image_as_ndarray

if working_dir := os.environ.get("PYXEL_WORKING_DIR"):
    WORKING_DIR = working_dir
else:
    working_dir = os.getcwd()
    os.environ["PYXEL_WORKING_DIR"] = working_dir
    WORKING_DIR = working_dir

WINDOW_WIDTH, WINDOW_HEIGHT = 427, 240


def asset_path(*args: str):
    if os.path.isabs(args[0]):
        return args[0]
    return os.path.join(WORKING_DIR, "assets", *args)


class VideoState(Enum):
    PLAYING = 1
    REWINDING = 2


def cached_video_path(*args: str):
    p = asset_path(*args)
    return asset_path(sha256(p.encode()).hexdigest()[0:8] + ".npz")


class Video:
    def __init__(self, *args: str) -> None:
        image_paths = sorted(glob(asset_path(*args)))
        cached_path = cached_video_path(*args)
        if os.path.exists(cached_path):
            self.images = np.load(cached_path)["images"]
            self.images = [buffer_to_image(i) for i in self.images]
            self.num_frames = len(self.images)
        else:
            self.num_frames = len(image_paths)
            self.images = [load_image(p) for p in image_paths]
            np.savez_compressed(
                cached_path, images=[_image_as_ndarray(i) for i in self.images]
            )
        self.timer = 0

        self.actual_timer = 0
        self.masks = [
            buffer_to_image(self.generate_mask(thres))
            for thres in [0.7, 0.6, 0.8, 0.5, 0.3]
        ]
        self.state = VideoState.PLAYING
        self.state_timers = Counter()
        self.appearance = np.random.rand(WINDOW_HEIGHT, WINDOW_WIDTH)

    def update(self) -> None:
        if self.state == VideoState.PLAYING:
            self.actual_timer += 1
            if self.actual_timer % 2 == 0:
                self.timer += 1
            if self.timer == self.num_frames:
                self.timer = 0
                self.state = VideoState.REWINDING
                self.state_timers[self.state] = 0
        else:
            if self.state_timers[self.state] >= 30:
                self.state = VideoState.PLAYING
                self.state_timers[self.state] = 0
        self.state_timers[self.state] += 1

    @property
    def current_image(self):
        return self.images[self.timer]

    def draw_image(self) -> None:
        match self.state:
            case VideoState.PLAYING:
                pyxel.blt(0, 0, self.current_image, 0, 0, 427, 240, 0)
            case VideoState.REWINDING:
                pyxel.blt(0, 0, self.images[-1], 0, 0, 427, 240, 0)
                dither_factor = min(self.state_timers[self.state] / 30, 1)
                pyxel.dither(dither_factor)
                pyxel.blt(0, 0, self.images[self.timer], 0, 0, 427, 240, 0)
                pyxel.dither(1.0)

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


def split_as_spritesheet(asset_args: tuple[str, ...]) -> tuple[list[str], str] | None:
    if len(asset_args) >= 2 and asset_args[-2].endswith(".json"):
        return asset_args[:-1], asset_args[-1]
    return None


@cache
def image_open_cached(image_path: str) -> Image.Image:
    return Image.open(image_path)


def levenstein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenstein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def closest_string_match(s: str, strings: list[str]) -> str:
    return min(strings, key=lambda x: levenstein_distance(s, x))


def pil_image_from_spritesheet(asset_args: list[str], k: str) -> Image.Image:
    json_path = asset_path(*asset_args)
    image_path = json_path.replace(".json", ".png")
    import json

    with open(json_path) as f:
        data = json.load(f)
    lookup = {}
    for frame_name, frame_metadata in data["frames"].items():
        frame_name = frame_name.replace(" ", "_")
        frame_name = frame_name.split(".")[0]
        lookup[frame_name] = frame_metadata
    try:
        frame_metadata = lookup[k]
    except KeyError:
        raise ValueError(
            f"Invalid frame name: {k}. Closest match: {closest_string_match(k, lookup.keys())}"
        )
    match frame_metadata["frame"]:
        case {"x": x, "y": y, "w": w, "h": h}:
            parent = image_open_cached(image_path).convert("RGBA")
            return parent.crop((x, y, x + w, y + h))
        case _:
            raise ValueError("Invalid frame metadata")


def load_as_buffer(*asset_args: str) -> np.ndarray:
    rgb2paletteix = calculate_rgb2paletteix()
    if split := split_as_spritesheet(asset_args):
        spritesheet_args, k = split
        image = pil_image_from_spritesheet(spritesheet_args, k)
    else:
        image_path = asset_path(*asset_args)
        image = Image.open(image_path).convert("RGBA")
    buffer = apply_palette_conversion(rgb2paletteix, image)
    return buffer


def apply_palette_conversion(rgb2paletteix, image: Image.Image) -> np.ndarray:
    buffer = np.full((image.height, image.width), 254, dtype=np.uint8)

    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = image.getpixel((x, y))
            if a != 0:
                if a != 255:
                    ...
                try:
                    buffer[y, x] = rgb2paletteix[(r, g, b)]
                except KeyError:
                    rgb = (r, g, b)
                    closest_color = min(
                        rgb2paletteix.keys(),
                        key=lambda c: sum((c[i] - rgb[i]) ** 2 for i in range(3)),
                    )
                    raise ValueError(
                        f"Unexpected color: {r}, {g}, {b}; closest: {closest_color} at {rgb2paletteix[closest_color]}"
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
    pyxel.init(WINDOW_WIDTH, WINDOW_HEIGHT, title="GLOLI")
    img = load_image("surv-sprites.json", "gloli")
    print(img)
