"""
Face Analysis Module — MediaPipe FaceLandmarker (Tasks API) for blendshape-based
expression classification, iris gaze tracking, and head pose estimation.

Uses the FaceLandmarker model with ``output_face_blendshapes=True`` which
provides 52 ARKit-standard blendshapes (brow, eye, jaw, mouth, cheek, nose)
at near–real-time speed on Apple Silicon.  These replace hand-crafted AU
distance ratios with ML-predicted activation scores.

Additionally computes:
  • Iris-based gaze (landmarks 468-477) with optional 9-point calibration
  • Head pose (pitch/yaw/roll) via cv2.solvePnP

Requirements:
  pip install mediapipe opencv-python numpy
  Model file: face_landmarker.task (placed alongside this file)
"""

from __future__ import annotations

import math
import os
import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False
    print("[FaceAnalyzer] WARNING: mediapipe not installed — face analysis disabled")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Landmark Indices (478-point mesh with iris refinement)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOSE_TIP = 1
CHIN = 152
L_EYE_OUTER = 33
L_EYE_INNER = 133
L_EYE_TOP = 159
L_EYE_BOTTOM = 145
L_IRIS = 468
R_EYE_OUTER = 263
R_EYE_INNER = 362
R_EYE_TOP = 386
R_EYE_BOTTOM = 374
R_IRIS = 473
MOUTH_LEFT = 61
MOUTH_RIGHT = 291

