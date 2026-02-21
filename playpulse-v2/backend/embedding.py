"""
Embedding generator — produces fixed-size feature vectors for 10-second
sliding windows over the fused timeline.  Stored in VectorAI for
cross-session similarity search.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from models import FusedRow

# DFA state names in canonical order (for one-hot encoding)
DEFAULT_STATES = ["tutorial", "puzzle_room", "surprise_event", "gauntlet", "victory"]


def generate_window_embedding(
    fused_rows: List[FusedRow],
    window_start: int,
    window_end: int,
    session_id: str,
    project_id: str,
    tester_name: str = "",
    state_names: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Build an embedding dict for a 10-second window.

    The embedding is a direct feature concat — no ML model needed.

    Returns ``None`` if the window contains no rows.
    """
    states = state_names or DEFAULT_STATES
    window = [r for r in fused_rows if window_start <= r.timestamp_sec < window_end]

    if not window:
        return None

    def _mean(vals: List[float]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    def _std(vals: List[float]) -> float:
        if len(vals) < 2:
            return 0.0
        m = _mean(vals)
        return (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5

    avg_frust = _mean([r.frustration for r in window])
    avg_conf = _mean([r.confusion for r in window])
    avg_del = _mean([r.delight for r in window])
    avg_bore = _mean([r.boredom for r in window])
    avg_surp = _mean([r.surprise for r in window])
    avg_engage = _mean([r.engagement for r in window])

    # Normalise HR to 0-1 range (assume 50-160 BPM range)
    avg_hr_norm = max(0.0, min(1.0, (_mean([r.watch_hr for r in window]) - 50) / 110))
    # Normalise HRV RMSSD (assume 10-100 ms range)
    avg_hrv_norm = max(0.0, min(1.0, (_mean([r.hrv_rmssd for r in window]) - 10) / 90))

    hr_var = _std([r.watch_hr for r in window])
    avg_movement = _mean([r.movement_variance for r in window])

    # One-hot for dominant DFA state in window
    state_counts: Dict[str, int] = {}
    for r in window:
        state_counts[r.current_state] = state_counts.get(r.current_state, 0) + 1
    dom_state = max(state_counts, key=state_counts.get) if state_counts else "unknown"
    state_onehot = [1.0 if s == dom_state else 0.0 for s in states]

    vector = [
        avg_frust, avg_conf, avg_del, avg_bore, avg_surp, avg_engage,
        avg_hr_norm, avg_hrv_norm, hr_var, avg_movement,
    ] + state_onehot

    emotions = {
        "frustration": avg_frust,
        "confusion": avg_conf,
        "delight": avg_del,
        "boredom": avg_bore,
        "surprise": avg_surp,
    }
    dominant_emotion = max(emotions, key=emotions.get) if any(v > 0 for v in emotions.values()) else "unknown"

    return {
        "id": f"{session_id}_{window_start}_{window_end}",
        "vector": [round(v, 6) for v in vector],
        "metadata": {
            "session_id": session_id,
            "project_id": project_id,
            "tester_name": tester_name,
            "dfa_state": dom_state,
            "window_start_sec": window_start,
            "window_end_sec": window_end,
            "dominant_emotion": dominant_emotion,
            "frustration_score": round(avg_frust, 4),
            "confusion_score": round(avg_conf, 4),
        },
    }
