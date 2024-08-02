import json
from collections.abc import Iterator, Mapping
from functools import cache

import numpy as np
import PIL.Image as Image
import pyxel
from pyxelxl.font import _image_as_ndarray

from genio.gears.sentence_embed import SentenceEmbeddingGenerator


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


def apply_palette_conversion(image: Image.Image) -> np.ndarray:
    rgb2paletteix = calculate_rgb2paletteix()
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


def buffer_to_image(buffer: np.ndarray) -> pyxel.Image:
    pimage = pyxel.Image(buffer.shape[1], buffer.shape[0])
    _image_as_ndarray(pimage)[:] = buffer
    return pimage


def pil_image_to_pyxel_image(image: Image.Image) -> pyxel.Image:
    buffer = apply_palette_conversion(image)
    return buffer_to_image(buffer)


def iterate_cells_of_spritesheet(path: str) -> Iterator[tuple[str, Image.Image]]:
    with open(path) as f:
        data = json.load(f)
    parent_image = Image.open(path.replace(".json", ".png")).convert("RGBA")
    for frame_name, frame_metadata in data["frames"].items():
        frame_name = frame_name.split(".")[0]
        frame_name = frame_name.replace("(", "").replace(")", "")
        frame_name = frame_name.lower()
        x, y, w, h = (
            frame_metadata["frame"]["x"],
            frame_metadata["frame"]["y"],
            frame_metadata["frame"]["w"],
            frame_metadata["frame"]["h"],
        )
        yield (
            frame_name,
            pil_image_to_pyxel_image(parent_image.crop((x, y, x + w, y + h))),
        )


class Spritesheet(Mapping[str, pyxel.Image]):
    embeddings: np.ndarray

    def __init__(self, path: str | list[str], build_search_index: bool = False) -> None:
        super().__init__()
        paths = path if isinstance(path, list) else [path]
        self.images = {}
        for path in paths:
            for frame_name, frame_image in iterate_cells_of_spritesheet(path):
                self.images[frame_name] = frame_image
        self._keys = []
        if build_search_index:
            self.build_search_index()

    def build_search_index(self) -> None:
        self._keys = list(self.images.keys())
        gen = SentenceEmbeddingGenerator.default()
        embeddings = [gen.sentence_embedding(k) for k in self._keys]
        shapes = [e.shape for e in embeddings]
        self.embeddings = np.stack(embeddings)

    def search(self, query: str) -> str:
        gen = SentenceEmbeddingGenerator.default()
        query_embedding = gen.sentence_embedding(query)
        scores = np.linalg.norm(self.embeddings - query_embedding, axis=1)
        print(list(zip(self._keys, scores)))
        best_ix = np.argmin(scores)
        return self._keys[best_ix]

    def search_image(self, query: str) -> pyxel.Image:
        print(self.search(query))
        return self[self.search(query)]

    def __getitem__(self, key):
        return self.images[key]

    def __len__(self):
        return len(self.images)

    def __iter__(self):
        return iter(self.images)
