import argparse
import os
from collections.abc import Iterator
from functools import cache
from glob import glob
from pathlib import Path

import cramjam
import numpy as np
import PIL.Image as Image
import pyxel
import torch
import torchvision.transforms as T
import webp
from safetensors.numpy import load


def iterator_of_raw_frames(parent: str) -> Iterator[np.ndarray]:
    dirs = sorted(glob(f"{parent}/*-*"))
    for chunk in dirs:
        if not os.path.exists(f"{chunk}/frames.safetensors.zstd"):
            continue
        with open(f"{chunk}/frames.safetensors.zstd", "rb") as f:
            buffer = load(bytes(cramjam.zstd.decompress(f.read())))
            frames = buffer["frames"]
            yield frames


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


def frame_to_rgb_tensor(frame: np.ndarray) -> np.ndarray:
    rgb2paletteix = calculate_rgb2paletteix()
    paletteix2rgb = {v: k for k, v in rgb2paletteix.items()}
    rgb2paletteix_arr = np.array([paletteix2rgb[i] for i in range(16)], dtype=np.uint8)
    return rgb2paletteix_arr[frame]


def resize2x(img: torch.Tensor) -> torch.Tensor:
    return T.Resize((240 * 4, 427 * 4))(img)


def detect_need_conversion_inputs() -> Iterator[str]:
    for d in glob("recordings/*-*"):
        p = Path(d) / "export.webp"
        if not p.exists():
            yield os.path.abspath(d)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=False)
    parser.add_argument("--output", type=str, required=False)
    args = parser.parse_args()
    candidates = list(detect_need_conversion_inputs())
    pyxel.init(128, 128)
    for c in candidates:
        print(c)
        pil_images = []
        for i, frame in enumerate(iterator_of_raw_frames(c)):
            rgb_tensor = frame_to_rgb_tensor(frame)
            conv = rgb_tensor
            for i in conv:
                pil_images.append(Image.fromarray(i))
        output_p = Path(c) / "export.webp"
        webp.save_images(pil_images, str(output_p), lossless=True, fps=30)
