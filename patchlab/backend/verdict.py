"""
Verdict engine -- computes PASS / WARN / FAIL per DFA state
and the session-level Playtest Health Score.

Scoring philosophy
------------------
Success is measured by the **absence of contradictory emotions**, not by
exact emotional matching.  First-time players naturally feel surprise --
that is fine unless surprise contradicts the state intent (e.g. a calm
section).  What actually matters is whether the player felt emotions that
signal a real UX problem:

  - boredom when you wanted excitement
  - frustration in a reward moment
  - confusion during a straightforward victory lap

For each developer-intent emotion we define:
  primary        -- MediaPipe keys that positively indicate the intent is
                    being met, with relative weights.
  contradictions -- MediaPipe keys that signal a design problem, with
                    severity weights (1.0 = strong signal, 0.3 = mild).

Anything not listed is **neutral** -- acceptable to be present (e.g.
surprise during an exciting section is totally fine).
"""

from __future__ import annotations

from typing import Any, Dict, List

from models import DFAState, FusedRow, StateVerdict


EMOTION_KEYS = ["frustration", "confusion", "delight", "boredom", "surprise", "engagement"]


# ── Emotion profiles ────────────────────────────────────────────────────────
# For each developer-intent emotion:
#   primary:        MediaPipe keys that positively indicate the intent is met.
#   contradictions: MediaPipe keys that signal a problem, with severity.
#
# Developer-friendly names (used in DFA state configs) map to profiles that
# blend multiple MediaPipe emotions.  Raw MediaPipe key names are also valid
# so developers can use them directly.
# ────────────────────────────────────────────────────────────────────────────

EMOTION_PROFILES: Dict[str, Dict[str, Dict[str, float]]] = {
    # ── Developer-friendly names ────────────────────────────
    "excited": {
        "primary":        {"engagement": 0.5, "surprise": 0.3, "delight": 0.2},
        "contradictions": {"boredom": 1.0, "frustration": 0.7},
    },
    "curious": {
        "primary":        {"engagement": 0.6, "surprise": 0.2, "confusion": 0.2},
        "contradictions": {"boredom": 1.0, "frustration": 0.6},
    },
    "tense": {
        "primary":        {"engagement": 0.4, "surprise": 0.3, "frustration": 0.3},
        "contradictions": {"boredom": 1.0, "delight": 0.3},
    },
    "delighted": {
        "primary":        {"delight": 0.7, "engagement": 0.2, "surprise": 0.1},
        "contradictions": {"frustration": 1.0, "boredom": 0.8, "confusion": 0.5},
    },
    "calm": {
        "primary":        {"engagement": 0.5, "delight": 0.5},
        "contradictions": {"frustration": 1.0, "surprise": 0.6, "confusion": 0.5},
    },
    "surprised": {
        "primary":        {"surprise": 0.7, "engagement": 0.3},
        "contradictions": {"boredom": 1.0},
    },
    "satisfied": {
        "primary":        {"delight": 0.5, "engagement": 0.5},
        "contradictions": {"frustration": 1.0, "boredom": 0.7, "confusion": 0.4},
    },
    # ── Raw MediaPipe keys (developer uses the metric name) ─
    "frustration": {
        "primary":        {"frustration": 0.6, "engagement": 0.4},
        "contradictions": {"boredom": 1.0, "delight": 0.3},
    },
    "confusion": {
        "primary":        {"confusion": 0.6, "engagement": 0.4},
        "contradictions": {"boredom": 1.0},
    },
    "delight": {
        "primary":        {"delight": 0.7, "engagement": 0.2, "surprise": 0.1},
        "contradictions": {"frustration": 1.0, "boredom": 0.8, "confusion": 0.5},
    },
    "boredom": {
        "primary":        {"boredom": 1.0},
        "contradictions": {"engagement": 0.8, "delight": 0.6, "surprise": 0.5},
    },
    "surprise": {
        "primary":        {"surprise": 0.7, "engagement": 0.3},
        "contradictions": {"boredom": 1.0},
    },
    "engagement": {
        "primary":        {"engagement": 0.8, "delight": 0.2},
        "contradictions": {"boredom": 1.0, "frustration": 0.4},
    },
}

_DEFAULT_PROFILE: Dict[str, Dict[str, float]] = {
    "primary":        {"engagement": 1.0},
    "contradictions": {"boredom": 1.0, "frustration": 0.5},
}


