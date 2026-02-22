"""
Gaze Calibration Window — 9-point calibration for iris-based gaze tracking.

Opens a fullscreen overlay showing dots at 9 screen positions.  The user
fixates on each dot while the face analyser collects iris ratios.  After
all 9 points a polynomial model is fitted that maps iris position → screen
pixel coordinates.

Usage:
    win = GazeCalibrationWindow(
        master=root,
        face_analyzer=face_analyzer,
        camera_index=0,
        on_complete=lambda err: print(f"Error: {err:.1f}px"),
    )
"""

from __future__ import annotations

import time
import threading
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

try:
    import tkinter as tk
except ImportError:
    import Tkinter as tk  # type: ignore

from face_analyzer import FaceAnalyzer


# ── Colours ─────────────────────────────────────────────
_BG = "#0a0a14"
_DOT = "#3b82f6"
_DOT_ACTIVE = "#22c55e"
_TEXT = "#e2e8f0"
_MUTED = "#64748b"


class GazeCalibrationWindow:
    """Fullscreen 9-point gaze calibration."""

    # Seconds per dot: 1s settle + 2s capture
    SETTLE_SEC = 1.0
    CAPTURE_SEC = 2.0
    DOT_TOTAL_SEC = SETTLE_SEC + CAPTURE_SEC - 0.2  # slight overlap ok
    MARGIN = 0.10  # 10% margin from screen edges

    def __init__(
        self,
        master: tk.Tk,
        face_analyzer: FaceAnalyzer,
        camera_index: int = 0,
        on_complete: Optional[Callable[[float], None]] = None,
    ):
        self._analyzer = face_analyzer
        self._camera_index = camera_index
        self._on_complete = on_complete

        # State
        self._running = False
        self._current_dot = -1  # -1 = instructions
        self._capture_data: List[Tuple[float, float]] = []  # averaged iris per dot
        self._screen_points: List[Tuple[float, float]] = []
        self._frame_iris_buffer: List[Tuple[float, float]] = []

        # Camera (opened during calibration)
        self._cap: Optional[cv2.VideoCapture] = None
        self._cam_thread: Optional[threading.Thread] = None

        # ── Build fullscreen window ─────────────────────
        self.top = tk.Toplevel(master)
        self.top.title("Gaze Calibration")
        self.top.configure(bg=_BG)
        self.top.attributes("-topmost", True)

        # Use fullscreen
        self.top.attributes("-fullscreen", True)
        self.top.update_idletasks()

        self.screen_w = self.top.winfo_screenwidth()
        self.screen_h = self.top.winfo_screenheight()

        self.canvas = tk.Canvas(
            self.top,
            width=self.screen_w,
            height=self.screen_h,
            bg=_BG,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Compute 9-dot grid positions
        self._positions = self._make_grid()

        # Draw instructions
        self._show_instructions()

        # Bind keys
        self.top.bind("<space>", self._on_space)
        self.top.bind("<Escape>", self._on_escape)
        self.top.protocol("WM_DELETE_WINDOW", self._close)

    # ── Grid ────────────────────────────────────────────

    def _make_grid(self) -> List[Tuple[float, float]]:
        mx = self.screen_w * self.MARGIN
        my = self.screen_h * self.MARGIN
        pts = []
        for row in range(3):
            for col in range(3):
                x = mx + col * (self.screen_w - 2 * mx) / 2
                y = my + row * (self.screen_h - 2 * my) / 2
                pts.append((x, y))
        return pts

    # ── UI States ───────────────────────────────────────

    def _show_instructions(self) -> None:
        self.canvas.delete("all")
        cx, cy = self.screen_w / 2, self.screen_h / 2
        self.canvas.create_text(
            cx,
            cy - 60,
            text="👁️  Gaze Calibration",
            fill=_TEXT,
            font=("Helvetica", 36, "bold"),
        )
        self.canvas.create_text(
            cx,
            cy + 10,
            text="Look at each green dot and hold your gaze for ~2 seconds.",
            fill=_MUTED,
            font=("Helvetica", 18),
        )
        self.canvas.create_text(
            cx,
            cy + 50,
            text="Keep your head still.  Press SPACE to begin.",
            fill=_MUTED,
            font=("Helvetica", 18),
        )
        self.canvas.create_text(
            cx,
            cy + 110,
            text="Press ESC to cancel.",
            fill=_MUTED,
            font=("Helvetica", 14),
        )

    def _show_dot(self, idx: int) -> None:
        self.canvas.delete("all")
        x, y = self._positions[idx]
        r = 18
        self.canvas.create_oval(
            x - r, y - r, x + r, y + r, fill=_DOT_ACTIVE, outline=""
        )
        # Small crosshair
        self.canvas.create_line(x - r * 2, y, x + r * 2, y, fill=_MUTED, width=1)
        self.canvas.create_line(x, y - r * 2, x, y + r * 2, fill=_MUTED, width=1)
        # Counter
        self.canvas.create_text(
            self.screen_w / 2,
            self.screen_h - 40,
            text=f"Point {idx + 1} / {len(self._positions)}",
            fill=_MUTED,
            font=("Helvetica", 14),
        )

    def _show_fitting(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(
            self.screen_w / 2,
            self.screen_h / 2,
            text="Fitting model…",
            fill=_TEXT,
            font=("Helvetica", 24),
        )

    def _show_result(self, error_px: float) -> None:
        self.canvas.delete("all")
        cx, cy = self.screen_w / 2, self.screen_h / 2
        color = _DOT_ACTIVE if error_px < 50 else "#f59e0b" if error_px < 100 else "#ef4444"
        self.canvas.create_text(
            cx,
            cy - 30,
            text=f"✅  Calibration complete!",
            fill=_TEXT,
            font=("Helvetica", 28, "bold"),
        )
        self.canvas.create_text(
            cx,
            cy + 20,
            text=f"Mean error: {error_px:.1f} px",
            fill=color,
            font=("Helvetica", 20),
        )
        self.canvas.create_text(
            cx,
            cy + 70,
            text="Closing in 3 seconds…",
            fill=_MUTED,
            font=("Helvetica", 14),
        )

    # ── Event Handlers ──────────────────────────────────

    def _on_space(self, event=None) -> None:
        if self._running:
            return
        self._start_calibration()

    def _on_escape(self, event=None) -> None:
        self._close()

    # ── Calibration Loop ────────────────────────────────

    def _start_calibration(self) -> None:
        self._running = True
        self._current_dot = 0
        self._capture_data.clear()
        self._screen_points.clear()

        # Open camera
        self._cap = cv2.VideoCapture(self._camera_index)
        if not self._cap.isOpened():
            print("[GazeCalib] Failed to open camera")
            self._close()
            return

        # Start camera reader thread
        self._cam_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self._cam_thread.start()

        # Kick off first dot
        self._advance_dot()

    def _advance_dot(self) -> None:
        if not self._running:
            return

        idx = self._current_dot
        if idx >= len(self._positions):
            # All dots done — fit model
            self._finish_calibration()
            return

        self._show_dot(idx)
        self._frame_iris_buffer.clear()

        # After settle period, start capture
        settle_ms = int(self.SETTLE_SEC * 1000)
        capture_ms = int(self.CAPTURE_SEC * 1000)

        self.top.after(settle_ms, self._begin_capture)
        self.top.after(settle_ms + capture_ms, self._end_capture)

    def _begin_capture(self) -> None:
        """Mark that we're now collecting iris data for the current dot."""
        self._frame_iris_buffer.clear()

    def _end_capture(self) -> None:
        """Finish capturing for current dot, average the iris data."""
        if not self._running:
            return

        if self._frame_iris_buffer:
            avg_rx = sum(p[0] for p in self._frame_iris_buffer) / len(self._frame_iris_buffer)
            avg_ry = sum(p[1] for p in self._frame_iris_buffer) / len(self._frame_iris_buffer)
            self._capture_data.append((avg_rx, avg_ry))
            self._screen_points.append(self._positions[self._current_dot])
            print(
                f"[GazeCalib] Dot {self._current_dot + 1}: "
                f"iris=({avg_rx:.4f}, {avg_ry:.4f}) "
                f"screen={self._positions[self._current_dot]} "
                f"({len(self._frame_iris_buffer)} samples)"
            )
        else:
            print(f"[GazeCalib] Dot {self._current_dot + 1}: no iris data captured!")

        self._current_dot += 1
        self._advance_dot()

    def _finish_calibration(self) -> None:
        """Fit the gaze model and close."""
        self._show_fitting()
        self.top.update_idletasks()

        # Stop camera
        self._running = False
        if self._cam_thread and self._cam_thread.is_alive():
            self._cam_thread.join(timeout=3.0)
        if self._cap:
            self._cap.release()
            self._cap = None

        # Fit
        if len(self._capture_data) >= 4:
            error = self._analyzer.gaze_calibrator.fit(
                self._capture_data,
                self._screen_points,
                self.screen_w,
                self.screen_h,
            )
            print(f"[GazeCalib] Calibration fitted — mean error: {error:.1f} px")
            self._show_result(error)
            if self._on_complete:
                self._on_complete(error)
        else:
            print("[GazeCalib] Not enough data for calibration")
            self._show_result(-1)

        self.top.after(3000, self._close)

    # ── Camera reading ──────────────────────────────────

    def _camera_loop(self) -> None:
        """Read frames and run face analysis to get iris ratios."""
        while self._running and self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            # Run face analysis
            ts = time.monotonic()
            result = self._analyzer.analyze(frame, ts)

            if result.face_detected:
                self._frame_iris_buffer.append(
                    (result.iris_ratio_x, result.iris_ratio_y)
                )

            time.sleep(0.03)  # ~30 FPS cap

    # ── Cleanup ─────────────────────────────────────────

    def _close(self) -> None:
        self._running = False
        if self._cam_thread and self._cam_thread.is_alive():
            self._cam_thread.join(timeout=2.0)
        if self._cap:
            self._cap.release()
            self._cap = None
        try:
            self.top.destroy()
        except Exception:
            pass
