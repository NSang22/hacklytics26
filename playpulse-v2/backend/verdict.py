"""
Verdict engine — computes PASS / WARN / FAIL per DFA state
and the session-level Playtest Health Score.
"""

from __future__ import annotations

from typing import Any, Dict, List

from models import DFAState, FusedRow, StateVerdict


EMOTION_KEYS = ["frustration", "confusion", "delight", "boredom", "surprise"]


def compute_verdict(fused_rows: List[FusedRow], state_config: DFAState) -> StateVerdict:
    """Compute a verdict for a single DFA state.

    Compares the average score of the *intended* emotion against the
    developer-defined acceptable range, then checks whether a different
    emotion dominated instead.
    """
    state_name = state_config.name
    intended = state_config.intended_emotion
    low, high = state_config.acceptable_range
    expected_dur = state_config.expected_duration_sec

    # Filter rows belonging to this state
    state_rows = [r for r in fused_rows if r.current_state == state_name]

    if not state_rows:
        return StateVerdict(
            state_name=state_name,
            intended_emotion=intended,
            acceptable_range=(low, high),
            expected_duration_sec=expected_dur,
            verdict="NO_DATA",
        )

    # Average each emotion across the state
    emotion_avgs: Dict[str, float] = {}
    for key in EMOTION_KEYS:
        vals = [getattr(r, key) for r in state_rows]
        emotion_avgs[key] = sum(vals) / len(vals) if vals else 0.0

    # Map intended emotion name to key (handle aliases)
    intended_key = _resolve_emotion_key(intended)
    intended_score = emotion_avgs.get(intended_key, 0.0)
    dominant = max(emotion_avgs, key=emotion_avgs.get) if emotion_avgs else "unknown"
    actual_dur = float(len(state_rows))  # 1 row per second
    time_delta = actual_dur - expected_dur

    # Deviation & verdict
    if low <= intended_score <= high:
        deviation = 0.0
        verdict = "PASS"
    elif intended_score < low:
        deviation = (low - intended_score) / low if low > 0 else 1.0
        verdict = "FAIL" if deviation > 0.3 else "WARN"
    else:
        deviation = (intended_score - high) / (1.0 - high) if high < 1.0 else 0.0
        verdict = "WARN"

    # Override: dominant emotion very different from intended
    if (
        dominant != intended_key
        and emotion_avgs.get(dominant, 0) > intended_score + 0.2
    ):
        verdict = "FAIL"
        deviation = max(deviation, 0.5)

    return StateVerdict(
        state_name=state_name,
        intended_emotion=intended,
        acceptable_range=(low, high),
        actual_avg_score=round(intended_score, 4),
        actual_dominant_emotion=dominant,
        actual_distribution={k: round(v, 4) for k, v in emotion_avgs.items()},
        actual_duration_sec=actual_dur,
        expected_duration_sec=expected_dur,
        time_delta_sec=round(time_delta, 2),
        intent_met=(verdict == "PASS"),
        deviation_score=round(deviation, 4),
        verdict=verdict,
    )


def compute_playtest_health_score(verdicts: List[StateVerdict]) -> float:
    """Weighted average of per-state scores → 0.0 (worst) to 1.0 (best)."""
    scores: List[float] = []
    for v in verdicts:
        if v.verdict == "PASS":
            scores.append(1.0)
        elif v.verdict == "WARN":
            scores.append(0.5)
        elif v.verdict == "FAIL":
            scores.append(max(0.0, 1.0 - v.deviation_score))
        # NO_DATA excluded
    return round(sum(scores) / len(scores), 4) if scores else 0.0


# ── Helpers ─────────────────────────────────────────────────────────────────

_EMOTION_ALIASES: Dict[str, str] = {
    "calm": "delight",
    "curious": "delight",
    "tense": "surprise",
    "excited": "surprise",
    "satisfied": "delight",
}


def _resolve_emotion_key(name: str) -> str:
    """Map developer-friendly emotion names to the 5-key Presage vocabulary."""
    key = name.lower().strip()
    if key in EMOTION_KEYS:
        return key
    return _EMOTION_ALIASES.get(key, key)
