"""
Face Calibration Window — 3-step expression calibration for per-person emotion scaling.

Opens an overlay window with three prompts:
  1. "Look at camera with a neutral face" (~3 seconds)
  2. "Now smile" (~3 seconds)
  3. "Now open your eyes wide" (~3 seconds)

The captured blendshape data is used to compute per-person expression ranges,
so that emotion scores are normalized to each individual's natural range.

Usage:
    win = FaceCalibrationWindow(
        master=root,
        face_analyzer=face_analyzer,
        camera_index=0,
        on_complete=lambda success: print(f"Calibrated: {success}"),
    )
"""

from __future__ import annotations

import time
import threading
from typing import Callable, Dict, List, Optional

import cv2
import numpy as np

try:
    import tkinter as tk
except ImportError:
    import Tkinter as tk  # type: ignore

from face_analyzer import FaceAnalyzer

# ── Colours ─────────────────────────────────────────────
_BG = "#0a0a14"
_TEXT = "#e2e8f0"
_MUTED = "#64748b"
_ACCENT = "#3b82f6"
_SUCCESS = "#22c55e"
_COUNTDOWN = "#f59e0b"


# ── Calibration phases ──────────────────────────────────
_PHASES = [
    {
        "key": "neutral",
        "title": "Neutral Face",
        "instruction": "Look at the camera with a relaxed, neutral face.",
        "emoji": "😐",
    },
    {
        "key": "smile",
        "title": "Smile",
        "instruction": "Now smile naturally.",
        "emoji": "😊",
    },
    {
        "key": "eyes_wide",
        "title": "Eyes Wide",
        "instruction": "Now open your eyes wide.",
        "emoji": "👀",
    },
]


