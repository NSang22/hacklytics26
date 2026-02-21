"""
Screen Capture Module — captures the screen at configurable FPS using mss,
encodes frames into video chunks using OpenCV, and yields .webm blobs.

Supported FPS: 1, 2, 3, or any custom value up to 30.
Chunks are 10-second segments by default.
"""

from __future__ import annotations

import io
import os
import time
import tempfile
import threading
from typing import Callable, Optional, Tuple

import cv2
import numpy as np
import mss


class ScreenCapture:
    """Captures the screen at a given FPS and yields chunked video blobs."""

    def __init__(
        self,
        fps: int = 3,
        chunk_duration_sec: float = 10.0,
        monitor_index: int = 1,
        resolution: Optional[Tuple[int, int]] = None,
    ):
        self.fps = max(1, min(fps, 30))
        self.chunk_duration_sec = chunk_duration_sec
        self.monitor_index = monitor_index
        self.resolution = resolution  # (width, height) or None for native
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._chunk_index = 0
        self._on_chunk_ready: Optional[Callable[[bytes, int], None]] = None
        self._sct: Optional[mss.mss] = None
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()

    def start(self, on_chunk_ready: Callable[[bytes, int], None]) -> None:
        """Start screen capture in a background thread.

        Args:
            on_chunk_ready: Callback ``(video_bytes, chunk_index)`` called
                each time a chunk is complete.
        """
        if self._running:
            return
        self._on_chunk_ready = on_chunk_ready
        self._running = True
        self._chunk_index = 0
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the capture loop."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Internal ────────────────────────────────────────────

    def _capture_loop(self) -> None:
        """Main capture loop — grabs frames and writes .webm chunks."""
        with mss.mss() as sct:
            monitor = sct.monitors[self.monitor_index]

            # Determine output resolution
            if self.resolution:
                out_w, out_h = self.resolution
            else:
                out_w = monitor["width"]
                out_h = monitor["height"]

            # Ensure even dimensions (required by many codecs)
            out_w = out_w if out_w % 2 == 0 else out_w - 1
            out_h = out_h if out_h % 2 == 0 else out_h - 1

            frame_interval = 1.0 / self.fps
            frames_per_chunk = int(self.chunk_duration_sec * self.fps)

            while self._running:
                # Create temp file for this chunk
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".mp4", delete=False, prefix="aura_chunk_"
                )
                tmp_path = tmp.name
                tmp.close()

                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(tmp_path, fourcc, self.fps, (out_w, out_h))

                frame_count = 0
                chunk_start = time.monotonic()

                while self._running and frame_count < frames_per_chunk:
                    t0 = time.monotonic()

                    # Grab screen
                    raw = sct.grab(monitor)
                    img = np.array(raw)  # BGRA
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                    # Resize if needed
                    h, w = img.shape[:2]
                    if (w, h) != (out_w, out_h):
                        img = cv2.resize(img, (out_w, out_h), interpolation=cv2.INTER_AREA)

                    writer.write(img)
                    frame_count += 1

                    # Store latest frame for UI preview
                    with self._frame_lock:
                        self._latest_frame = img.copy()

                    # Sleep to maintain target FPS
                    elapsed = time.monotonic() - t0
                    sleep_time = frame_interval - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                writer.release()

                # Read the chunk bytes and dispatch
                if frame_count > 0 and self._on_chunk_ready:
                    try:
                        with open(tmp_path, "rb") as f:
                            chunk_bytes = f.read()
                        self._on_chunk_ready(chunk_bytes, self._chunk_index)
                    except Exception as e:
                        print(f"[ScreenCapture] Error reading chunk: {e}")

                # Cleanup temp file
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

                with self._lock:
                    self._chunk_index += 1

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Get the most recent captured frame (BGR) for UI preview."""
        with self._frame_lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def get_monitors(self) -> list:
        """Return list of available monitors for selection UI."""
        with mss.mss() as sct:
            return [
                {
                    "index": i,
                    "width": m["width"],
                    "height": m["height"],
                    "left": m["left"],
                    "top": m["top"],
                    "label": f"Monitor {i}: {m['width']}x{m['height']}"
                    if i > 0
                    else "All Monitors Combined",
                }
                for i, m in enumerate(sct.monitors)
            ]
