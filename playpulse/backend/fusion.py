"""
Fusion engine — aligns game events and emotion frames by timestamp.
"""

from __future__ import annotations

import bisect
from typing import Any, Dict, List


def fuse_events_and_emotions(
    events: List[Dict[str, Any]],
    emotions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Align game events with the nearest emotion frame by timestamp.

    For every game event, finds the closest emotion frame (by absolute
    timestamp difference) and bundles them together.

    Args:
        events:  List of game event dicts, each with a ``timestamp`` key.
        emotions: List of emotion frame dicts, each with a ``timestamp`` key.

    Returns:
        Unified timeline — one entry per game event, each containing the
        original event, the nearest emotion frame, and a contextualized
        human-readable note.
    """
    if not events:
        return []

    emotion_timestamps = [e["timestamp"] for e in emotions] if emotions else []

    fused: List[Dict[str, Any]] = []
    for event in events:
        t = event["timestamp"]
        closest_emotion: Dict[str, Any] = {}

        if emotion_timestamps:
            idx = bisect.bisect_left(emotion_timestamps, t)
            # Choose the side that is actually closer
            if idx == 0:
                closest_emotion = emotions[0]
            elif idx >= len(emotions):
                closest_emotion = emotions[-1]
            else:
                before = emotions[idx - 1]
                after = emotions[idx]
                if (t - before["timestamp"]) <= (after["timestamp"] - t):
                    closest_emotion = before
                else:
                    closest_emotion = after

        fused.append(
            {
                "timestamp": t,
                "event": event,
                "emotion": closest_emotion,
                "contextualized": _contextualize(event, closest_emotion),
            }
        )

    return fused


def _contextualize(event: Dict[str, Any], emotion: Dict[str, Any]) -> str:
    """Generate a short human-readable insight from an event+emotion pair."""
    emotions = emotion.get("emotions", {})
    frustration = emotions.get("frustration", 0)
    confusion = emotions.get("confusion", 0)
    delight = emotions.get("delight", 0)

    name = event.get("event_name", "")

    if name == "player_death" and frustration > 0.7:
        return f"Player died and showed high frustration ({frustration:.0%})"
    if name == "stuck_detected" and confusion > 0.6:
        return f"Player stuck with high confusion ({confusion:.0%}) — likely unclear design"
    if "milestone" in event.get("event_type", "") and delight > 0.6:
        return f"Milestone reached with positive response ({delight:.0%})"

    return ""


def compare_intent_vs_reality(
    fused: List[Dict[str, Any]],
    segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compare actual averaged emotions against intended emotions for each segment."""
    results: List[Dict[str, Any]] = []

    for seg in segments:
        seg_name = seg["name"]
        intended = seg["intended_emotion"]

        seg_emotions = _get_emotions_for_segment(fused, seg_name)

        if not seg_emotions:
            results.append(
                {
                    "segment": seg_name,
                    "intended": intended,
                    "actual_dominant": None,
                    "actual_distribution": {},
                    "intent_met": None,
                    "deviation_score": None,
                }
            )
            continue

        avg = _average_emotions(seg_emotions)
        dominant = max(avg, key=avg.get) if avg else "unknown"
        intent_met = intended.lower() in dominant.lower()

        results.append(
            {
                "segment": seg_name,
                "intended": intended,
                "actual_dominant": dominant,
                "actual_distribution": avg,
                "intent_met": intent_met,
                "deviation_score": round(1.0 - avg.get(intended.lower(), 0), 3),
            }
        )

    return results


# ── helpers ─────────────────────────────────────────────────────────────────


def _get_emotions_for_segment(
    fused: List[Dict[str, Any]], segment_name: str
) -> List[Dict[str, float]]:
    """Return emotion dicts for all fused entries that fall inside *segment_name*.

    Segment boundaries are inferred from ``state_change`` events whose
    ``event_name`` contains the segment name.
    """
    in_segment = False
    collected: List[Dict[str, float]] = []

    for entry in fused:
        ev = entry.get("event", {})
        if ev.get("event_type") == "state_change":
            if segment_name.lower() in ev.get("event_name", "").lower():
                in_segment = True
            else:
                if in_segment:
                    in_segment = False  # exited the segment

        if in_segment and entry.get("emotion", {}).get("emotions"):
            collected.append(entry["emotion"]["emotions"])

    return collected


def _average_emotions(emotion_dicts: List[Dict[str, float]]) -> Dict[str, float]:
    """Average a list of {emotion_name: score} dicts."""
    if not emotion_dicts:
        return {}
    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    for d in emotion_dicts:
        for k, v in d.items():
            totals[k] = totals.get(k, 0.0) + v
            counts[k] = counts.get(k, 0) + 1
    return {k: round(totals[k] / counts[k], 4) for k in totals}


def compute_session_stats(fused: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute high-level summary stats from a fused timeline."""
    if not fused:
        return {}

    total_events = len(fused)
    deaths = sum(
        1 for f in fused if f["event"].get("event_name") == "player_death"
    )
    stuck = sum(
        1 for f in fused if f["event"].get("event_name") == "stuck_detected"
    )
    duration = fused[-1]["timestamp"] - fused[0]["timestamp"] if len(fused) > 1 else 0

    return {
        "total_events": total_events,
        "deaths": deaths,
        "stuck_events": stuck,
        "duration_sec": round(duration, 2),
    }
