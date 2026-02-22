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

        # Per-person blendshape baseline calibration
        # Captures neutral face values over first N frames, then subtracts them
        self._baseline_frames: List[Dict[str, float]] = []
        self._baseline: Optional[Dict[str, float]] = None
        self._baseline_calibrated = False
        self._BASELINE_FRAME_COUNT = 30  # ~2 seconds at 15 Hz

        # Explicit calibration (overrides auto-baseline when set)
        self._explicit_calibration = False
        self._expression_scale: Dict[str, float] = {}  # emotion → scale factor

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

        # ── Per-person baseline calibration ────────────────
        # Collect neutral-face samples for the first ~2s, then subtract
        if not self._baseline_calibrated:
            self._baseline_frames.append(dict(bs))
            if len(self._baseline_frames) >= self._BASELINE_FRAME_COUNT:
                self._baseline = {}
                all_keys = self._baseline_frames[0].keys()
                for key in all_keys:
                    vals = [f.get(key, 0.0) for f in self._baseline_frames]
                    self._baseline[key] = sum(vals) / len(vals)
                self._baseline_calibrated = True
                print(f"[FaceAnalyzer] Baseline calibrated from {len(self._baseline_frames)} frames")
        
        # Subtract baseline: each person's resting face becomes zero
        if self._baseline is not None:
            for key in bs:
                bs[key] = max(0.0, bs[key] - self._baseline.get(key, 0.0))

        # ── Head Pose (computed first for use in expressions) ───
        pitch, yaw, roll = self._compute_head_pose(lm, w, h)
        result.head_pitch = round(pitch, 1)
        result.head_yaw = round(yaw, 1)
        result.head_roll = round(roll, 1)

        # ── Expressions ───────────────────────────────────
        emotions = self._blendshapes_to_expressions(bs, pitch, yaw, roll)

        # ── Per-person expression scaling ─────────────────
        # If explicit calibration was done, normalize each emotion by the
        # person's measured ceiling so their natural smile → ~0.85 delight, etc.
        if self._explicit_calibration and self._expression_scale:
            for k, scale in self._expression_scale.items():
                if k in emotions:
                    emotions[k] = _clamp(emotions[k] * scale)

        # Differential smoothing: positive emotions persist longer
        if self._prev_emotions is not None:
            for k in emotions:
                # Higher alpha = more persistence (more weight on previous value)
                # Positive emotions (delight, surprise) should linger after expression ends
                if k in ("delight", "surprise"):
                    alpha = 0.75  # 75% previous, 25% current - very slow decay
                elif k == "engagement":
                    alpha = 0.5  # Medium-high persistence for engagement
                else:
                    alpha = 0.35  # Default for negative emotions
                
                emotions[k] = alpha * self._prev_emotions.get(k, emotions[k]) + (1 - alpha) * emotions[k]
        
        # Baseline subtraction: remove resting-face noise floor then clamp to 0
        # This shifts the entire signal down so neutral = 0.0 cleanly
        BASELINE_BOREDOM = 0.05
        BASELINE_CONFUSION = 0.05
        emotions["boredom"] = max(0.0, emotions["boredom"] - BASELINE_BOREDOM)
        emotions["confusion"] = max(0.0, emotions["confusion"] - BASELINE_CONFUSION)
        
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

    def set_explicit_calibration(
        self,
        neutral_bs: Dict[str, float],
        smile_bs: Dict[str, float],
        wide_bs: Dict[str, float],
    ) -> Dict[str, float]:
        """Set per-person calibration from 3-step flow (neutral → smile → eyes wide).

        Computes:
          • Baseline from neutral phase (subtracted from all future readings)
          • Expression ceilings from smile/wide phases → per-emotion scaling factors

        Returns dict of scaling factors applied.
        """
        # Neutral becomes the baseline (replaces auto-calibration)
        self._baseline = dict(neutral_bs)
        self._baseline_calibrated = True
        self._explicit_calibration = True
        self._baseline_frames.clear()  # no longer needed

        # Baseline-subtract the smile and wide captures
        smile_sub = {k: max(0.0, v - neutral_bs.get(k, 0.0)) for k, v in smile_bs.items()}
        wide_sub = {k: max(0.0, v - neutral_bs.get(k, 0.0)) for k, v in wide_bs.items()}

        # Run through expression formulas to get ceilings
        # (head pose = 0 since person faces camera during calibration)
        smile_emotions = self._blendshapes_to_expressions(smile_sub, 0.0, 0.0, 0.0)
        wide_emotions = self._blendshapes_to_expressions(wide_sub, 0.0, 0.0, 0.0)

        delight_ceil = smile_emotions["delight"]
        surprise_ceil = wide_emotions["surprise"]
        engagement_ceil = wide_emotions["engagement"]

        # Compute scale factors: person's natural expression → ~0.85 target
        TARGET = 0.85
        self._expression_scale = {}
        if delight_ceil > 0.05:
            self._expression_scale["delight"] = TARGET / delight_ceil
        if surprise_ceil > 0.05:
            self._expression_scale["surprise"] = TARGET / surprise_ceil
        # Scale engagement eye-wide component indirectly via surprise
        # (engagement uses eye_wide which correlates with surprise)

        print(f"[FaceAnalyzer] Explicit calibration set")
        print(f"  Neutral baseline: {len(neutral_bs)} blendshapes")
        print(f"  Delight ceiling: {delight_ceil:.3f}, scale: {self._expression_scale.get('delight', 1.0):.2f}x")
        print(f"  Surprise ceiling: {surprise_ceil:.3f}, scale: {self._expression_scale.get('surprise', 1.0):.2f}x")

        # Reset smoothing state so first real frame starts fresh
        self._prev_emotions = None
        self._prev_gaze = None

        return dict(self._expression_scale)

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
        raw_squint = (bs.get("eyeSquintLeft", 0) + bs.get("eyeSquintRight", 0)) / 2
        raw_frown = (bs.get("mouthFrownLeft", 0) + bs.get("mouthFrownRight", 0)) / 2
        
        # Threshold: MediaPipe returns ~0.1-0.35 for neutral faces on these AUs.
        # Only count values ABOVE the neutral baseline.
        eye_squint = max(0.0, raw_squint - 0.35)
        mouth_frown = max(0.0, raw_frown - 0.15)
        brow_down_thresh = max(0.0, brow_down - 0.10)
        
        # Head tilt bonus (confusion often shows as head tilting)
        head_tilt_bonus = min(0.25, abs(head_roll) / 100.0) if abs(head_roll) > 15 else 0.0
        
        confusion = _clamp(
            (brow_down_thresh * 0.35 + eye_squint * 0.25 + mouth_frown * 0.25 
             + bs.get("mouthPucker", 0) * 0.15 + head_tilt_bonus * 0.2) * 1.5
        )

        # === BOREDOM ===
        # ONLY triggered by actual disengagement: sustained eye closure + looking away
        # Natural blinks are fast (~0.1-0.3s) and should NOT count as boredom
        raw_blink = (bs.get("eyeBlinkLeft", 0) + bs.get("eyeBlinkRight", 0)) / 2
        
        # Threshold blink: only sustained eye closure (>0.7) counts as boredom signal
        # This filters out natural blinks which are brief spikes
        sustained_eye_close = max(0.0, raw_blink - 0.7) / 0.3  # 0-1 range above threshold
        
        # Looking away penalty (downward gaze suggests distraction/phone)
        looking_away_score = 0.0
        if head_pitch < -20:  # Raised threshold from -15 to -20
            # Scale from -20° to -45° → 0.0 to 0.4
            looking_away_score = min(0.4, abs(head_pitch + 20) / 62.5)
        
        # Boredom requires STRONG disengagement signals
        boredom = _clamp(
            sustained_eye_close * 0.50  # Sustained eye closure only
            + looking_away_score * 0.50  # Looking significantly down/away
        )
        
        # Also store raw blink for engagement calculation
        blink = raw_blink

        # === ENGAGEMENT ===
        # Attention-based: eyes open + looking at screen + facial activity
        # Eyes closed or looking away = disengaged
        eye_wide = (bs.get("eyeWideLeft", 0) + bs.get("eyeWideRight", 0)) / 2
        
        # Eye openness: not blinking = paying attention
        eye_openness = 1.0 - blink
        
        # Attention direction: looking at screen vs looking away
        # Neutral head position (±15°) = attentive, extreme tilt = disengaged
        attention_direction = 1.0
        if head_pitch < -20:  # Looking down significantly
            attention_direction = max(0.3, 1.0 + (head_pitch + 20) / 50.0)
        elif abs(head_yaw) > 25:  # Looking left/right away from screen
            attention_direction = max(0.3, 1.0 - (abs(head_yaw) - 25) / 50.0)
        
        # Activity bonus (but not required for baseline engagement)
        activity = (surprise + delight + frustration + confusion) / 4
        
        engagement = _clamp(
            eye_openness * 0.40  # Eyes open = engaged
            + attention_direction * 0.35  # Looking at screen
            + eye_wide * 0.10  # Interest/alertness
            + min(1.0, activity * 1.5) * 0.15  # Facial activity bonus
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
