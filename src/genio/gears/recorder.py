import json
from collections import deque
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cramjam
import numpy as np
import pyxel
from pyxelxl.font import _image_as_ndarray
from safetensors.numpy import save

from genio.base import asset_path


class HasEvents(Protocol):
    events: list[int]


@dataclass
class FrameData:
    buffer: deque[np.ndarray]
    events: list[int]


class FrameWriter:
    buffer: deque[FrameData]

    def __init__(self, parent: HasEvents) -> None:
        self.buffer = deque()
        self.parent = parent

    def record_frame(self) -> None:
        arr = _image_as_ndarray(pyxel.screen).copy()
        self.buffer.append(FrameData(buffer=arr, events=list(set(self.parent.events))))

    def flush(self, tmp_buffer: Sequence[np.ndarray], path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        frames = np.stack([frame.buffer for frame in tmp_buffer])
        buffer = cramjam.zstd.compress(
            save(
                {
                    "frames": frames,
                }
            )
        )
        events_list = json.dumps([frame.events for frame in tmp_buffer])
        # write two files
        with open(path / "frames.safetensors.zstd", "wb") as f:
            f.write(buffer)
        with open(path / "events.json", "w") as f:
            f.write(events_list)

    def __len__(self) -> int:
        return len(self.buffer)


class Recorder:
    def __init__(self, parent: HasEvents) -> None:
        self.writer = FrameWriter(parent)
        self.parent = parent
        self.recording_name = None
        self.num_chunks = 0
        self.executor = ThreadPoolExecutor(1)

    def start_recording(self) -> None:
        import datetime

        self.recording_name = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self.num_chunks = 0

    def stop_recording(self) -> None:
        self.save_chunk()
        self.recording_name = None
        self.num_chunks = 0

    def update(self) -> None:
        if self.recording_name:
            self.writer.record_frame()
            if len(self.writer) >= 60:
                self.save_chunk()

    def draw(self) -> None:
        if self.is_recording():
            pyxel.text(0, 0, "RECORDING", 7)

    def toggle_recording(self) -> None:
        if self.is_recording():
            self.stop_recording()
        else:
            self.start_recording()

    def save_chunk(self):
        import time

        t0 = time.time()
        num_chunks_leftpad = str(self.num_chunks).zfill(4)
        root = Path(asset_path(".")).parent
        # self.writer.flush()
        fname = (
            root
            / "recordings"
            / f"{self.recording_name}"
            / f"{self.recording_name}-{num_chunks_leftpad}"
        )
        dumped_buffer = list(self.writer.buffer)
        self.writer.buffer.clear()
        self.executor.submit(self.writer.flush, dumped_buffer, fname)
        self.num_chunks += 1
        # print(f"Saved chunk {num_chunks_leftpad} in {time.time() - t0:.2f}s")

    def is_recording(self) -> bool:
        return bool(self.recording_name)
