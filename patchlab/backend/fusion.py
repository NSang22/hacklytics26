"""
PatchLab — Temporal Fusion Engine

Aligns three async data streams onto a clean, unified 1-second Pandas DataFrame.

Streams:
  1. Presage emotion frames (~10 Hz)     → resample to 1 Hz by averaging each 1s window
  2. Apple Watch HR/HRV (~1 Hz)          → forward-fill to fill sub-second gaps
  3. Gemini DFA chunk results (variable) → forward-fill from transition timestamps

Output DataFrame columns (one row = 1 second of gameplay):
    t, session_id, state, time_in_state_sec,
    frustration, confusion, delight, boredom, surprise, engagement,
    hr, hrv_rmssd, hrv_sdnn, presage_hr, breathing_rate,
    intent_delta, dominant_emotion, data_quality

Public API (called by main.py and snowflake_writer.py):
    fuse_streams(presage_frames, watch_readings, chunk_results, dfa_config,
                 session_id) -> pd.DataFrame

    fuse_timeline(...)  # legacy-compatible wrapper kept for existing backend calls
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config import FUSION_RESAMPLE_HZ
from models import ChunkResult, DFAConfig, EmotionFrame, FusedRow, WatchReading

logger = logging.getLogger(__name__)

# ── Emotion name → DataFrame column mapping ───────────────────────────────────
# Maps the DFA's human-readable intended_emotion onto the actual measured column.
EMOTION_COLUMN_MAP: Dict[str, str] = {
    "frustration": "frustration",
    "confusion":   "confusion",
    "delight":     "delight",
    "boredom":     "boredom",
    "surprise":    "surprise",
    "engagement":  "engagement",
    # Semantic aliases used by game designers
    "tense":       "frustration",   # tense → frustration channel
    "calm":        "frustration",   # calm  → want frustration LOW (same channel, inverted intent)
    "excited":     "delight",
    "satisfied":   "delight",
    "curious":     "confusion",
    "angry":       "frustration",
    "scared":      "surprise",
}

EMOTION_COLS = ["frustration", "confusion", "delight", "boredom", "surprise", "engagement"]




# ─────────────────────────────────────────────────────────────────────────────
# Input normalizers
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_presage(frames: List[Any]) -> pd.DataFrame:
    """
    Accept Presage data in any of three formats:
      1. List[EmotionFrame] Pydantic objects  (from models.py)
      2. List[dict] with 'timestamp_sec' key  (from backend API)
      3. List[dict] with 'timestamp' key      (from spec / raw SDK)

    Returns a DataFrame with columns: [t_sec, frustration, confusion,
    delight, boredom, surprise, engagement, presage_hr, breathing_rate]
    """
    if not frames:
        return pd.DataFrame(columns=["t_sec"] + EMOTION_COLS + ["presage_hr", "breathing_rate"])

    rows = []
    for f in frames:
        if isinstance(f, EmotionFrame):
            ts = f.timestamp_sec
            row = {
                "t_sec":        ts,
                "frustration":  f.frustration,
                "confusion":    f.confusion,
                "delight":      f.delight,
                "boredom":      f.boredom,
                "surprise":     f.surprise,
                "engagement":   f.engagement,
                "presage_hr":   f.heart_rate,
                "breathing_rate": f.breathing_rate,
            }
        else:
            # Dict — handle both key names
            ts = float(f.get("timestamp_sec", f.get("timestamp", 0.0)))
            row = {
                "t_sec":        ts,
                "frustration":  float(f.get("frustration", 0.0)),
                "confusion":    float(f.get("confusion", 0.0)),
                "delight":      float(f.get("delight", 0.0)),
                "boredom":      float(f.get("boredom", 0.0)),
                "surprise":     float(f.get("surprise", 0.0)),
                "engagement":   float(f.get("engagement", 0.0)),
                "presage_hr":   float(f.get("heart_rate", f.get("hr", 0.0))),
                "breathing_rate": float(f.get("breathing_rate", 0.0)),
            }
        rows.append(row)

    return pd.DataFrame(rows)


def _normalize_watch(readings: List[Any]) -> pd.DataFrame:
    """
    Accept Watch data as List[WatchReading] or List[dict].
    Handles 'timestamp_sec' and 'timestamp' keys. Also handles
    the spec's 'hrv' key mapped to hrv_rmssd.

    Returns DataFrame: [t_sec, hr, hrv_rmssd, hrv_sdnn, movement_variance]
    """
    if not readings:
        return pd.DataFrame(columns=["t_sec", "hr", "hrv_rmssd", "hrv_sdnn", "movement_variance"])

    rows = []
    for r in readings:
        if isinstance(r, WatchReading):
            rows.append({
                "t_sec":             r.timestamp_sec,
                "hr":                r.heart_rate,
                "hrv_rmssd":         r.hrv_rmssd,
                "hrv_sdnn":          r.hrv_sdnn,
                "movement_variance": r.movement_variance,
            })
        else:
            ts = float(r.get("timestamp_sec", r.get("timestamp", 0.0)))
            rows.append({
                "t_sec":             ts,
                "hr":                float(r.get("heart_rate", r.get("hr", 0.0))),
                # spec uses 'hrv' as a single float — treat as rmssd
                "hrv_rmssd":         float(r.get("hrv_rmssd", r.get("hrv", 0.0))),
                "hrv_sdnn":          float(r.get("hrv_sdnn", 0.0)),
                "movement_variance": float(r.get("movement_variance", 0.0)),
            })

    return pd.DataFrame(rows)


def _build_state_timeline(
    chunk_results: List[ChunkResult],
    total_sec: int,
) -> pd.Series:
    """
    Convert ChunkResult transitions into a 1-Hz forward-filled Series of
    state labels indexed 0..total_sec-1.

    Each row's state = the most recent transition whose timestamp_sec <= t.
    If no chunk results, every second is labeled 'unknown'.
    """
    # Collect all transitions across all chunks, sorted by time
    transitions: List[Dict] = []
    for cr in chunk_results:
        for tr in cr.transitions:
            transitions.append({
                "t": tr.timestamp_sec,
                "state": tr.to_state,
            })
        # Also seed the chunk's starting state from states_observed
        for obs in cr.states_observed:
            transitions.append({
                "t": obs.entered_at_sec,
                "state": obs.state_name,
            })

    transitions.sort(key=lambda x: x["t"])

    # Build a full-length index and forward-fill
    index = pd.RangeIndex(total_sec)
    state_series = pd.Series("unknown", index=index, dtype=str, name="state")

    for tr in transitions:
        t_int = int(tr["t"])
        if 0 <= t_int < total_sec:
            state_series.iloc[t_int:] = tr["state"]

    return state_series


# ─────────────────────────────────────────────────────────────────────────────
# Intent delta
# ─────────────────────────────────────────────────────────────────────────────

def _compute_intent_delta(
    df: pd.DataFrame,
    dfa_config: Optional[DFAConfig],
) -> pd.Series:
    """
    For each row, look up the DFA state's intended emotion + score,
    find the actual measured value for that emotion column, and return
    the absolute difference.

    intent_delta = |actual_emotion_score - intended_score|

    If the state isn't in the DFA config, delta = NaN (filled with 0 later).
    """
    if dfa_config is None or not dfa_config.states:
        return pd.Series(0.0, index=df.index)

    # Build lookup: state_name -> (emotion_column, intended_score)
    state_intent: Dict[str, tuple] = {}
    for s in dfa_config.states:
        col = EMOTION_COLUMN_MAP.get(s.intended_emotion.lower(), "frustration")
        state_intent[s.name] = (col, s.acceptable_range[0] + (s.acceptable_range[1] - s.acceptable_range[0]) / 2)
        # Use midpoint of acceptable range as the intended score target

    deltas = []
    for _, row in df.iterrows():
        state = row.get("state", "unknown")
        if state in state_intent:
            col, intended_score = state_intent[state]
            actual = row.get(col, 0.0)
            deltas.append(abs(actual - intended_score))
        else:
            deltas.append(np.nan)

    return pd.Series(deltas, index=df.index).fillna(0.0)


# ─────────────────────────────────────────────────────────────────────────────
# Core fusion function
# ─────────────────────────────────────────────────────────────────────────────

def fuse_streams(
    presage_frames: List[Any],
    watch_readings: List[Any],
    chunk_results: List[ChunkResult],
    dfa_config: Optional[DFAConfig] = None,
    session_id: str = "",
    total_duration_sec: Optional[int] = None,
) -> pd.DataFrame:
    """
    Fuse three data streams into a clean 1-Hz Pandas DataFrame.

    Args:
        presage_frames:      Emotion readings from Presage at ~10 Hz.
                             Accepts List[EmotionFrame] or List[dict] with
                             either 'timestamp' or 'timestamp_sec' keys.
        watch_readings:      Apple Watch HR/HRV at ~1 Hz.
                             Accepts List[WatchReading] or List[dict].
        chunk_results:       Gemini DFA analysis results from chunk_processor.
        dfa_config:          Developer DFA definition (used for intent_delta).
        session_id:          Partition key attached to every row.
        total_duration_sec:  Override session length. Auto-detected if None.

    Returns:
        pd.DataFrame with columns:
            t, session_id, state, time_in_state_sec,
            frustration, confusion, delight, boredom, surprise, engagement,
            hr, hrv_rmssd, hrv_sdnn, presage_hr, breathing_rate,
            intent_delta, dominant_emotion, data_quality
    """
    logger.info(
        f"[fusion] Fusing streams: {len(presage_frames)} presage frames, "
        f"{len(watch_readings)} watch readings, {len(chunk_results)} chunks"
    )

    # ── Step 1: Normalize inputs into DataFrames ───────────────────────────
    presage_df = _normalize_presage(presage_frames)
    watch_df   = _normalize_watch(watch_readings)

    # ── Step 2: Determine total session length ─────────────────────────────
    if total_duration_sec is None:
        candidates = []
        if not presage_df.empty:
            candidates.append(int(presage_df["t_sec"].max()) + 1)
        if not watch_df.empty:
            candidates.append(int(watch_df["t_sec"].max()) + 1)
        if chunk_results:
            candidates.append(int(math.ceil(max(cr.time_range_sec[1] for cr in chunk_results))))
        total_duration_sec = max(candidates) if candidates else 60

    total_sec = int(total_duration_sec)
    index_1hz = pd.RangeIndex(total_sec)  # 0, 1, 2, ... N-1 seconds

    # ── Step 3: Resample Presage to 1 Hz by averaging within each second ──
    if not presage_df.empty:
        presage_df["t_bucket"] = presage_df["t_sec"].astype(int).clip(0, total_sec - 1)
        presage_1hz = (
            presage_df
            .drop(columns=["t_sec"])
            .groupby("t_bucket")
            .mean()
            .reindex(index_1hz)
        )
        # Mark data quality: 1.0 if data present, 0.0 if gap
        data_quality = presage_df.groupby("t_bucket")["frustration"].count().reindex(index_1hz).gt(0).astype(float)
        # Linearly interpolate short gaps (≤ 3s), forward/back-fill edges
        presage_1hz = presage_1hz.interpolate(method="linear", limit=3).ffill().bfill().fillna(0.0)
    else:
        logger.warning("[fusion] No Presage data — filling emotion columns with 0")
        presage_1hz = pd.DataFrame(
            0.0,
            index=index_1hz,
            columns=EMOTION_COLS + ["presage_hr", "breathing_rate"],
        )
        data_quality = pd.Series(0.0, index=index_1hz)

    data_quality = data_quality.reindex(index_1hz).fillna(0.0)

    # ── Step 4: Resample Watch to 1 Hz via forward-fill ───────────────────
    if not watch_df.empty:
        watch_df["t_bucket"] = watch_df["t_sec"].astype(int).clip(0, total_sec - 1)
        watch_1hz = (
            watch_df
            .drop(columns=["t_sec"])
            .groupby("t_bucket")
            .last()           # keep last reading in each second
            .reindex(index_1hz)
            .ffill()          # forward-fill gaps (Watch may drop out temporarily)
            .bfill()          # back-fill leading NaNs
            .fillna(0.0)
        )
    else:
        logger.warning("[fusion] No Watch data — filling HR/HRV columns with 0")
        watch_1hz = pd.DataFrame(
            0.0,
            index=index_1hz,
            columns=["hr", "hrv_rmssd", "hrv_sdnn", "movement_variance"],
        )

    # ── Step 5: Forward-fill DFA state from Gemini chunk results ──────────
    state_series = _build_state_timeline(chunk_results, total_sec)

    # ── Step 6: Assemble the unified DataFrame ─────────────────────────────
    fused = pd.DataFrame(index=index_1hz)
    fused.index.name = "t"
    fused["t"]          = index_1hz
    fused["session_id"] = session_id
    fused["state"]      = state_series.values

    # Emotion columns from Presage
    for col in EMOTION_COLS:
        fused[col] = presage_1hz[col].values if col in presage_1hz.columns else 0.0
    fused["presage_hr"]     = presage_1hz["presage_hr"].values if "presage_hr" in presage_1hz.columns else 0.0
    fused["breathing_rate"] = presage_1hz["breathing_rate"].values if "breathing_rate" in presage_1hz.columns else 0.0

    # Biometric columns from Watch
    fused["hr"]                = watch_1hz["hr"].values
    fused["hrv_rmssd"]         = watch_1hz["hrv_rmssd"].values
    fused["hrv_sdnn"]          = watch_1hz["hrv_sdnn"].values
    fused["movement_variance"] = watch_1hz["movement_variance"].values

    fused["data_quality"] = data_quality.values

    # ── Step 7: Derived columns ────────────────────────────────────────────
    # time_in_state_sec: how many consecutive seconds in the current state
    state_change = fused["state"] != fused["state"].shift(1)
    group_ids = state_change.cumsum()
    fused["time_in_state_sec"] = fused.groupby(group_ids).cumcount()

    # dominant_emotion: which emotion channel is highest at each second
    emotion_vals = fused[["frustration", "confusion", "delight", "boredom", "surprise"]]
    fused["dominant_emotion"] = emotion_vals.idxmax(axis=1).where(emotion_vals.max(axis=1) > 0, "unknown")

    # intent_delta: |actual - intended| for the current state's target emotion
    fused["intent_delta"] = _compute_intent_delta(fused, dfa_config)

    # ── Step 8: Final type enforcement & column ordering ──────────────────
    fused = fused[[
        "t", "session_id", "state", "time_in_state_sec",
        "frustration", "confusion", "delight", "boredom", "surprise", "engagement",
        "hr", "hrv_rmssd", "hrv_sdnn", "presage_hr", "breathing_rate",
        "movement_variance", "intent_delta", "dominant_emotion", "data_quality",
    ]].copy()

    # Round floats for clean storage
    float_cols = [
        "frustration", "confusion", "delight", "boredom", "surprise", "engagement",
        "hr", "hrv_rmssd", "hrv_sdnn", "presage_hr", "breathing_rate",
        "intent_delta", "data_quality",
    ]
    fused[float_cols] = fused[float_cols].round(4)

    logger.info(f"[fusion] Done — {len(fused)} rows, {fused['state'].nunique()} unique states")
    return fused


# ─────────────────────────────────────────────────────────────────────────────
# Legacy-compatible wrapper (keeps existing backend calls working)
# ─────────────────────────────────────────────────────────────────────────────

def fuse_timeline(
    presage_frames: List[Any],
    dfa_transitions: List[Dict[str, Any]],
    watch_readings: List[Any],
    total_duration_sec: int,
    session_id: str = "",
    dfa_config: Optional[DFAConfig] = None,
) -> List[FusedRow]:
    """
    Legacy wrapper — accepts the old dfa_transitions list format and returns
    List[FusedRow] so existing backend code doesn't break.

    Internally converts dfa_transitions to minimal ChunkResult objects,
    calls fuse_streams(), and converts the DataFrame back to FusedRow objects.

    Prefer calling fuse_streams() directly for new code.
    """
    # Convert legacy transition dicts to a single dummy ChunkResult
    dummy_transitions = []
    for tr in dfa_transitions:
        from models import ChunkTransition
        dummy_transitions.append(ChunkTransition(
            from_state=tr.get("from", tr.get("from_state", "unknown")),
            to_state=tr.get("to", tr.get("to_state", "unknown")),
            timestamp_sec=float(tr.get("timestamp_sec", 0.0)),
            confidence=1.0,
        ))

    dummy_chunk = ChunkResult(
        chunk_index=0,
        time_range_sec=(0.0, float(total_duration_sec)),
        transitions=dummy_transitions,
        states_observed=[],
        events=[],
        end_state=dummy_transitions[-1].to_state if dummy_transitions else "unknown",
    )

    df = fuse_streams(
        presage_frames=presage_frames,
        watch_readings=watch_readings,
        chunk_results=[dummy_chunk],
        dfa_config=dfa_config,
        session_id=session_id,
        total_duration_sec=total_duration_sec,
    )

    # Convert DataFrame rows → FusedRow objects
    rows: List[FusedRow] = []
    for _, row in df.iterrows():
        rows.append(FusedRow(
            session_id=row["session_id"],
            timestamp_sec=int(row["t"]),
            current_state=row["state"],
            time_in_state_sec=int(row["time_in_state_sec"]),
            frustration=row["frustration"],
            confusion=row["confusion"],
            delight=row["delight"],
            boredom=row["boredom"],
            surprise=row["surprise"],
            engagement=row["engagement"],
            presage_hr=row["presage_hr"],
            breathing_rate=row["breathing_rate"],
            watch_hr=row["hr"],
            hrv_rmssd=row["hrv_rmssd"],
            hrv_sdnn=row["hrv_sdnn"],
            movement_variance=row["movement_variance"],
            dominant_emotion=row["dominant_emotion"],
            data_quality=row["data_quality"],
        ))

    return rows