def compute_verdict(fused_rows: List[FusedRow], state_config: DFAState) -> StateVerdict:
    """Compute a verdict for a single DFA state.

    Uses contradiction-based scoring: success = low contradictory emotion,
    not exact emotional matching.  Surprise on a first playthrough is fine
    unless it contradicts the intent (e.g. calm section).
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

    # ── Average each emotion across the state ───────────────
    emotion_avgs: Dict[str, float] = {}
    for key in EMOTION_KEYS:
        vals = [getattr(r, key) for r in state_rows]
        emotion_avgs[key] = sum(vals) / len(vals) if vals else 0.0

    dominant = max(emotion_avgs, key=emotion_avgs.get) if emotion_avgs else "unknown"

    # ── Look up the emotion profile ─────────────────────────
    profile = EMOTION_PROFILES.get(intended.lower().strip(), _DEFAULT_PROFILE)

    # ── Positive score: weighted blend of primary emotions ──
    positive_score = 0.0
    for key, weight in profile["primary"].items():
        positive_score += weight * emotion_avgs.get(key, 0.0)
    positive_score = min(positive_score, 1.0)

    # ── Contradiction score: weighted blend of bad signals ──
    contradiction_detail: Dict[str, float] = {}
    contradiction_score = 0.0
    for key, severity in profile["contradictions"].items():
        avg = emotion_avgs.get(key, 0.0)
        if avg > 0.05:  # ignore noise floor
            contribution = severity * avg
            contradiction_detail[key] = round(contribution, 4)
            contradiction_score += contribution
    contradiction_score = min(contradiction_score, 1.0)

    # ── Timing analysis (soft penalty) ──────────────────────
    actual_dur = float(len(state_rows))  # 1 row per second
    time_delta = actual_dur - expected_dur
    time_ratio = actual_dur / expected_dur if expected_dur > 0 else 1.0

    time_penalty = 0.0
    if time_ratio < 0.25:
        time_penalty = 0.15   # suspiciously short
    elif time_ratio > 4.0:
        time_penalty = 0.2    # probably stuck
    elif time_ratio > 2.0:
        time_penalty = 0.1    # somewhat long

    # ── Verdict logic ───────────────────────────────────────
    #   Low contradiction + any positive signal  -> PASS
    #   Moderate contradiction or weak positive   -> WARN
    #   High contradiction                        -> FAIL
    #   Time can downgrade PASS -> WARN, never straight to FAIL

    if contradiction_score < 0.15 and positive_score >= low:
        verdict = "PASS"
    elif contradiction_score < 0.3 and positive_score >= low * 0.5:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    # Time can downgrade PASS -> WARN but not to FAIL by itself
    if verdict == "PASS" and time_penalty >= 0.15:
        verdict = "WARN"

    # ── Deviation score (for health calculation) ────────────
    # Higher = worse.  Dominated by contradictions, time is secondary.
    deviation = contradiction_score + time_penalty * 0.3
    deviation = min(deviation, 1.0)

    return StateVerdict(
        state_name=state_name,
        intended_emotion=intended,
        acceptable_range=(low, high),
        actual_avg_score=round(positive_score, 4),
        actual_dominant_emotion=dominant,
        actual_distribution={k: round(v, 4) for k, v in emotion_avgs.items()},
        actual_duration_sec=actual_dur,
        expected_duration_sec=expected_dur,
        time_delta_sec=round(time_delta, 2),
        intent_met=(verdict == "PASS"),
        deviation_score=round(deviation, 4),
        contradiction_score=round(contradiction_score, 4),
        contradiction_detail=contradiction_detail,
        positive_score=round(positive_score, 4),
        verdict=verdict,
    )


def compute_playtest_health_score(verdicts: List[StateVerdict]) -> float:
    """Weighted average of per-state scores -> 0.0 (worst) to 1.0 (best).

    PASS = 1.0, WARN = 0.6, FAIL = scaled by contradiction severity.
    NO_DATA states are excluded.
    """
    scores: List[float] = []
    for v in verdicts:
        if v.verdict == "PASS":
            scores.append(1.0)
        elif v.verdict == "WARN":
            scores.append(0.6)
        elif v.verdict == "FAIL":
            # Contradiction-driven: low contradiction FAIL still gets some credit
            scores.append(max(0.0, 1.0 - v.contradiction_score - v.deviation_score * 0.3))
        # NO_DATA excluded
    return round(sum(scores) / len(scores), 4) if scores else 0.0