class FaceCalibrationWindow:
    """Fullscreen 3-step face expression calibration."""

    SETTLE_SEC = 1.0   # seconds to let person adjust before capturing
    CAPTURE_SEC = 2.0  # seconds of actual data capture

    def __init__(
        self,
        master: tk.Tk,
        face_analyzer: FaceAnalyzer,
        camera_index: int = 0,
        on_complete: Optional[Callable[[bool], None]] = None,
    ):
        self._analyzer = face_analyzer
        self._camera_index = camera_index
        self._on_complete = on_complete

        # State
        self._running = False
        self._current_phase = -1  # -1 = instructions screen
        self._phase_blendshapes: Dict[str, List[Dict[str, float]]] = {
            "neutral": [],
            "smile": [],
            "eyes_wide": [],
        }
        self._frame_bs_buffer: List[Dict[str, float]] = []

        # Camera
        self._cap: Optional[cv2.VideoCapture] = None
        self._cam_thread: Optional[threading.Thread] = None

        # ── Build window ────────────────────────────────
        self.top = tk.Toplevel(master)
        self.top.title("Face Calibration")
        self.top.configure(bg=_BG)
        self.top.attributes("-topmost", True)

        # Centered window (not fullscreen — less intimidating)
        win_w, win_h = 600, 400
        self.top.update_idletasks()
        screen_w = self.top.winfo_screenwidth()
        screen_h = self.top.winfo_screenheight()
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        self.top.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.top.resizable(False, False)

        self.canvas = tk.Canvas(
            self.top,
            width=win_w,
            height=win_h,
            bg=_BG,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self._win_w = win_w
        self._win_h = win_h

        # Show instructions
        self._show_instructions()

        # Bind keys
        self.top.bind("<space>", self._on_space)
        self.top.bind("<Escape>", self._on_escape)
        self.top.protocol("WM_DELETE_WINDOW", self._close)

    # ── UI Screens ──────────────────────────────────────

    def _show_instructions(self) -> None:
        self.canvas.delete("all")
        cx, cy = self._win_w / 2, self._win_h / 2
        self.canvas.create_text(
            cx, cy - 80,
            text="😊  Face Calibration",
            fill=_TEXT,
            font=("Helvetica", 28, "bold"),
        )
        self.canvas.create_text(
            cx, cy - 20,
            text="We'll capture your neutral face, smile,",
            fill=_MUTED,
            font=("Helvetica", 16),
        )
        self.canvas.create_text(
            cx, cy + 10,
            text="and wide eyes to personalize emotion detection.",
            fill=_MUTED,
            font=("Helvetica", 16),
        )
        self.canvas.create_text(
            cx, cy + 60,
            text="Make sure your face is visible in the webcam.",
            fill=_MUTED,
            font=("Helvetica", 14),
        )
        self.canvas.create_text(
            cx, cy + 110,
            text="Press SPACE to begin  •  ESC to cancel",
            fill=_ACCENT,
            font=("Helvetica", 14, "bold"),
        )

    def _show_phase(self, phase_idx: int, countdown: Optional[int] = None) -> None:
        self.canvas.delete("all")
        phase = _PHASES[phase_idx]
        cx, cy = self._win_w / 2, self._win_h / 2

        # Step indicator
        self.canvas.create_text(
            cx, cy - 100,
            text=f"Step {phase_idx + 1} of {len(_PHASES)}",
            fill=_MUTED,
            font=("Helvetica", 14),
        )

        # Emoji
        self.canvas.create_text(
            cx, cy - 50,
            text=phase["emoji"],
            fill=_TEXT,
            font=("Helvetica", 48),
        )

        # Title
        self.canvas.create_text(
            cx, cy + 20,
            text=phase["title"],
            fill=_TEXT,
            font=("Helvetica", 24, "bold"),
        )

        # Instruction
        self.canvas.create_text(
            cx, cy + 60,
            text=phase["instruction"],
            fill=_MUTED,
            font=("Helvetica", 16),
        )

        # Countdown or "capturing" indicator
        if countdown is not None:
            self.canvas.create_text(
                cx, cy + 110,
                text=f"Get ready… {countdown}",
                fill=_COUNTDOWN,
                font=("Helvetica", 18, "bold"),
            )
        else:
            # Pulsing capture indicator
            self.canvas.create_oval(
                cx - 8, cy + 102, cx + 8, cy + 118,
                fill=_SUCCESS, outline="",
            )
            self.canvas.create_text(
                cx + 20, cy + 110,
                text="Capturing…",
                fill=_SUCCESS,
                font=("Helvetica", 16, "bold"),
                anchor="w",
            )

    def _show_complete(self, scales: Dict[str, float]) -> None:
        self.canvas.delete("all")
        cx, cy = self._win_w / 2, self._win_h / 2

        self.canvas.create_text(
            cx, cy - 60,
            text="✅  Calibration Complete!",
            fill=_TEXT,
            font=("Helvetica", 26, "bold"),
        )

        # Show what was learned
        lines = []
        if "delight" in scales:
            lines.append(f"Smile sensitivity: {scales['delight']:.1f}x")
        if "surprise" in scales:
            lines.append(f"Eye-wide sensitivity: {scales['surprise']:.1f}x")
        if not scales:
            lines.append("Using default sensitivity")

        for i, line in enumerate(lines):
            self.canvas.create_text(
                cx, cy + i * 28,
                text=line,
                fill=_MUTED,
                font=("Helvetica", 16),
            )

        self.canvas.create_text(
            cx, cy + 80 + len(lines) * 10,
            text="Closing automatically…",
            fill=_MUTED,
            font=("Helvetica", 12),
        )

    def _show_failed(self, reason: str) -> None:
        self.canvas.delete("all")
        cx, cy = self._win_w / 2, self._win_h / 2
        self.canvas.create_text(
            cx, cy - 20,
            text="❌  Calibration Failed",
            fill="#ef4444",
            font=("Helvetica", 24, "bold"),
        )
        self.canvas.create_text(
            cx, cy + 20,
            text=reason,
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

    # ── Calibration Flow ────────────────────────────────

    def _start_calibration(self) -> None:
        self._running = True
        self._current_phase = 0

        # Reset buffers
        for key in self._phase_blendshapes:
            self._phase_blendshapes[key].clear()

        # Open camera
        self._cap = cv2.VideoCapture(self._camera_index)
        if not self._cap.isOpened():
            print("[FaceCalib] Failed to open camera")
            self._show_failed("Could not open camera")
            self.top.after(3000, self._close)
            return

        # Start camera reader thread
        self._cam_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self._cam_thread.start()

        # Begin first phase
        self._advance_phase()

    def _advance_phase(self) -> None:
        if not self._running:
            return

        idx = self._current_phase
        if idx >= len(_PHASES):
            self._finish_calibration()
            return

        # Show phase with countdown
        settle_ms = int(self.SETTLE_SEC * 1000)
        capture_ms = int(self.CAPTURE_SEC * 1000)

        # Countdown: show "Get ready… 1"
        self._show_phase(idx, countdown=1)
        self._frame_bs_buffer.clear()

        # After settle, start capturing
        self.top.after(settle_ms, lambda: self._begin_capture(idx))
        # After settle + capture, end and move on
        self.top.after(settle_ms + capture_ms, lambda: self._end_capture(idx))

    def _begin_capture(self, phase_idx: int) -> None:
        """Start collecting blendshape data for this phase."""
        if not self._running:
            return
        self._frame_bs_buffer.clear()
        self._show_phase(phase_idx, countdown=None)  # show "Capturing…"

    def _end_capture(self, phase_idx: int) -> None:
        """Finish capturing and store averaged blendshapes."""
        if not self._running:
            return

        phase_key = _PHASES[phase_idx]["key"]
        self._phase_blendshapes[phase_key] = list(self._frame_bs_buffer)

        n = len(self._phase_blendshapes[phase_key])
        print(f"[FaceCalib] {phase_key}: captured {n} frames")

        if n < 5:
            print(f"[FaceCalib] WARNING: very few frames for {phase_key}")

        self._current_phase += 1
        self._advance_phase()

    def _finish_calibration(self) -> None:
        """Compute averages and set calibration on FaceAnalyzer."""
        self._running = False

        # Stop camera
        if self._cam_thread and self._cam_thread.is_alive():
            self._cam_thread.join(timeout=3.0)
        if self._cap:
            self._cap.release()
            self._cap = None

        # Average blendshapes per phase
        averages: Dict[str, Dict[str, float]] = {}
        for phase_key, frames in self._phase_blendshapes.items():
            if not frames:
                self._show_failed(f"No face detected during '{phase_key}' phase")
                if self._on_complete:
                    self._on_complete(False)
                self.top.after(3000, self._close)
                return

            avg: Dict[str, float] = {}
            all_keys = frames[0].keys()
            for k in all_keys:
                vals = [f.get(k, 0.0) for f in frames]
                avg[k] = sum(vals) / len(vals)
            averages[phase_key] = avg

        # Apply to FaceAnalyzer
        scales = self._analyzer.set_explicit_calibration(
            neutral_bs=averages["neutral"],
            smile_bs=averages["smile"],
            wide_bs=averages["eyes_wide"],
        )

        self._show_complete(scales)
        if self._on_complete:
            self._on_complete(True)

        self.top.after(3000, self._close)

    # ── Camera reading ──────────────────────────────────

    def _camera_loop(self) -> None:
        """Read frames and extract raw (un-baseline-subtracted) blendshapes."""
        while self._running and self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            # We need RAW blendshapes (before baseline subtraction)
            # So we run MediaPipe directly instead of going through analyze()
            try:
                import mediapipe as mp
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

                if self._analyzer._landmarker is None:
                    time.sleep(0.03)
                    continue

                detection = self._analyzer._landmarker.detect(mp_img)

                if detection.face_landmarks and detection.face_blendshapes:
                    bs: Dict[str, float] = {}
                    for b in detection.face_blendshapes[0]:
                        bs[b.category_name] = round(b.score, 4)
                    self._frame_bs_buffer.append(bs)
            except Exception as e:
                print(f"[FaceCalib] Frame error: {e}")

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
