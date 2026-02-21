"""
Webcam Capture Module — captures webcam video using OpenCV and integrates
with FaceAnalyzer (MediaPipe Face Mesh) for real-time facial expression,
Action Unit, and gaze tracking.

Replaces the former Presage SDK stub with on-device MediaPipe analysis.
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

# FaceAnalyzer (local MediaPipe-based)
try:
    from face_analyzer import FaceAnalyzer, FaceAnalysis
    HAS_FACE_ANALYZER = True
except ImportError:
    HAS_FACE_ANALYZER = False
    print("[Webcam] WARNING: face_analyzer not available")


class EmotionReading:
    """Single reading from face analysis: emotions + AUs + gaze + head pose."""

    __slots__ = (
        "timestamp_sec", "frustration", "confusion", "delight",
        "boredom", "surprise", "engagement",
        "gaze_x", "gaze_y", "gaze_confidence",
        "head_pitch", "head_yaw", "head_roll",
        "action_units", "face_detected",
    )

    def __init__(
        self,
        timestamp_sec: float,
        frustration: float = 0.0,
        confusion: float = 0.0,
        delight: float = 0.0,
        boredom: float = 0.0,
        surprise: float = 0.0,
        engagement: float = 0.0,
        gaze_x: float = 0.5,
        gaze_y: float = 0.5,
        gaze_confidence: float = 0.0,
        head_pitch: float = 0.0,
        head_yaw: float = 0.0,
        head_roll: float = 0.0,
        action_units: Optional[Dict] = None,
        face_detected: bool = False,
    ):
        self.timestamp_sec = timestamp_sec
        self.frustration = frustration
        self.confusion = confusion
        self.delight = delight
        self.boredom = boredom
        self.surprise = surprise
        self.engagement = engagement
        self.gaze_x = gaze_x
        self.gaze_y = gaze_y
        self.gaze_confidence = gaze_confidence
        self.head_pitch = head_pitch
        self.head_yaw = head_yaw
        self.head_roll = head_roll
        self.action_units = action_units or {}
        self.face_detected = face_detected

    def to_dict(self) -> Dict:
        return {
            "timestamp_sec": self.timestamp_sec,
            "frustration": self.frustration,
            "confusion": self.confusion,
            "delight": self.delight,
            "boredom": self.boredom,
            "surprise": self.surprise,
            "engagement": self.engagement,
            "gaze_x": self.gaze_x,
            "gaze_y": self.gaze_y,
            "gaze_confidence": self.gaze_confidence,
            "head_pitch": self.head_pitch,
            "head_yaw": self.head_yaw,
            "head_roll": self.head_roll,
            "action_units": dict(self.action_units) if self.action_units else {},
            "face_detected": self.face_detected,
        }


class WebcamCapture:
    """Captures webcam feed, records video, and runs Presage emotion detection."""

    def __init__(
        self,
        camera_index: int = 0,
        presage_api_key: str = "",
        emotion_hz: int = 10,
        face_analyzer: Optional[Any] = None,
    ):
        self.camera_index = camera_index
        self.presage_api_key = presage_api_key or os.getenv("PRESAGE_API_KEY", "")
        self.emotion_hz = emotion_hz
        self.face_analyzer = face_analyzer  # FaceAnalyzer instance (shared)

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

        # Face Analyzer (replaces Presage)
        self._owns_analyzer = False  # True if we created the analyzer

    def start(
        self,
        on_emotion: Optional[Callable[[EmotionReading], None]] = None,
        record_video: bool = False,
    ) -> Optional[str]:
        """Start webcam capture and face analysis.

        Args:
            on_emotion: Callback fired at ~10 Hz with emotion readings.
            record_video: If True, records webcam to a temp .mp4 file.

        Returns:
            Path to the video file if recording, else None.
        """
        if self._running:
            return self._video_path

        if on_emotion is not None:
            self._on_emotion = on_emotion
        self._start_time = time.monotonic()
        self._emotion_buffer.clear()

        # Open camera
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            print(f"[Webcam] Failed to open camera {self.camera_index}")
            return None

        # Get camera properties
        self._cam_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._cam_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._cam_fps = self._cap.get(cv2.CAP_PROP_FPS) or 30

        # Setup video recording
        if record_video:
            self._begin_video_writer()

        # Initialize Face Analyzer if not provided externally
        if self.face_analyzer is None and HAS_FACE_ANALYZER:
            self.face_analyzer = FaceAnalyzer()
            self._owns_analyzer = True
            print("[Webcam] FaceAnalyzer created internally")
        elif self.face_analyzer is not None:
            print("[Webcam] Using shared FaceAnalyzer")

        self._running = True

        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        self._emotion_thread = threading.Thread(target=self._emotion_loop, daemon=True)
        self._emotion_thread.start()

        return self._video_path

    def start_recording(self) -> Optional[str]:
        """Begin recording video on an already-running camera.

        Returns:
            Path to the video file, or None if camera not running.
        """
        if not self._running or not self._cap:
            return None
        if self._recording:
            return self._video_path
        self._begin_video_writer()
        return self._video_path

    def stop_recording(self) -> Optional[str]:
        """Stop recording video but keep the camera and face analysis running.

        Returns:
            Path to the recorded video file.
        """
        self._recording = False
        if self._writer:
            self._writer.release()
            self._writer = None
        return self._video_path

    def _begin_video_writer(self) -> None:
        """Create a new video writer for recording."""
        tmp = tempfile.NamedTemporaryFile(
            suffix=".mp4", delete=False, prefix="aura_webcam_"
        )
        self._video_path = tmp.name
        tmp.close()
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        w = getattr(self, "_cam_w", 640)
        h = getattr(self, "_cam_h", 480)
        fps = getattr(self, "_cam_fps", 30)
        self._writer = cv2.VideoWriter(self._video_path, fourcc, fps, (w, h))
        self._recording = True

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
        """Run FaceAnalyzer (MediaPipe) on a single frame."""
        if self.face_analyzer is not None:
            try:
                fa = self.face_analyzer.analyze(frame, timestamp_sec)
                emo = fa.emotions
                return EmotionReading(
                    timestamp_sec=timestamp_sec,
                    frustration=emo.get("frustration", 0.0),
                    confusion=emo.get("confusion", 0.0),
                    delight=emo.get("delight", 0.0),
                    boredom=emo.get("boredom", 0.0),
                    surprise=emo.get("surprise", 0.0),
                    engagement=emo.get("engagement", 0.0),
                    gaze_x=fa.gaze_x,
                    gaze_y=fa.gaze_y,
                    gaze_confidence=fa.gaze_confidence,
                    head_pitch=fa.head_pitch,
                    head_yaw=fa.head_yaw,
                    head_roll=fa.head_roll,
                    action_units=fa.action_units,
                    face_detected=fa.face_detected,
                )
            except Exception as e:
                print(f"[Webcam] FaceAnalyzer error: {e}")

        # Fallback: no-face empty reading
        return EmotionReading(timestamp_sec=timestamp_sec)

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
