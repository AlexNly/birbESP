"""Server-side "interesting frame" detector.

Each incoming JPEG is downsampled to a tiny grayscale thumbnail and compared
against the previous frame's thumbnail using mean absolute difference. The
threshold for "interesting" is intentionally loose by default — tune via the
``BIRB_HIGHLIGHT_THRESHOLD`` env var once real frames are flowing.
"""

from __future__ import annotations

import io
import os
import threading

import numpy as np
from PIL import Image

# Downsample target. Tiny enough to be fast and robust to sensor noise, large
# enough that a bird-sized blob still moves the needle.
_THUMB_SIZE = (64, 48)


def _threshold() -> float:
    return float(os.environ.get("BIRB_HIGHLIGHT_THRESHOLD", "8.0"))


def _thumb(jpeg_bytes: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(jpeg_bytes)) as im:
        im = im.convert("L").resize(_THUMB_SIZE, Image.BILINEAR)
        return np.asarray(im, dtype=np.int16)


class Highlighter:
    def __init__(self) -> None:
        self._prev: np.ndarray | None = None
        self._lock = threading.Lock()

    def score(self, jpeg_bytes: bytes) -> tuple[float, bool]:
        """Return (diff_score, is_highlight). First frame is never a highlight."""
        thumb = _thumb(jpeg_bytes)
        with self._lock:
            prev = self._prev
            self._prev = thumb
        if prev is None or prev.shape != thumb.shape:
            return 0.0, False
        diff = float(np.abs(thumb - prev).mean())
        return diff, diff >= _threshold()


_singleton: Highlighter | None = None


def get_highlighter() -> Highlighter:
    global _singleton
    if _singleton is None:
        _singleton = Highlighter()
    return _singleton
