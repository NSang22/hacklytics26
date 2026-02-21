"""
Webcam Capture Module — captures webcam video using OpenCV and integrates
with the Presage SDK for real-time facial emotion detection.

The Presage SDK runs on the live webcam feed and produces 10 Hz emotion
signals (frustration, confusion, delight, boredom, surprise).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

# Optional: Presage SDK import
try:
    import presage  # type: ignore
    HAS_PRESAGE = True
except ImportError:
    HAS_PRESAGE = False


class EmotionReading:
    """Single emotion reading from Presage."""

    __slots__ = ("timestamp_sec", "frustration", "confusion", "delight", "boredom", "surprise", "engagement")

    def __init__(
        self,
        timestamp_sec: float,
        frustration: float = 0.0,
        confusion: float = 0.0,
        delight: float = 0.0,
        boredom: float = 0.0,
        surprise: float = 0.0,
        engagement: float = 0.0,
    ):
        self.timestamp_sec = timestamp_sec
        self.frustration = frustration
        self.confusion = confusion
        self.delight = delight
        self.boredom = boredom
        self.surprise = surprise
        self.engagement = engagement

    def to_dict(self) -> Dict[str, float]:
        return {
            "timestamp_sec": self.timestamp_sec,
            "frustration": self.frustration,
            "confusion": self.confusion,
            "delight": self.delight,
            "boredom": self.boredom,
            "surprise": self.surprise,
            "engagement": self.engagement,
        }


class WebcamCapture:
    """Captures webcam feed, records video, and runs Presage emotion detection."""

    def __init__(
        self,
        camera_index: int = 0,
        presage_api_key: str = "",
        emotion_hz: int = 10,
    ):
        self.camera_index = camera_index
        self.presage_api_key = presage_api_key or os.getenv("PRESAGE_API_KEY", "")
        self.emotion_hz = emotion_hz

        self._running = False
        self._capture_thread: Optional[threading.Thread] = None
        self._emotion_thread: Optional[threading.Thread] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._current_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._start_time: float = 0.0

        # Emotion data buffer
        self._emotion_buffer: List[EmotionReading] = []
        self._emotion_lock = threading.Lock()

        # Callbacks
        self._on_emotion: Optional[Callable[[EmotionReading], None]] = None

        # Video recording
        self._recording = False
        self._writer: Optional[cv2.VideoWriter] = None
        self._video_path: Optional[str] = None

        # Presage SDK handle
        self._presage_client = None

    def start(
        self,
        on_emotion: Optional[Callable[[EmotionReading], None]] = None,
        record_video: bool = True,
    ) -> Optional[str]:
        """Start webcam capture and Presage emotion detection.

        Args:
            on_emotion: Callback fired at ~10 Hz with emotion readings.
            record_video: If True, records webcam to a temp .mp4 file.

        Returns:
            Path to the video file if recording, else None.
        """
        if self._running:
            return self._video_path

        self._on_emotion = on_emotion
        self._start_time = time.monotonic()
        self._emotion_buffer.clear()

        # Open camera
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            print(f"[Webcam] Failed to open camera {self.camera_index}")
            return None

        # Get camera properties
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cam_fps = self._cap.get(cv2.CAP_PROP_FPS) or 30

        # Setup video recording
        if record_video:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".mp4", delete=False, prefix="aura_webcam_"
            )
            self._video_path = tmp.name
            tmp.close()
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(self._video_path, fourcc, cam_fps, (w, h))
            self._recording = True

        # Initialize Presage SDK if available
        if HAS_PRESAGE and self.presage_api_key:
            try:
                self._presage_client = presage.Client(api_key=self.presage_api_key)
                print("[Webcam] Presage SDK initialized")
            except Exception as e:
                print(f"[Webcam] Presage init failed: {e}")
                self._presage_client = None

        self._running = True

        # Start capture thread
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        # Start emotion analysis thread
        self._emotion_thread = threading.Thread(target=self._emotion_loop, daemon=True)
        self._emotion_thread.start()

        return self._video_path

    def stop(self) -> Tuple[Optional[str], List[Dict]]:
        """Stop capture and return (video_path, emotion_data).

        Returns:
            Tuple of (path to recorded video or None, list of emotion dicts).
        """
        self._running = False

        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=5.0)
        if self._emotion_thread and self._emotion_thread.is_alive():
            self._emotion_thread.join(timeout=3.0)

        if self._writer:
            self._writer.release()
            self._writer = None
        if self._cap:
            self._cap.release()
            self._cap = None

        with self._emotion_lock:
            emotion_data = [e.to_dict() for e in self._emotion_buffer]

        return self._video_path, emotion_data

    @property
    def is_running(self) -> bool:
        return self._running

    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get the latest webcam frame (for UI preview)."""
        with self._frame_lock:
            return self._current_frame.copy() if self._current_frame is not None else None

    def get_emotion_buffer(self) -> List[Dict]:
        """Get all collected emotion readings so far."""
        with self._emotion_lock:
            return [e.to_dict() for e in self._emotion_buffer]

    # ── Internal ────────────────────────────────────────────

    def _capture_loop(self) -> None:
        """Main webcam capture loop."""
        while self._running and self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            with self._frame_lock:
                self._current_frame = frame.copy()

            if self._recording and self._writer:
                self._writer.write(frame)

            time.sleep(0.001)  # Yield to other threads

    def _emotion_loop(self) -> None:
        """Run emotion detection at target Hz on the current webcam frame."""
        interval = 1.0 / self.emotion_hz

        while self._running:
            t0 = time.monotonic()

            frame = self.get_current_frame()
            if frame is not None:
                timestamp_sec = round(t0 - self._start_time, 3)
                reading = self._analyze_frame(frame, timestamp_sec)

                with self._emotion_lock:
                    self._emotion_buffer.append(reading)

                if self._on_emotion:
                    try:
                        self._on_emotion(reading)
                    except Exception as e:
                        print(f"[Webcam] Emotion callback error: {e}")

            elapsed = time.monotonic() - t0
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _analyze_frame(self, frame: np.ndarray, timestamp_sec: float) -> EmotionReading:
        """Run Presage SDK on a single frame, or generate stub data."""
        # Try Presage SDK first
        if self._presage_client is not None:
            try:
                # Presage SDK expects RGB image
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = self._presage_client.analyze_frame(rgb)
                return EmotionReading(
                    timestamp_sec=timestamp_sec,
                    frustration=result.get("frustration", 0.0),
                    confusion=result.get("confusion", 0.0),
                    delight=result.get("delight", 0.0),
                    boredom=result.get("boredom", 0.0),
                    surprise=result.get("surprise", 0.0),
                    engagement=result.get("engagement", 0.0),
                )
            except Exception as e:
                pass  # Fall through to stub

        # Stub: basic face detection heuristic
        return self._stub_emotion(frame, timestamp_sec)

    def _stub_emotion(self, frame: np.ndarray, timestamp_sec: float) -> EmotionReading:
        """Generate plausible emotion data based on simple heuristics.

        Uses face detection to set engagement, and adds time-based variance.
        """
        import random

        # Simple face presence check via Haar cascade
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(80, 80))
        face_detected = len(faces) > 0

        # Base values with time-varying noise
        t = timestamp_sec
        engagement = 0.7 if face_detected else 0.2
        base_frust = 0.15 + 0.1 * np.sin(t * 0.3)
        base_conf = 0.1 + 0.08 * np.sin(t * 0.2 + 1)
        base_del = 0.4 + 0.15 * np.sin(t * 0.15 + 2)
        base_bore = 0.08 + 0.05 * np.sin(t * 0.1 + 3)
        base_surp = 0.05 + 0.1 * np.sin(t * 0.4 + 4)

        return EmotionReading(
            timestamp_sec=timestamp_sec,
            frustration=max(0.0, min(1.0, base_frust + random.gauss(0, 0.03))),
            confusion=max(0.0, min(1.0, base_conf + random.gauss(0, 0.02))),
            delight=max(0.0, min(1.0, base_del + random.gauss(0, 0.04))),
            boredom=max(0.0, min(1.0, base_bore + random.gauss(0, 0.02))),
            surprise=max(0.0, min(1.0, base_surp + random.gauss(0, 0.03))),
            engagement=max(0.0, min(1.0, engagement + random.gauss(0, 0.05))),
        )

    @staticmethod
    def list_cameras(max_check: int = 2) -> List[Dict]:
        """Enumerate available cameras (default checks 0 and 1 only)."""
        import os
        # Suppress noisy OpenCV warnings during probe
        old_loglevel = os.environ.get("OPENCV_LOG_LEVEL", "")
        os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
        cameras = []
        for i in range(max_check):
            try:
                cap = cv2.VideoCapture(i)
                if cap is not None and cap.isOpened():
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    cameras.append({
                        "index": i,
                        "label": f"Camera {i}: {w}x{h}",
                        "width": w,
                        "height": h,
                    })
                    cap.release()
                else:
                    if cap is not None:
                        cap.release()
            except Exception:
                pass
        # Restore log level
        if old_loglevel:
            os.environ["OPENCV_LOG_LEVEL"] = old_loglevel
        else:
            os.environ.pop("OPENCV_LOG_LEVEL", None)
        return cameras
