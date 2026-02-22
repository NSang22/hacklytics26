"""
PatchLab — Chunk Processor

Receives raw .webm / .mp4 gameplay video chunks from the FastAPI backend,
extracts frames at CHUNK_FPS using OpenCV, and sends them to Gemini Vision
to determine which DFA state the player is in.

Public API (called by main.py):
    process_chunk(video_bytes, chunk_index, chunk_start_sec, dfa_config,
                  previous_context, session_id) -> ChunkResult
    process_all_chunks(chunk_data_list, dfa_config, session_id) -> List[ChunkResult]
    stitch_chunk_results(chunk_results) -> Dict

Set MOCK_MODE = True in config.py (or MOCK_MODE=true in .env) to skip
all Gemini calls and return realistic fake data instead.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2  # opencv-python

from config import (
    CHUNK_DURATION_SEC,
    CHUNK_FPS,
    GEMINI_API_KEY,
    GEMINI_MODEL_CHUNK,
    MOCK_MODE,
)
from models import (
    ChunkEvent,
    ChunkResult,
    ChunkStateObservation,
    ChunkTransition,
    DFAConfig,
)

logger = logging.getLogger(__name__)

# ── Retry settings ────────────────────────────────────────────────────────────
MAX_RETRIES = 3
RETRY_DELAY_SEC = 1.5


# ─────────────────────────────────────────────────────────────────────────────
# Frame extraction and gaze overlay
# ─────────────────────────────────────────────────────────────────────────────

def _overlay_gaze_marker(
    frame: Any,  # numpy array (OpenCV BGR image)
    gaze_data: List[Dict],
    frame_time: float,
) -> Any:
    """
    Draw a visual gaze marker on the frame at the player's gaze position.

    Finds the emotion frame closest to frame_time and draws a semi-transparent
    circle + crosshair at (gaze_x, gaze_y) coordinates.

    Args:
        frame: OpenCV BGR image (numpy array)
        gaze_data: List of emotion frames with gaze_x, gaze_y, timestamp_sec
        frame_time: Timestamp of this frame in seconds

    Returns:
        Modified frame with gaze overlay
    """
    if not gaze_data:
        return frame

    # Find nearest gaze reading by timestamp
    closest = min(
        gaze_data,
        key=lambda g: abs(g.get("timestamp_sec", 0.0) - frame_time)
    )

    gaze_x = closest.get("gaze_x", 0.5)
    gaze_y = closest.get("gaze_y", 0.5)
    confidence = closest.get("gaze_confidence", 0.0)

    # Skip if low confidence or invalid coordinates
    if confidence < 0.3 or not (0.0 <= gaze_x <= 1.0 and 0.0 <= gaze_y <= 1.0):
        return frame

    h, w = frame.shape[:2]
    px = int(gaze_x * w)
    py = int(gaze_y * h)

    # Create overlay for semi-transparency
    overlay = frame.copy()

    # Draw outer circle (attention radius)
    radius = int(min(w, h) * 0.04)  # 4% of smaller dimension
    cv2.circle(overlay, (px, py), radius, (0, 255, 255), 2)  # Yellow circle

    # Draw crosshair
    cross_len = radius // 2
    cv2.line(overlay, (px - cross_len, py), (px + cross_len, py), (0, 255, 255), 2)
    cv2.line(overlay, (px, py - cross_len), (px, py + cross_len), (0, 255, 255), 2)

    # Draw center dot
    cv2.circle(overlay, (px, py), 3, (0, 0, 255), -1)  # Red center dot

    # Blend overlay with original (70% overlay, 30% original)
    alpha = 0.7
    frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

    return frame



def extract_frames(
    video_bytes: bytes,
    fps: int = CHUNK_FPS,
    gaze_data: Optional[List[Dict]] = None,
    chunk_start_sec: float = 0.0,
) -> List[bytes]:
    """
    Decode a video chunk (any format OpenCV supports: .mp4, .webm, etc.)
    and return a list of JPEG-encoded frames sampled at `fps` frames/sec.

    If gaze_data is provided, overlays gaze coordinates as visual markers
    on each frame, showing where the player was looking.

    Args:
        video_bytes: Raw video chunk data
        fps: Target sampling rate (frames per second)
        gaze_data: List of emotion frames with gaze_x, gaze_y, timestamp_sec
        chunk_start_sec: Absolute session time when chunk starts

    Writes bytes to a temp file because OpenCV's VideoCapture needs a path.
    Cleans up the temp file afterward.
    """
    frames: List[bytes] = []

    suffix = ".mp4"  # OpenCV figures out the real container from the header
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = tmp.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            logger.warning("[chunk_processor] Could not open video — zero frames returned")
            return frames

        source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = max(1, int(round(source_fps / fps)))

        frame_idx = 0
        frame_count = 0  # Count of extracted frames (not total)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                # Overlay gaze if data available
                if gaze_data:
                    frame_time = chunk_start_sec + (frame_count / fps)
                    frame = _overlay_gaze_marker(frame, gaze_data, frame_time)
                
                ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ok:
                    frames.append(buf.tobytes())
                frame_count += 1
            frame_idx += 1

        cap.release()
        logger.debug(f"[chunk_processor] Extracted {len(frames)} frames from {frame_idx} total")

    except Exception as exc:
        logger.error(f"[chunk_processor] Frame extraction failed: {exc}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return frames


# ─────────────────────────────────────────────────────────────────────────────
# Mock response generator
# ─────────────────────────────────────────────────────────────────────────────

def _generate_mock_result(
    chunk_index: int,
    chunk_start_sec: float,
    dfa_config: DFAConfig,
    previous_context: Optional[Dict],
) -> ChunkResult:
    """
    Returns a realistic-looking ChunkResult without calling Gemini.
    Used when MOCK_MODE = True.

    Simulates the player progressing through DFA states in order,
    spending roughly expected_duration_sec in each state.
    """
    state_names = [s.name for s in dfa_config.states] if dfa_config.states else ["unknown"]
    chunk_end_sec = chunk_start_sec + CHUNK_DURATION_SEC

    # Decide which state we're in based on elapsed time vs expected durations
    elapsed = chunk_start_sec
    current_state_name = state_names[0]
    cumulative_expected = 0.0
    for state in dfa_config.states:
        cumulative_expected += state.expected_duration_sec
        if elapsed < cumulative_expected:
            current_state_name = state.name
            break
    else:
        current_state_name = state_names[-1]

    # Simulate an occasional mid-chunk transition
    transitions: List[ChunkTransition] = []
    if random.random() < 0.25 and len(state_names) > 1:
        idx = state_names.index(current_state_name)
        if idx < len(state_names) - 1:
            next_state = state_names[idx + 1]
            trans_ts = round(chunk_start_sec + random.uniform(2.0, CHUNK_DURATION_SEC - 2.0), 1)
            transitions.append(ChunkTransition(
                from_state=current_state_name,
                to_state=next_state,
                timestamp_sec=trans_ts,
                confidence=round(random.uniform(0.7, 0.95), 2),
            ))
            end_state = next_state
        else:
            end_state = current_state_name
    else:
        end_state = current_state_name

    states_observed: List[ChunkStateObservation] = [
        ChunkStateObservation(
            state_name=current_state_name,
            entered_at_sec=chunk_start_sec,
            exited_at_sec=transitions[0].timestamp_sec if transitions else chunk_end_sec,
            duration_sec=(transitions[0].timestamp_sec if transitions else chunk_end_sec) - chunk_start_sec,
            player_behavior=random.choice(["progressing", "exploring", "stuck", "dying", "confused"]),
            progress=random.choice(["normal", "normal", "normal", "slow", "fast"]),
            matches_success_indicators=random.random() > 0.6,
            matches_failure_indicators=random.random() > 0.8,
        )
    ]
    if transitions:
        states_observed.append(ChunkStateObservation(
            state_name=end_state,
            entered_at_sec=transitions[0].timestamp_sec,
            exited_at_sec=chunk_end_sec,
            duration_sec=chunk_end_sec - transitions[0].timestamp_sec,
            player_behavior="progressing",
            progress="normal",
            matches_success_indicators=True,
            matches_failure_indicators=False,
        ))

    events: List[ChunkEvent] = []
    if random.random() < 0.15:
        events.append(ChunkEvent(
            type="death",
            timestamp_sec=round(chunk_start_sec + random.uniform(1.0, CHUNK_DURATION_SEC - 1.0), 1),
            description="Player died (mock)",
            state=current_state_name,
        ))
    if random.random() < 0.10:
        events.append(ChunkEvent(
            type="stuck",
            timestamp_sec=round(chunk_start_sec + random.uniform(1.0, CHUNK_DURATION_SEC - 1.0), 1),
            description="Player appears stuck (mock)",
            state=current_state_name,
        ))

    prev_deaths = (previous_context or {}).get("cumulative_deaths", 0)
    death_count = sum(1 for e in events if e.type == "death")

    return ChunkResult(
        chunk_index=chunk_index,
        time_range_sec=(chunk_start_sec, chunk_end_sec),
        states_observed=states_observed,
        transitions=transitions,
        events=events,
        end_state=end_state,
        end_status=random.choice(["progressing", "stuck", "exploring"]),
        cumulative_deaths=prev_deaths + death_count,
        chunk_summary=f"[MOCK] chunk {chunk_index}: player in '{current_state_name}'",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Gemini call (real mode)
# ─────────────────────────────────────────────────────────────────────────────

async def _call_gemini_with_retry(
    gemini_client: Any,
    video_bytes: bytes,
    prompt: str,
    session_id: str,
) -> Dict:
    """Calls gemini_client.process_chunk with retry/backoff."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = await gemini_client.process_chunk(video_bytes, prompt, session_id)
            if isinstance(result, dict):
                return result
            return json.loads(result)
        except Exception as exc:
            last_exc = exc
            logger.warning(f"[chunk_processor] Gemini attempt {attempt}/{MAX_RETRIES} failed: {exc}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SEC * attempt)

    logger.error(f"[chunk_processor] All Gemini retries exhausted: {last_exc}")
    return {"states_observed": [], "transitions": [], "events": [], "notes": "gemini_error"}


def _build_gemini_prompt(
    chunk_index: int,
    dfa_config: DFAConfig,
    previous_context: Optional[Dict],
) -> str:
    """Constructs the structured prompt sent to Gemini for each chunk."""
    state_desc = "\n".join(
        f"  - {s.name}: intended_emotion={s.intended_emotion}, "
        f"visual_cues={s.visual_cues}, "
        f"failure_indicators={s.failure_indicators}"
        for s in dfa_config.states
    )
    valid_state_names = [s.name for s in dfa_config.states]

    context_block = ""
    if previous_context:
        context_block = (
            f"\nCONTEXT FROM PREVIOUS CHUNK:\n"
            f"  end_state: {previous_context.get('end_state', 'unknown')}\n"
            f"  end_status: {previous_context.get('end_status', '')}\n"
            f"  cumulative_deaths: {previous_context.get('cumulative_deaths', 0)}\n"
        )

    return f"""Analyze this {CHUNK_DURATION_SEC}-second gameplay recording (chunk #{chunk_index}).

NOTE: Yellow circles with crosshairs on the video show where the player was looking (gaze tracking). 
Use this to determine if the player noticed important visual cues or was looking elsewhere.

DFA STATES (use EXACTLY these names):
{state_desc}
{context_block}
Return ONLY valid JSON:
{{
  "states_observed": [
    {{
      "state_name": "<one of: {valid_state_names}>",
      "entered_at_sec": <absolute seconds from session start>,
      "exited_at_sec": <absolute seconds from session start>,
      "player_behavior": "<progressing|stuck|dying|confused|exploring>",
      "progress": "<fast|normal|slow|stuck>"
    }}
  ],
  "transitions": [
    {{
      "from_state": "<state_name>",
      "to_state": "<state_name>",
      "timestamp_sec": <absolute seconds>,
      "confidence": <0.0-1.0>
    }}
  ],
  "events": [
    {{
      "type": "<death|stuck|backtrack|close_call|exploration>",
      "timestamp_sec": <absolute seconds>,
      "description": "<brief description>",
      "state": "<state_name>"
    }}
  ],
  "end_state": "<state_name>",
  "end_status": "<progressing|stuck|dying|confused|exploring>",
  "chunk_summary": "<one sentence for next chunk context>"
}}"""


def _parse_gemini_response(
    data: Dict,
    chunk_index: int,
    chunk_start_sec: float,
    prev_deaths: int,
) -> ChunkResult:
    """Converts raw Gemini dict into a typed ChunkResult."""
    chunk_end_sec = chunk_start_sec + CHUNK_DURATION_SEC

    states_observed = [
        ChunkStateObservation(
            state_name=obs.get("state_name", "unknown"),
            entered_at_sec=float(obs.get("entered_at_sec", chunk_start_sec)),
            exited_at_sec=float(obs.get("exited_at_sec", chunk_end_sec)),
            duration_sec=float(obs.get("exited_at_sec", chunk_end_sec))
                         - float(obs.get("entered_at_sec", chunk_start_sec)),
            player_behavior=obs.get("player_behavior", "progressing"),
            progress=obs.get("progress", "normal"),
            matches_success_indicators=False,
            matches_failure_indicators=False,
        )
        for obs in data.get("states_observed", [])
    ]

    transitions = [
        ChunkTransition(
            from_state=t.get("from_state"),
            to_state=t.get("to_state", "unknown"),
            timestamp_sec=float(t.get("timestamp_sec", chunk_start_sec)),
            confidence=float(t.get("confidence", 1.0)),
        )
        for t in data.get("transitions", [])
    ]

    events = [
        ChunkEvent(
            type=e.get("type", "unknown"),
            timestamp_sec=float(e.get("timestamp_sec", chunk_start_sec)),
            description=e.get("description", ""),
            state=e.get("state", "unknown"),
        )
        for e in data.get("events", [])
    ]

    death_count = sum(1 for e in events if e.type == "death")

    return ChunkResult(
        chunk_index=chunk_index,
        time_range_sec=(chunk_start_sec, chunk_end_sec),
        states_observed=states_observed,
        transitions=transitions,
        events=events,
        end_state=data.get("end_state", states_observed[-1].state_name if states_observed else "unknown"),
        end_status=data.get("end_status", "progressing"),
        cumulative_deaths=prev_deaths + death_count,
        chunk_summary=data.get("chunk_summary", ""),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def process_chunk(
    video_bytes: bytes,
    chunk_index: int,
    chunk_start_sec: float,
    dfa_config: DFAConfig,
    previous_context: Optional[Dict] = None,
    session_id: str = "",
    gemini_client: Any = None,
    emotion_frames: Optional[List[Dict]] = None,
) -> ChunkResult:
    """
    Process a single gameplay video chunk.

    In MOCK_MODE: returns realistic fake data, no external calls.
    In real mode: extracts frames with OpenCV, sends to Gemini Vision,
                  returns a structured ChunkResult.

    Args:
        video_bytes:      Raw bytes of the video chunk (.mp4 or .webm).
        chunk_index:      Zero-based index of this chunk in the session.
        chunk_start_sec:  Absolute session time (seconds) when this chunk starts.
        dfa_config:       Developer-defined DFA state machine.
        previous_context: Dict from the previous chunk's result (for context chaining).
        session_id:       Used for logging/tracing.
        gemini_client:    GeminiClient instance (only used in real mode).
    """
    logger.info(
        f"[chunk_processor] session={session_id} chunk={chunk_index} "
        f"start={chunk_start_sec}s mode={'MOCK' if MOCK_MODE else 'REAL'}"
    )

    # ── Mock path ─────────────────────────────────────────────────────────────
    if MOCK_MODE:
        await asyncio.sleep(0.05)  # simulate small processing delay
        return _generate_mock_result(
            chunk_index=chunk_index,
            chunk_start_sec=chunk_start_sec,
            dfa_config=dfa_config,
            previous_context=previous_context,
        )

    # ── Real path ─────────────────────────────────────────────────────────────
    if gemini_client is None:
        logger.warning("[chunk_processor] No gemini_client provided — falling back to mock")
        return _generate_mock_result(chunk_index, chunk_start_sec, dfa_config, previous_context)

    if not video_bytes:
        logger.warning(f"[chunk_processor] Empty video_bytes for chunk {chunk_index} — using mock")
        return _generate_mock_result(chunk_index, chunk_start_sec, dfa_config, previous_context)

    # Step 1: Extract frames with OpenCV (with optional gaze overlay)
    frames = extract_frames(
        video_bytes,
        fps=CHUNK_FPS,
        gaze_data=emotion_frames,
        chunk_start_sec=chunk_start_sec,
    )
    if not frames:
        logger.warning(f"[chunk_processor] Frame extraction yielded 0 frames for chunk {chunk_index}")
    elif emotion_frames:
        logger.info(f"[chunk_processor] Overlaid gaze data on {len(frames)} frames")

    # Step 2: Build the prompt
    prompt = _build_gemini_prompt(chunk_index, dfa_config, previous_context)

    # Step 3: Call Gemini with retry
    raw_data = await _call_gemini_with_retry(gemini_client, video_bytes, prompt, session_id)

    # Step 4: Parse into typed model
    prev_deaths = (previous_context or {}).get("cumulative_deaths", 0)
    return _parse_gemini_response(raw_data, chunk_index, chunk_start_sec, prev_deaths)


async def process_all_chunks(
    chunk_data_list: List[bytes],
    dfa_config: DFAConfig,
    session_id: str = "",
    gemini_client: Any = None,
    chunk_duration_sec: float = CHUNK_DURATION_SEC,
) -> List[ChunkResult]:
    """
    Process all chunks for a session sequentially.

    Order matters — each chunk passes context to the next so Gemini
    understands cross-chunk state transitions.
    """
    results: List[ChunkResult] = []
    context: Optional[Dict] = None

    for i, chunk_bytes in enumerate(chunk_data_list):
        chunk_start = i * chunk_duration_sec
        result = await process_chunk(
            video_bytes=chunk_bytes,
            chunk_index=i,
            chunk_start_sec=chunk_start,
            dfa_config=dfa_config,
            previous_context=context,
            session_id=session_id,
            gemini_client=gemini_client,
        )
        results.append(result)

        context = {
            "end_state": result.end_state,
            "end_status": result.end_status,
            "cumulative_deaths": result.cumulative_deaths,
        }
        logger.debug(
            f"[chunk_processor] Finished chunk {i}/{len(chunk_data_list)-1} "
            f"end_state='{result.end_state}' deaths={result.cumulative_deaths}"
        )

    return results


def stitch_chunk_results(chunk_results: List[ChunkResult]) -> Dict:
    """
    Converts per-chunk ChunkResults into a unified session dict.
    All timestamps are already absolute (set by process_chunk).

    Returns:
        {
          "timeline":       [{"timestamp_sec", "state", "behavior", "progress"}],
          "transitions":    [{"from_state", "to_state", "timestamp_sec", "confidence"}],
          "events":         [{"type", "timestamp_sec", "description", "state"}],
          "total_deaths":   int,
          "chunk_summaries": [str],
        }
    """
    timeline: List[Dict] = []
    all_transitions: List[Dict] = []
    all_events: List[Dict] = []

    for cr in sorted(chunk_results, key=lambda c: c.chunk_index):
        for obs in cr.states_observed:
            timeline.append({
                "timestamp_sec": round(obs.entered_at_sec, 2),
                "state": obs.state_name,
                "behavior": obs.player_behavior,
                "progress": obs.progress,
            })
        for t in cr.transitions:
            all_transitions.append({
                "from_state": t.from_state,
                "to_state": t.to_state,
                "timestamp_sec": round(t.timestamp_sec, 2),
                "confidence": t.confidence,
            })
        for e in cr.events:
            all_events.append({
                "type": e.type,
                "timestamp_sec": round(e.timestamp_sec, 2),
                "description": e.description,
                "state": e.state,
            })

    timeline.sort(key=lambda x: x["timestamp_sec"])
    all_transitions.sort(key=lambda x: x["timestamp_sec"])
    all_events.sort(key=lambda x: x["timestamp_sec"])

    merged_timeline = _merge_adjacent_states(timeline)
    total_deaths = sum(1 for e in all_events if e.get("type") == "death")
    chunk_summaries = [
        cr.chunk_summary for cr in sorted(chunk_results, key=lambda c: c.chunk_index)
    ]

    return {
        "timeline": merged_timeline,
        "transitions": all_transitions,
        "events": all_events,
        "total_deaths": total_deaths,
        "chunk_summaries": chunk_summaries,
    }


def _merge_adjacent_states(timeline: List[Dict]) -> List[Dict]:
    """Remove consecutive duplicate state entries, keeping the first of each run."""
    if not timeline:
        return []
    merged = [timeline[0]]
    for entry in timeline[1:]:
        if entry["state"] != merged[-1]["state"]:
            merged.append(entry)
    return merged