# 3D model for solvePnP (generic face, mm)
FACE_3D_MODEL = np.array(
    [
        (0.0, 0.0, 0.0),  # Nose tip
        (0.0, -330.0, -65.0),  # Chin
        (-225.0, 170.0, -135.0),  # Left eye outer
        (225.0, 170.0, -135.0),  # Right eye outer
        (-150.0, -150.0, -125.0),  # Left mouth
        (150.0, -150.0, -125.0),  # Right mouth
    ],
    dtype=np.float64,
)
POSE_LANDMARK_IDS = [NOSE_TIP, CHIN, L_EYE_OUTER, R_EYE_OUTER, MOUTH_LEFT, MOUTH_RIGHT]


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Data class
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class FaceAnalysis:
    """Result of analysing a single frame."""

    __slots__ = (
        "timestamp_sec",
        "face_detected",
        "action_units",
        "emotions",
        "gaze_x",
        "gaze_y",
        "gaze_confidence",
        "iris_ratio_x",
        "iris_ratio_y",
        "head_pitch",
        "head_yaw",
        "head_roll",
    )

    def __init__(self, timestamp_sec: float = 0.0):
        self.timestamp_sec = timestamp_sec
        self.face_detected = False
        self.action_units: Dict[str, float] = {}
        self.emotions: Dict[str, float] = {
            "frustration": 0.0,
            "confusion": 0.0,
            "delight": 0.0,
            "boredom": 0.0,
            "surprise": 0.0,
            "engagement": 0.0,
        }
        self.gaze_x: float = 0.5
        self.gaze_y: float = 0.5
        self.gaze_confidence: float = 0.0
        self.iris_ratio_x: float = 0.5
        self.iris_ratio_y: float = 0.5
        self.head_pitch: float = 0.0
        self.head_yaw: float = 0.0
        self.head_roll: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "timestamp_sec": self.timestamp_sec,
            "face_detected": self.face_detected,
            "action_units": dict(self.action_units),
            "emotions": dict(self.emotions),
            "gaze_x": self.gaze_x,
            "gaze_y": self.gaze_y,
            "gaze_confidence": self.gaze_confidence,
            "iris_ratio_x": self.iris_ratio_x,
            "iris_ratio_y": self.iris_ratio_y,
            "head_pitch": self.head_pitch,
            "head_yaw": self.head_yaw,
            "head_roll": self.head_roll,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Gaze Calibrator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class GazeCalibrator:
    """2nd-order polynomial mapping: (iris_ratio_x, iris_ratio_y) -> screen px."""

    def __init__(self):
        self.calibrated: bool = False
        self._coeff_x: Optional[np.ndarray] = None
        self._coeff_y: Optional[np.ndarray] = None
        self.screen_w: int = 0
        self.screen_h: int = 0
        self.mean_error_px: float = -1.0

    def fit(
        self,
        iris_data: List[Tuple[float, float]],
        screen_points: List[Tuple[float, float]],
        screen_w: int,
        screen_h: int,
    ) -> float:
        """Fit polynomial via least-squares. Returns mean error in px."""
        self.screen_w = screen_w
        self.screen_h = screen_h
        n = len(iris_data)
        if n < 4:
            return -1.0

        iris = np.array(iris_data, dtype=np.float64)
        screen = np.array(screen_points, dtype=np.float64)

        X = np.column_stack(
            [
                np.ones(n),
                iris[:, 0],
                iris[:, 1],
                iris[:, 0] ** 2,
                iris[:, 1] ** 2,
                iris[:, 0] * iris[:, 1],
            ]
        )

        self._coeff_x = np.linalg.lstsq(X, screen[:, 0], rcond=None)[0]
        self._coeff_y = np.linalg.lstsq(X, screen[:, 1], rcond=None)[0]

        pred_x = X @ self._coeff_x
        pred_y = X @ self._coeff_y
        errors = np.sqrt((pred_x - screen[:, 0]) ** 2 + (pred_y - screen[:, 1]) ** 2)
        self.mean_error_px = float(errors.mean())
        self.calibrated = True
        return self.mean_error_px

    def predict(self, iris_x: float, iris_y: float) -> Tuple[float, float]:
        if not self.calibrated or self._coeff_x is None:
            return iris_x, iris_y
        feat = np.array(
            [1, iris_x, iris_y, iris_x**2, iris_y**2, iris_x * iris_y]
        )
        gx = float(feat @ self._coeff_x)
        gy = float(feat @ self._coeff_y)
        gx = _clamp(gx, -50, self.screen_w + 50)
        gy = _clamp(gy, -50, self.screen_h + 50)
        return gx, gy


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Face Analyzer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class FaceAnalyzer:
    """MediaPipe FaceLandmarker-based: blendshapes, expressions, gaze, pose."""

    def __init__(self, smoothing: float = 0.3, model_path: Optional[str] = None):
        """
        Args:
            smoothing: EMA alpha for temporal smoothing (0 = none).
            model_path: Path to face_landmarker.task file.
        """
        self._smoothing = smoothing
        self.gaze_calibrator = GazeCalibrator()

        # Temporal smoothing
        self._prev_emotions: Optional[Dict[str, float]] = None
        self._prev_gaze: Optional[Tuple[float, float]] = None

        # Resolve model path
        if model_path is None:
            here = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(here, "face_landmarker.task")

        # Init FaceLandmarker
        self._landmarker = None
        if HAS_MEDIAPIPE and os.path.exists(model_path):
            try:
                opts = vision.FaceLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=model_path),
                    running_mode=vision.RunningMode.IMAGE,
                    num_faces=1,
                    output_face_blendshapes=True,
                    output_facial_transformation_matrixes=True,
                    min_face_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self._landmarker = vision.FaceLandmarker.create_from_options(opts)
                print("[FaceAnalyzer] FaceLandmarker ready (478 lm + 52 blendshapes)")
            except Exception as e:
                print(f"[FaceAnalyzer] Init error: {e}")
        elif not os.path.exists(model_path):
            print(f"[FaceAnalyzer] Model not found: {model_path}")

    # ── Public API ──────────────────────────────────────

    def analyze(self, frame_bgr: np.ndarray, timestamp_sec: float) -> FaceAnalysis:
        """Run full face analysis on a BGR frame."""
        result = FaceAnalysis(timestamp_sec)
        if self._landmarker is None:
            return result

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        try:
            detection = self._landmarker.detect(mp_img)
        except Exception:
            return result

        if not detection.face_landmarks:
            return result

        result.face_detected = True
        lm = detection.face_landmarks[0]
        h, w = frame_bgr.shape[:2]

        # ── Blendshapes → raw AUs ─────────────────────────
        bs: Dict[str, float] = {}
        if detection.face_blendshapes:
            for b in detection.face_blendshapes[0]:
                bs[b.category_name] = round(b.score, 4)
        result.action_units = bs

        # ── Head Pose (computed first for use in expressions) ───
        pitch, yaw, roll = self._compute_head_pose(lm, w, h)
        result.head_pitch = round(pitch, 1)
        result.head_yaw = round(yaw, 1)
        result.head_roll = round(roll, 1)

        # ── Expressions ───────────────────────────────────
        emotions = self._blendshapes_to_expressions(bs, pitch, yaw, roll)
        if self._prev_emotions is not None:
            a = self._smoothing
            for k in emotions:
                emotions[k] = a * self._prev_emotions.get(k, emotions[k]) + (1 - a) * emotions[k]
        self._prev_emotions = dict(emotions)
        result.emotions = {k: round(v, 3) for k, v in emotions.items()}

        # ── Gaze ──────────────────────────────────────────
        iris_rx, iris_ry = self._compute_iris_ratios(lm, bs)
        result.iris_ratio_x = round(iris_rx, 4)
        result.iris_ratio_y = round(iris_ry, 4)

        if self.gaze_calibrator.calibrated:
            gx, gy = self.gaze_calibrator.predict(iris_rx, iris_ry)
            result.gaze_x = round(gx, 1)
            result.gaze_y = round(gy, 1)
            result.gaze_confidence = 0.8
        else:
            result.gaze_x = round(iris_rx, 4)
            result.gaze_y = round(iris_ry, 4)
            result.gaze_confidence = 0.2

        if self._prev_gaze is not None:
            ga = 0.4
            result.gaze_x = round(ga * self._prev_gaze[0] + (1 - ga) * result.gaze_x, 2)
            result.gaze_y = round(ga * self._prev_gaze[1] + (1 - ga) * result.gaze_y, 2)
        self._prev_gaze = (result.gaze_x, result.gaze_y)

        return result

    def reset_baseline(self) -> None:
        self._prev_emotions = None
        self._prev_gaze = None

    def close(self) -> None:
        if self._landmarker:
            self._landmarker.close()
            self._landmarker = None

    # ── Blendshape → Expression Mapping ────────────────

    @staticmethod
    def _blendshapes_to_expressions(
        bs: Dict[str, float],
        head_pitch: float = 0.0,
        head_yaw: float = 0.0,
        head_roll: float = 0.0
    ) -> Dict[str, float]:
        """Map 52 ARKit blendshapes + head pose → 6 playtest expression categories.
        
        Enhanced with:
        - Closed-mouth smile detection for genuine delight
        - Head tilt for confusion
        - Looking down for boredom
        - Head movement patterns for engagement
        
        Future enhancements (requires hand tracking):
        - Head scratching → increased confusion
        - Face palming → frustration spike
        - Mouth covering → excitement/surprise
        """

        # === SURPRISE ===
        # Brows up + eyes wide + jaw open
        surprise = _clamp(
            (
                bs.get("browInnerUp", 0) * 0.25
                + (bs.get("eyeWideLeft", 0) + bs.get("eyeWideRight", 0)) / 2 * 0.35
                + bs.get("jawOpen", 0) * 0.40
            )
            * 1.4
        )

        # === DELIGHT ===
        # Differentiate between closed-mouth smile (genuine delight) and open smile
        smile = (bs.get("mouthSmileLeft", 0) + bs.get("mouthSmileRight", 0)) / 2
        cheek = (bs.get("cheekSquintLeft", 0) + bs.get("cheekSquintRight", 0)) / 2
        jaw_open = bs.get("jawOpen", 0)
        
        # Closed-mouth smile = high smile + low jaw open + cheek squint
        # This is a more genuine/satisfied expression
        closed_smile_bonus = 0.0
        if smile > 0.3 and jaw_open < 0.2:
            closed_smile_bonus = 0.2 * (1 - jaw_open)
        
        delight = _clamp((smile * 0.65 + cheek * 0.35 + closed_smile_bonus) * 1.4)

        # === FRUSTRATION ===
        # Brows down + mouth press + nose sneer
        # TODO: Add face palm detection when hand tracking is enabled
        brow_down = (bs.get("browDownLeft", 0) + bs.get("browDownRight", 0)) / 2
        mouth_press = (bs.get("mouthPressLeft", 0) + bs.get("mouthPressRight", 0)) / 2
        nose_sneer = (bs.get("noseSneerLeft", 0) + bs.get("noseSneerRight", 0)) / 2
        frustration = _clamp(
            (brow_down * 0.40 + mouth_press * 0.30 + nose_sneer * 0.30) * 1.5
        )

        # === CONFUSION ===
        # Brows down + squint + frown + pucker
        # Enhanced with head tilt detection (side-to-side tilting often indicates confusion)
        # TODO: Add head scratching detection when hand tracking is enabled
        eye_squint = (bs.get("eyeSquintLeft", 0) + bs.get("eyeSquintRight", 0)) / 2
        mouth_frown = (bs.get("mouthFrownLeft", 0) + bs.get("mouthFrownRight", 0)) / 2
        
        # Head tilt bonus (confusion often shows as head tilting)
        head_tilt_bonus = min(0.25, abs(head_roll) / 100.0) if abs(head_roll) > 10 else 0.0
        
        confusion = _clamp(
            (brow_down * 0.35 + eye_squint * 0.25 + mouth_frown * 0.25 
             + bs.get("mouthPucker", 0) * 0.15 + head_tilt_bonus * 0.2) * 1.3
        )

        # === BOREDOM ===
        # Low activity + eyes closed + looking down (at phone or distracted)
        blink = (bs.get("eyeBlinkLeft", 0) + bs.get("eyeBlinkRight", 0)) / 2
        activity = (surprise + delight + frustration + confusion + jaw_open + smile) / 6
        
        # Looking down bonus (pitch < -15 degrees = looking down, possibly at phone)
        # Stronger boredom signal if head is tilted down significantly
        looking_down_bonus = 0.0
        if head_pitch < -15:
            # Scale from -15° to -45° → 0.0 to 0.3 bonus
            looking_down_bonus = min(0.3, abs(head_pitch + 15) / 100.0)
        
        boredom = _clamp(
            max(0, 0.5 - activity * 1.5) * 0.5 
            + blink * 0.25 
            + looking_down_bonus * 0.25
        )

        # === ENGAGEMENT ===
        # Eyes open + some expression + head movement (not slumped)
        # TODO: Add mouth covering (hand over mouth) as excitement indicator when hand tracking enabled
        eye_wide = (bs.get("eyeWideLeft", 0) + bs.get("eyeWideRight", 0)) / 2
        
        # Head posture bonus: upright head = more engaged
        # Penalty for extreme downward tilt (disengaged/distracted)
        head_posture = 1.0
        if head_pitch < -30:  # Significantly looking down
            head_posture = max(0.5, 1.0 + head_pitch / 60.0)
        
        engagement = _clamp(
            (
                (1 - blink) * 0.30
                + eye_wide * 0.15
                + min(1.0, activity * 2) * 0.25
                + head_posture * 0.20
                + 0.10
            )
        )

        return {
            "surprise": surprise,
            "delight": delight,
            "frustration": frustration,
            "confusion": confusion,
            "boredom": boredom,
            "engagement": engagement,
        }

    # ── Head Pose ───────────────────────────────────────

    @staticmethod
    def _compute_head_pose(lm, frame_w: int, frame_h: int) -> Tuple[float, float, float]:
        try:
            pts_2d = np.array(
                [(lm[i].x * frame_w, lm[i].y * frame_h) for i in POSE_LANDMARK_IDS],
                dtype=np.float64,
            )
            fl = float(frame_w)
            cx, cy = frame_w / 2.0, frame_h / 2.0
            cam = np.array([[fl, 0, cx], [0, fl, cy], [0, 0, 1]], dtype=np.float64)
            dist_c = np.zeros((4, 1), dtype=np.float64)

            ok, rvec, _ = cv2.solvePnP(
                FACE_3D_MODEL, pts_2d, cam, dist_c, flags=cv2.SOLVEPNP_ITERATIVE
            )
            if not ok:
                return 0.0, 0.0, 0.0

            rmat, _ = cv2.Rodrigues(rvec)
            pitch = math.degrees(math.atan2(rmat[2][1], rmat[2][2]))
            yaw = math.degrees(
                math.atan2(-rmat[2][0], math.sqrt(rmat[2][1] ** 2 + rmat[2][2] ** 2))
            )
            roll = math.degrees(math.atan2(rmat[1][0], rmat[0][0]))
            return pitch, yaw, roll
        except Exception:
            return 0.0, 0.0, 0.0

    # ── Iris Gaze ───────────────────────────────────────

    @staticmethod
    def _compute_iris_ratios(lm, bs: Dict[str, float]) -> Tuple[float, float]:
        """Gaze direction ratio (0-1 each axis).

        Fuses blendshape eye-look directions (60%) with iris landmark
        positions (40%) for stability.
        """
        # Blendshape gaze
        look_left = (bs.get("eyeLookOutLeft", 0) + bs.get("eyeLookInRight", 0)) / 2
        look_right = (bs.get("eyeLookInLeft", 0) + bs.get("eyeLookOutRight", 0)) / 2
        look_up = (bs.get("eyeLookUpLeft", 0) + bs.get("eyeLookUpRight", 0)) / 2
        look_down = (bs.get("eyeLookDownLeft", 0) + bs.get("eyeLookDownRight", 0)) / 2

        rx = 0.5 + (look_right - look_left) * 0.5
        ry = 0.5 + (look_down - look_up) * 0.5

        # Iris landmark fallback / blend
        if len(lm) > R_IRIS:
            try:
                l_iris = lm[L_IRIS]
                li, lo = lm[L_EYE_INNER], lm[L_EYE_OUTER]
                l_w = li.x - lo.x
                l_rx = (l_iris.x - lo.x) / (l_w + 1e-6) if abs(l_w) > 1e-6 else 0.5

                r_iris = lm[R_IRIS]
                ri, ro = lm[R_EYE_INNER], lm[R_EYE_OUTER]
                r_w = ri.x - ro.x
                r_rx = (r_iris.x - ro.x) / (r_w + 1e-6) if abs(r_w) > 1e-6 else 0.5

                iris_rx = (l_rx + r_rx) / 2

                lt, lb = lm[L_EYE_TOP], lm[L_EYE_BOTTOM]
                l_ry = (l_iris.y - lt.y) / (lb.y - lt.y + 1e-6)
                rt, rb = lm[R_EYE_TOP], lm[R_EYE_BOTTOM]
                r_ry = (r_iris.y - rt.y) / (rb.y - rt.y + 1e-6)
                iris_ry = (l_ry + r_ry) / 2

                rx = 0.6 * rx + 0.4 * iris_rx
                ry = 0.6 * ry + 0.4 * iris_ry
            except Exception:
                pass

        return _clamp(rx), _clamp(ry)
