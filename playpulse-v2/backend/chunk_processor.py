"""
Chunk processor — orchestrates the sequential processing of 15-second
gameplay video chunks through Gemini 2.0 Flash, then stitches the
per-chunk results into a coherent session-level timeline.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from models import (
    ChunkEvent,
    ChunkResult,
    ChunkStateObservation,
    ChunkTransition,
    DFAConfig,
)


async def process_chunk(
    gemini_client: Any,
    chunk_index: int,
    video_bytes: bytes,
    dfa_config: DFAConfig,
    previous_context: Optional[Dict] = None,
    session_id: str = "",
) -> ChunkResult:
    """Process a single 15-second .webm chunk through Gemini.

    Returns a ChunkResult with detected states, transitions, and events.
    ``previous_context`` carries forward key info from prior chunks so
    Gemini can reason about cross-chunk transitions.
    """
    context_prompt = ""
    if previous_context:
        end_state = previous_context.get("end_state", "unknown")
        end_status = previous_context.get("end_status", "")
        cum_deaths = previous_context.get("cumulative_deaths", 0)
        context_prompt = (
            f"\nCONTEXT FROM PREVIOUS CHUNK:\n"
            f"Ended in state: {end_state}\n"
            f"Player status: {end_status}\n"
            f"Cumulative deaths so far: {cum_deaths}\n"
        )

    state_desc = "\n".join(
        f"  - {s.name}: description=\"{s.description}\", "
        f"visual_cues={s.visual_cues}, "
        f"failure_indicators={s.failure_indicators}, "
        f"success_indicators={s.success_indicators}, "
        f"expected_duration_sec={s.expected_duration_sec}"
        for s in dfa_config.states
    )

    prompt = f"""Analyze this 15-second gameplay recording (chunk #{chunk_index}).

DFA States:
{state_desc}
{context_prompt}

Return JSON with:
{{
  "states_observed": [
    {{"state": "<dfa_state_name>", "confidence": 0.0-1.0, "timestamp_in_chunk_sec": 0.0}}
  ],
  "transitions": [
    {{"from_state": "...", "to_state": "...", "trigger": "...", "timestamp_sec": 0.0}}
  ],
  "events": [
    {{"label": "...", "description": "...", "timestamp_sec": 0.0, "severity": "info|warning|critical"}}
  ],
  "notes": "Brief context for the next chunk"
}}
"""

    raw = await gemini_client.process_chunk(video_bytes, prompt, session_id)

    # Parse the response — gemini_client stub returns pre-formed dict
    if isinstance(raw, dict):
        data = raw
    else:
        import json
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            data = {"states_observed": [], "transitions": [], "events": [], "notes": ""}

    chunk_start_sec = chunk_index * 15.0

    states_obs = [
        ChunkStateObservation(
            state=s.get("state", "unknown"),
            confidence=s.get("confidence", 0.5),
            timestamp_in_chunk_sec=s.get("timestamp_in_chunk_sec", 0.0),
        )
        for s in data.get("states_observed", [])
    ]

    transitions = [
        ChunkTransition(
            from_state=t.get("from_state", "unknown"),
            to_state=t.get("to_state", "unknown"),
            trigger=t.get("trigger", ""),
            timestamp_sec=t.get("timestamp_sec", 0.0),
        )
        for t in data.get("transitions", [])
    ]

    events = [
        ChunkEvent(
            label=e.get("label", ""),
            description=e.get("description", ""),
            timestamp_sec=e.get("timestamp_sec", 0.0),
            severity=e.get("severity", "info"),
        )
        for e in data.get("events", [])
    ]

    return ChunkResult(
        chunk_index=chunk_index,
        chunk_start_sec=chunk_start_sec,
        states_observed=states_obs,
        transitions=transitions,
        events=events,
        notes=data.get("notes", ""),
    )


async def process_all_chunks(
    gemini_client: Any,
    chunk_data_list: List[bytes],
    dfa_config: DFAConfig,
    session_id: str = "",
) -> List[ChunkResult]:
    """Process chunks sequentially (order matters for context chaining)."""
    results: List[ChunkResult] = []
    context: Optional[Dict] = None

    for i, chunk_bytes in enumerate(chunk_data_list):
        result = await process_chunk(
            gemini_client=gemini_client,
            chunk_index=i,
            video_bytes=chunk_bytes,
            dfa_config=dfa_config,
            previous_context=context,
            session_id=session_id,
        )
        results.append(result)

        # Build context for next chunk
        cum_deaths = sum(
            1 for cr in results
            for e in cr.events if e.label == "death" or "death" in (e.description or "").lower()
        )
        if result.states_observed:
            last_obs = max(result.states_observed, key=lambda s: s.timestamp_in_chunk_sec)
            context = {
                "end_state": last_obs.state,
                "end_status": result.notes,
                "cumulative_deaths": cum_deaths,
            }
        else:
            context = {
                "end_state": "unknown",
                "end_status": result.notes,
                "cumulative_deaths": cum_deaths,
            }

    return results


def stitch_chunk_results(chunk_results: List[ChunkResult]) -> Dict:
    """Re-map chunk-local timestamps to absolute session seconds and
    merge adjacent identical state observations.

    Returns a dict with keys:
        timeline  — list of {timestamp_sec, state, confidence}
        transitions — list of ChunkTransition (absolute times)
        events — list of ChunkEvent (absolute times)
    """
    timeline: List[Dict] = []
    all_transitions: List[Dict] = []
    all_events: List[Dict] = []

    for cr in sorted(chunk_results, key=lambda c: c.chunk_index):
        offset = cr.chunk_start_sec
        for obs in cr.states_observed:
            timeline.append({
                "timestamp_sec": round(offset + obs.timestamp_in_chunk_sec, 2),
                "state": obs.state,
                "confidence": obs.confidence,
            })
        for t in cr.transitions:
            all_transitions.append({
                "from_state": t.from_state,
                "to_state": t.to_state,
                "trigger": t.trigger,
                "timestamp_sec": round(offset + t.timestamp_sec, 2),
            })
        for e in cr.events:
            all_events.append({
                "label": e.label,
                "description": e.description,
                "timestamp_sec": round(offset + e.timestamp_sec, 2),
                "severity": e.severity,
            })

    # Sort everything by timestamp
    timeline.sort(key=lambda x: x["timestamp_sec"])
    all_transitions.sort(key=lambda x: x["timestamp_sec"])
    all_events.sort(key=lambda x: x["timestamp_sec"])

    # Merge consecutive identical states
    merged_timeline = merge_adjacent_states(timeline)

    total_deaths = sum(
        1 for e in all_events
        if e.get("label") == "death" or "death" in e.get("description", "").lower()
    )
    chunk_summaries = [cr.notes for cr in sorted(chunk_results, key=lambda c: c.chunk_index)]

    return {
        "timeline": merged_timeline,
        "transitions": all_transitions,
        "events": all_events,
        "total_deaths": total_deaths,
        "chunk_summaries": chunk_summaries,
    }


def merge_adjacent_states(timeline: List[Dict]) -> List[Dict]:
    """Remove redundant consecutive observations of the same DFA state,
    keeping the first occurrence in each run."""
    if not timeline:
        return []
    merged = [timeline[0]]
    for entry in timeline[1:]:
        if entry["state"] != merged[-1]["state"]:
            merged.append(entry)
        else:
            # Keep higher confidence
            if entry["confidence"] > merged[-1]["confidence"]:
                merged[-1]["confidence"] = entry["confidence"]
    return merged
