"""
Temporal Fusion Engine — aligns three streams onto a unified 1-second axis.

Streams:
  1. Presage emotion frames (~10 Hz)  → average per 1-second window
  2. Gemini DFA transitions (variable) → forward-fill
  3. Apple Watch readings (~1 Hz)      → direct alignment
"""

from __future__ import annotations

import bisect
from typing import Any, Dict, List, Optional

from models import EmotionFrame, FusedRow, WatchReading


EMOTION_KEYS = ["frustration", "confusion", "delight", "boredom", "surprise"]


def fuse_timeline(
    presage_frames: List[EmotionFrame],
    dfa_transitions: List[Dict[str, Any]],
    watch_readings: List[WatchReading],
    total_duration_sec: int,
    session_id: str = "",
) -> List[FusedRow]:
    """Resample all three streams onto a unified 1-second axis.

    Args:
        presage_frames: Emotion frames from Presage (~10 Hz).
        dfa_transitions: ``[{"timestamp_sec": 0.0, "to": "tutorial"}, …]``
        watch_readings: Apple Watch HR/HRV readings (~1 Hz).
        total_duration_sec: Session length in whole seconds.
        session_id: Attached to every fused row.

    Returns:
        One :class:`FusedRow` per second of gameplay.
    """
    # Pre-sort by timestamp for fast lookups
    presage_sorted = sorted(presage_frames, key=lambda f: f.timestamp_sec)
    watch_sorted = sorted(watch_readings, key=lambda r: r.timestamp_sec)
    dfa_sorted = sorted(dfa_transitions, key=lambda t: t["timestamp_sec"])

    watch_ts = [r.timestamp_sec for r in watch_sorted]

    # Track time-in-state
    state_entry_times: Dict[str, float] = {}

    rows: List[FusedRow] = []

    for t in range(total_duration_sec):
        # ── 1. Presage: average all frames in [t, t+1) ──────────────────
        window = [f for f in presage_sorted if t <= f.timestamp_sec < t + 1]
        if window:
            avg_frust   = _mean([f.frustration for f in window])
            avg_conf    = _mean([f.confusion for f in window])
            avg_del     = _mean([f.delight for f in window])
            avg_bore    = _mean([f.boredom for f in window])
            avg_surp    = _mean([f.surprise for f in window])
            avg_engage  = _mean([f.engagement for f in window])
            avg_p_hr    = _mean([f.heart_rate for f in window])
            avg_breath  = _mean([f.breathing_rate for f in window])
            quality     = 1.0
        else:
            avg_frust = avg_conf = avg_del = avg_bore = avg_surp = 0.0
            avg_engage = avg_p_hr = avg_breath = 0.0
            quality = 0.0

        # ── 2. DFA state: forward-fill ──────────────────────────────────
        current_state = _get_state_at_time(dfa_sorted, t)
        if current_state not in state_entry_times:
            state_entry_times[current_state] = float(t)
        time_in_state = int(t - state_entry_times.get(current_state, t))
        # Reset entry if state changed
        if rows and rows[-1].current_state != current_state:
            state_entry_times[current_state] = float(t)
            time_in_state = 0

        # ── 3. Watch: nearest reading ───────────────────────────────────
        watch = _get_nearest(watch_sorted, watch_ts, t)

        # ── Derived ─────────────────────────────────────────────────────
        emotions = {
            "frustration": avg_frust,
            "confusion": avg_conf,
            "delight": avg_del,
            "boredom": avg_bore,
            "surprise": avg_surp,
        }
        dominant = max(emotions, key=emotions.get) if any(v > 0 for v in emotions.values()) else "unknown"

        w_hr = watch.heart_rate if watch else 0.0
        hr_agree = abs(avg_p_hr - w_hr) <= 5 if (watch and avg_p_hr > 0) else None

        rows.append(FusedRow(
            session_id=session_id,
            timestamp_sec=t,
            current_state=current_state,
            time_in_state_sec=time_in_state,
            frustration=round(avg_frust, 4),
            confusion=round(avg_conf, 4),
            delight=round(avg_del, 4),
            boredom=round(avg_bore, 4),
            surprise=round(avg_surp, 4),
            engagement=round(avg_engage, 4),
            presage_hr=round(avg_p_hr, 1),
            breathing_rate=round(avg_breath, 1),
            watch_hr=round(w_hr, 1),
            hrv_rmssd=round(watch.hrv_rmssd if watch else 0.0, 2),
            hrv_sdnn=round(watch.hrv_sdnn if watch else 0.0, 2),
            movement_variance=round(watch.movement_variance if watch else 0.0, 4),
            dominant_emotion=dominant,
            hr_agreement=hr_agree,
            data_quality=round(quality, 2),
        ))

    return rows


# ── Helpers ─────────────────────────────────────────────────────────────────


def _mean(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _get_state_at_time(transitions: List[Dict[str, Any]], t: float) -> str:
    """Forward-fill: most recent transition before *t*."""
    current = "unknown"
    for tr in transitions:
        if tr["timestamp_sec"] <= t:
            current = tr["to"]
        else:
            break
    return current


def _get_nearest(
    readings: List[WatchReading],
    timestamps: List[float],
    t: float,
) -> Optional[WatchReading]:
    """Binary-search for the nearest watch reading to *t*."""
    if not readings:
        return None
    idx = bisect.bisect_left(timestamps, t)
    if idx == 0:
        return readings[0]
    if idx >= len(readings):
        return readings[-1]
    before = readings[idx - 1]
    after = readings[idx]
    return before if (t - before.timestamp_sec) <= (after.timestamp_sec - t) else after
