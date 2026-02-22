"""
PlayPulse v2 — FastAPI backend
===============================
All endpoints from the spec, in-memory stores for hackathon speed.
Chunked gameplay analysis, three-stream fusion, verdict system.
"""

from __future__ import annotations

import asyncio
import os
import uuid
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import (
    DFAConfig,
    DFAState,
    DFATransitionDef,
    Project,
    Session,
    EmotionFrame,
    WatchReading,
    ChunkResult,
    FusedRow,
    StateVerdict,
)
from fusion import fuse_timeline
from verdict import compute_verdict, compute_playtest_health_score
from embedding import generate_window_embedding
from chunk_processor import process_chunk as cp_process_chunk, stitch_chunk_results

from presage_client import PresageClient
from gemini_client import GeminiClient
from snowflake_client import SnowflakeClient
from vectorai_client import VectorAIClient
from sphinx_client import SphinxClient

# ── Service clients ──────────────────────────────────────────
presage = PresageClient()
gemini = GeminiClient()
snowflake = SnowflakeClient()
vectorai = VectorAIClient()
sphinx = SphinxClient()

# ── In-memory stores ─────────────────────────────────────────
projects: Dict[str, Dict] = {}
sessions: Dict[str, Dict] = {}
session_chunks: Dict[str, Dict[int, bytes]] = {}   # session_id → {chunk_index: bytes}
chunk_results: Dict[str, Dict[int, ChunkResult]] = {}
session_watch_data: Dict[str, List[Dict]] = {}
session_face_video: Dict[str, bytes] = {}
session_fused: Dict[str, List[Dict]] = {}
session_verdicts: Dict[str, List[Dict]] = {}
session_health: Dict[str, float] = {}
session_insights: Dict[str, str] = {}
session_events: Dict[str, List[Dict]] = {}
session_emotion_frames: Dict[str, List[Dict]] = {}  # desktop client emotion data

# ── FastAPI app ──────────────────────────────────────────────
app = FastAPI(title="PlayPulse v2", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ────────────────────────────────────────────────────────────
#   REQUEST / RESPONSE SCHEMAS
# ────────────────────────────────────────────────────────────

class CreateProjectReq(BaseModel):
    name: str
    description: str = ""
    dfa_states: List[Dict] = []   # [{name, description, visual_cues, ...}]
    transitions: List[Dict] = []  # [{from_state, to_state, trigger}]

class UpdateDFAReq(BaseModel):
    states: List[Dict]
    transitions: List[Dict] = []

class CreateSessionReq(BaseModel):
    tester_name: str = "anonymous"
    chunk_duration_sec: float = 15.0   # configurable; demo override = 10

class EmotionFrameBatchReq(BaseModel):
    frames: List[Dict] = []

class WatchDataReq(BaseModel):
    timestamp_sec: float = 0.0
    heart_rate: float = 0.0
    hrv_rmssd: float = 0.0
    hrv_sdnn: float = 0.0
    movement_variance: float = 0.0

class SphinxQueryReq(BaseModel):
    question: str
    session_ids: Optional[List[str]] = None

class VectorSearchReq(BaseModel):
    vector: List[float]
    top_k: int = 5
    filters: Optional[Dict] = None

# ────────────────────────────────────────────────────────────
#   PROJECT ENDPOINTS
# ────────────────────────────────────────────────────────────

@app.get("/v1/projects")
async def list_projects():
    """List all projects (debug/discovery)."""
    return [
        {"id": p["id"], "name": p["name"], "created_at": p.get("created_at")}
        for p in projects.values()
    ]


@app.get("/v1/sessions")
async def list_sessions():
    """List all sessions (debug/discovery)."""
    return [
        {"id": s["id"], "project_id": s["project_id"], "tester": s.get("tester_name", ""), "status": s.get("status", "unknown")}
        for s in sessions.values()
    ]


@app.delete("/v1/projects/{project_id}/data")
async def delete_project_data(project_id: str):
    """Delete all Snowflake data for a given project_id."""
    deleted = await snowflake.delete_project_data(project_id)
    return {"project_id": project_id, "deleted": deleted}


@app.post("/v1/projects")
async def create_project(body: CreateProjectReq):
    pid = str(uuid.uuid4())[:8]
    api_key = f"pp_{uuid.uuid4().hex[:16]}"
    dfa_states = []
    for s in body.dfa_states:
        dfa_states.append(DFAState(
            name=s.get("name", "unnamed"),
            description=s.get("description", ""),
            intended_emotion=s.get("intended_emotion", "delight"),
            acceptable_range=tuple(s.get("acceptable_range", [0.3, 0.7])),
            expected_duration_sec=s.get("expected_duration_sec", 30),
            visual_cues=s.get("visual_cues", []),
            failure_indicators=s.get("failure_indicators", []),
            success_indicators=s.get("success_indicators", []),
        ))
    transitions = [
        DFATransitionDef(
            from_state=t.get("from_state", ""),
            to_state=t.get("to_state", ""),
            trigger=t.get("trigger", ""),
        )
        for t in body.transitions
    ]
    projects[pid] = {
        "id": pid,
        "api_key": api_key,
        "name": body.name,
        "description": body.description,
        "dfa_config": DFAConfig(states=dfa_states, transitions=transitions),
        "optimal_reference": None,
        "created_at": time.time(),
    }
    return {"project_id": pid, "api_key": api_key}


@app.get("/v1/projects/{project_id}")
async def get_project(project_id: str):
    p = projects.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    cfg = p["dfa_config"]
    return {
        "id": p["id"],
        "name": p["name"],
        "description": p["description"],
        "dfa_config": {
            "states": [
                {
                    "name": s.name,
                    "description": s.description,
                    "intended_emotion": s.intended_emotion,
                    "acceptable_range": list(s.acceptable_range),
                    "expected_duration_sec": s.expected_duration_sec,
                    "visual_cues": s.visual_cues,
                    "failure_indicators": s.failure_indicators,
                    "success_indicators": s.success_indicators,
                }
                for s in cfg.states
            ],
            "transitions": [
                {"from_state": t.from_state, "to_state": t.to_state, "trigger": t.trigger}
                for t in cfg.transitions
            ],
        },
        "has_optimal_reference": p["optimal_reference"] is not None,
        "session_count": sum(1 for s in sessions.values() if s["project_id"] == project_id),
    }


@app.put("/v1/projects/{project_id}/dfa")
async def update_dfa(project_id: str, body: UpdateDFAReq):
    p = projects.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    dfa_states = []
    for s in body.states:
        dfa_states.append(DFAState(
            name=s.get("name", "unnamed"),
            description=s.get("description", ""),
            intended_emotion=s.get("intended_emotion", "delight"),
            acceptable_range=tuple(s.get("acceptable_range", [0.3, 0.7])),
            expected_duration_sec=s.get("expected_duration_sec", 30),
            visual_cues=s.get("visual_cues", []),
            failure_indicators=s.get("failure_indicators", []),
            success_indicators=s.get("success_indicators", []),
        ))
    transitions = [
        DFATransitionDef(
            from_state=t.get("from_state", ""),
            to_state=t.get("to_state", ""),
            trigger=t.get("trigger", ""),
        )
        for t in body.transitions
    ]
    p["dfa_config"] = DFAConfig(states=dfa_states, transitions=transitions)
    return {"status": "updated"}


@app.post("/v1/projects/{project_id}/optimal-playthrough")
async def upload_optimal_playthrough(project_id: str, file: UploadFile = File(...)):
    p = projects.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    video_bytes = await file.read()
    cfg = p["dfa_config"]
    reference = await gemini.analyze_optimal_playthrough(
        video_bytes,
        {
            "states": [
                {"name": s.name, "description": s.description, "expected_duration_sec": s.expected_duration_sec}
                for s in cfg.states
            ]
        },
    )
    p["optimal_reference"] = reference
    return {"status": "processed", "reference": reference}

# ────────────────────────────────────────────────────────────
#   SESSION ENDPOINTS
# ────────────────────────────────────────────────────────────

@app.post("/v1/projects/{project_id}/sessions")
async def create_session(project_id: str, body: CreateSessionReq):
    p = projects.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    sid = str(uuid.uuid4())[:8]
    sessions[sid] = {
        "id": sid,
        "project_id": project_id,
        "tester_name": body.tester_name,
        "status": "created",
        "chunks_uploaded": 0,
        "chunks_processed": 0,
        "created_at": time.time(),
        "duration_sec": 0,
        "chunk_duration_sec": body.chunk_duration_sec,
    }
    session_chunks[sid] = {}
    chunk_results[sid] = {}
    session_watch_data[sid] = []
    session_events[sid] = []
    tester_url = f"/play?session={sid}&project={project_id}"
    return {"session_id": sid, "tester_url": tester_url}


@app.get("/v1/sessions/{session_id}")
async def get_session(session_id: str):
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


@app.get("/v1/sessions/{session_id}/status")
async def session_status(session_id: str):
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return {
        "session_id": session_id,
        "status": s["status"],
        "chunks_uploaded": s["chunks_uploaded"],
        "chunks_processed": s["chunks_processed"],
    }


@app.post("/v1/sessions/{session_id}/upload-face-video")
async def upload_face_video(session_id: str, file: UploadFile = File(...)):
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    video_bytes = await file.read()
    session_face_video[session_id] = video_bytes
    return {"status": "received", "size_bytes": len(video_bytes)}


@app.post("/v1/sessions/{session_id}/upload-chunk")
async def upload_chunk(
    session_id: str,
    chunk_index: int = Form(...),
    file: UploadFile = File(...),
):
    """Receive a 15-sec .webm chunk and trigger Gemini processing."""
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(404, "Session not found")

    video_bytes = await file.read()
    if session_id not in session_chunks:
        session_chunks[session_id] = {}
    session_chunks[session_id][chunk_index] = video_bytes
    s["chunks_uploaded"] = len(session_chunks[session_id])
    s["status"] = "recording"

    # Fire-and-forget Gemini processing
    asyncio.create_task(_process_chunk_bg(session_id, chunk_index, video_bytes))

    return {
        "status": "received",
        "chunk_index": chunk_index,
        "size_bytes": len(video_bytes),
    }


async def _process_chunk_bg(session_id: str, chunk_index: int, video_bytes: bytes):
    """Background task: on_chunk_uploaded — run Gemini + write to Snowflake."""
    try:
        s = sessions.get(session_id)
        if not s:
            return
        p = projects.get(s["project_id"])
        if not p:
            return

        # Build sequential context from previous chunk
        prev_context = None
        if chunk_index > 0 and session_id in chunk_results:
            prev_cr = chunk_results[session_id].get(chunk_index - 1)
            if prev_cr:
                last_obs = prev_cr.states_observed[-1] if prev_cr.states_observed else None
                cumulative_deaths = prev_cr.cumulative_deaths  # already tracked cumulatively
                prev_context = {
                    "end_state": last_obs.state_name if last_obs else "unknown",
                    "end_status": prev_cr.end_status,
                    "cumulative_deaths": cumulative_deaths,
                }

        chunk_dur = s.get("chunk_duration_sec", 10.0)
        result = await cp_process_chunk(
            video_bytes=video_bytes,
            chunk_index=chunk_index,
            chunk_start_sec=chunk_index * chunk_dur,
            dfa_config=p["dfa_config"],
            previous_context=prev_context,
            session_id=session_id,
            gemini_client=gemini,
        )
        if session_id not in chunk_results:
            chunk_results[session_id] = {}
        chunk_results[session_id][chunk_index] = result
        s["chunks_processed"] = len(chunk_results[session_id])

        # Write gameplay events to Snowflake bronze layer
        chunk_dur = s.get("chunk_duration_sec", 15.0)
        await snowflake.store_gameplay_events(
            session_id=session_id,
            chunk_index=chunk_index,
            chunk_start_sec=chunk_index * chunk_dur,
            events=[
                {"type": ev.type, "description": ev.description,
                 "timestamp_sec": ev.timestamp_sec}
                for ev in result.events
            ],
            project_id=s["project_id"],
        )
    except Exception as e:
        print(f"[chunk_bg] Error processing chunk {chunk_index} for {session_id}: {e}")


@app.post("/v1/sessions/{session_id}/finalize")
async def finalize_session(session_id: str):
    """Run the full fusion → verdict → embedding pipeline."""
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    s["status"] = "processing"

    p = projects.get(s["project_id"])
    if not p:
        raise HTTPException(404, "Project not found")

    dfa_config: DFAConfig = p["dfa_config"]

    # 1. Stitch chunk results → unified DFA timeline
    cr_list = sorted(chunk_results.get(session_id, {}).values(), key=lambda c: c.chunk_index)
    stitched = stitch_chunk_results(cr_list) if cr_list else {"timeline": [], "transitions": [], "events": []}

    # Convert transitions to the format fusion expects: [{timestamp_sec, to}]
    dfa_transitions = []
    for obs in stitched.get("timeline", []):
        dfa_transitions.append({"timestamp_sec": obs["timestamp_sec"], "to": obs["state"]})
    if not dfa_transitions:
        # Fallback: single "unknown" state
        dfa_transitions = [{"timestamp_sec": 0.0, "to": "tutorial"}]

    # Store events
    session_events[session_id] = stitched.get("events", [])

    # 2. Presage → emotion frames
    #    Priority: desktop client live frames > face video batch > stub
    desktop_frames = session_emotion_frames.get(session_id, [])
    if desktop_frames:
        # Use live emotion data from desktop client
        emotion_frames = [
            EmotionFrame(
                timestamp_sec=f.get("timestamp_sec", 0),
                frustration=f.get("frustration", 0),
                confusion=f.get("confusion", 0),
                delight=f.get("delight", 0),
                boredom=f.get("boredom", 0),
                surprise=f.get("surprise", 0),
                engagement=f.get("engagement", 0),
            )
            for f in desktop_frames
        ]
    else:
        face_bytes = session_face_video.get(session_id, b"")
        emotion_frames = await presage.analyse_video(face_bytes, session_id)

    # 3. Watch data
    watch_data = session_watch_data.get(session_id, [])

    # Determine duration
    duration = max(
        (max((f.timestamp_sec for f in emotion_frames), default=0)),
        (max((w.get("timestamp_sec", 0) for w in watch_data), default=0)),
        (max((obs["timestamp_sec"] for obs in stitched.get("timeline", [])), default=0) + 15),
        30,
    )
    duration = int(duration)
    s["duration_sec"] = duration

    # 4. Temporal fusion
    fused = fuse_timeline(emotion_frames, dfa_transitions, watch_data, duration)
    fused_dicts = [r.__dict__ if hasattr(r, "__dict__") else r for r in fused]
    session_fused[session_id] = fused_dicts

    # Store in Snowflake
    await snowflake.store_fused_rows(session_id, fused_dicts, s["project_id"])

    # 5. Verdicts
    verdicts = []
    for state_def in dfa_config.states:
        v = compute_verdict(fused, state_def)
        verdicts.append(v)
    verdict_dicts = [v.__dict__ if hasattr(v, "__dict__") else v for v in verdicts]
    session_verdicts[session_id] = verdict_dicts
    await snowflake.store_verdicts(session_id, verdict_dicts, s["project_id"])

    # 6. Health score
    health = compute_playtest_health_score(verdicts)
    session_health[session_id] = health
    await snowflake.store_health_score(session_id, health, s["project_id"])

    # 7. Embeddings → VectorAI
    embeddings = []
    for ws in range(0, max(duration - 10, 1), 5):
        emb = generate_window_embedding(
            fused, ws, ws + 10,
            session_id, s["project_id"], s.get("tester_name", ""),
        )
        if emb:
            embeddings.append(emb)
    if embeddings:
        await vectorai.upsert(embeddings)

    # 8. Gemini insights
    insights = await gemini.generate_session_insights(fused_dicts, verdict_dicts, health)
    session_insights[session_id] = insights

    s["status"] = "complete"
    return {"status": "complete", "health_score": health, "verdicts_count": len(verdicts)}

# ────────────────────────────────────────────────────────────
#   RESULT ENDPOINTS
# ────────────────────────────────────────────────────────────

@app.get("/v1/sessions/{session_id}/timeline")
async def get_timeline(session_id: str):
    if session_id not in session_fused:
        raise HTTPException(404, "No fused data yet")
    return {"session_id": session_id, "rows": session_fused[session_id]}


@app.get("/v1/sessions/{session_id}/verdicts")
async def get_verdicts(session_id: str):
    if session_id not in session_verdicts:
        raise HTTPException(404, "No verdicts yet")
    return {"session_id": session_id, "verdicts": session_verdicts[session_id]}


@app.get("/v1/sessions/{session_id}/insights")
async def get_insights(session_id: str):
    return {
        "session_id": session_id,
        "insights": session_insights.get(session_id, "No insights generated yet."),
    }


@app.get("/v1/sessions/{session_id}/health-score")
async def get_health_score(session_id: str):
    if session_id not in session_health:
        raise HTTPException(404, "No health score yet")
    return {"session_id": session_id, "health_score": session_health[session_id]}


@app.get("/v1/sessions/{session_id}/chunks")
async def get_chunks(session_id: str):
    crs = chunk_results.get(session_id, {})
    out = []
    for idx in sorted(crs.keys()):
        cr = crs[idx]
        out.append({
            "chunk_index": cr.chunk_index,
            "chunk_start_sec": cr.time_range_sec[0],
            "summary": cr.chunk_summary,
            "end_status": cr.end_status,
            "states_observed": [
                {"state": o.state_name, "entered_at_sec": o.entered_at_sec,
                 "exited_at_sec": o.exited_at_sec, "progress": o.progress}
                for o in cr.states_observed
            ],
            "events": [
                {"type": e.type, "description": e.description, "timestamp_sec": e.timestamp_sec}
                for e in cr.events
            ],
        })
    return {"session_id": session_id, "chunks": out}


@app.get("/v1/sessions/{session_id}/events")
async def get_events(session_id: str):
    return {"session_id": session_id, "events": session_events.get(session_id, [])}

# ────────────────────────────────────────────────────────────
#   AGGREGATE ENDPOINTS (cross-tester)
# ────────────────────────────────────────────────────────────

@app.get("/v1/projects/{project_id}/aggregate")
async def aggregate(project_id: str):
    p = projects.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    proj_sessions = [s for s in sessions.values() if s["project_id"] == project_id and s["status"] == "complete"]
    summary = []
    for s in proj_sessions:
        summary.append({
            "session_id": s["id"],
            "tester_name": s.get("tester_name", ""),
            "health_score": session_health.get(s["id"], 0),
            "duration_sec": s.get("duration_sec", 0),
        })
    return {"project_id": project_id, "sessions": summary}


@app.get("/v1/projects/{project_id}/aggregate/verdicts")
async def aggregate_verdicts(project_id: str):
    proj_sessions = [s for s in sessions.values() if s["project_id"] == project_id and s["status"] == "complete"]
    all_v: Dict[str, List] = {}
    for s in proj_sessions:
        vds = session_verdicts.get(s["id"], [])
        all_v[s["id"]] = vds
    return {"project_id": project_id, "by_session": all_v}


@app.get("/v1/projects/{project_id}/aggregate/insights")
async def aggregate_insights(project_id: str):
    proj_sessions = [s for s in sessions.values() if s["project_id"] == project_id and s["status"] == "complete"]
    agg_data = []
    for s in proj_sessions:
        agg_data.append({
            "session_id": s["id"],
            "tester_name": s.get("tester_name", ""),
            "health_score": session_health.get(s["id"], 0),
            "verdicts": session_verdicts.get(s["id"], []),
        })
    insights_text = await gemini.generate_cross_tester_insights(agg_data)
    return {"project_id": project_id, "insights": insights_text}


@app.get("/v1/projects/{project_id}/health-trend")
async def health_trend(project_id: str):
    proj_sessions = [s for s in sessions.values() if s["project_id"] == project_id and s["status"] == "complete"]
    proj_sessions.sort(key=lambda s: s.get("created_at", 0))
    trend = [
        {
            "session_id": s["id"],
            "tester_name": s.get("tester_name", ""),
            "health_score": session_health.get(s["id"], 0),
            "created_at": s.get("created_at", 0),
        }
        for s in proj_sessions
    ]
    return {"project_id": project_id, "trend": trend}

# ────────────────────────────────────────────────────────────
#   SPHINX + VECTORAI ENDPOINTS
# ────────────────────────────────────────────────────────────

@app.post("/v1/projects/{project_id}/sphinx-query")
async def sphinx_query(project_id: str, body: SphinxQueryReq):
    if project_id not in projects:
        raise HTTPException(404, "Project not found")
    result = await sphinx.query(body.question, project_id, body.session_ids)
    return result


@app.post("/v1/projects/{project_id}/vector-search")
async def vector_search(project_id: str, body: VectorSearchReq):
    if project_id not in projects:
        raise HTTPException(404, "Project not found")
    filters = body.filters or {}
    filters["project_id"] = project_id
    results = await vectorai.search(body.vector, body.top_k, filters)
    return {"results": results}

# ────────────────────────────────────────────────────────────
#   DESKTOP CLIENT — EMOTION FRAMES + WATCH REST
# ────────────────────────────────────────────────────────────

@app.post("/v1/sessions/{session_id}/emotion-frames")
async def upload_emotion_frames(session_id: str, body: EmotionFrameBatchReq):
    """Receive a batch of emotion frames from the desktop Presage client."""
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    if session_id not in session_emotion_frames:
        session_emotion_frames[session_id] = []
    session_emotion_frames[session_id].extend(body.frames)
    return {
        "status": "ok",
        "frames_received": len(body.frames),
        "total_frames": len(session_emotion_frames[session_id]),
    }


@app.post("/v1/sessions/{session_id}/watch-data")
async def upload_watch_data(session_id: str, body: WatchDataReq):
    """REST fallback for watch readings (when WebSocket is unavailable)."""
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    reading = {
        "timestamp_sec": body.timestamp_sec,
        "heart_rate": body.heart_rate,
        "hrv_rmssd": body.hrv_rmssd,
        "hrv_sdnn": body.hrv_sdnn,
        "movement_variance": body.movement_variance,
    }
    if session_id not in session_watch_data:
        session_watch_data[session_id] = []
    session_watch_data[session_id].append(reading)
    return {"status": "ok", "readings_count": len(session_watch_data[session_id])}


@app.get("/v1/sessions/{session_id}/collection-status")
async def collection_status(session_id: str):
    """Return data collection stats for the desktop client / dashboard."""
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return {
        "session_id": session_id,
        "status": s["status"],
        "chunks_uploaded": s.get("chunks_uploaded", 0),
        "chunks_processed": s.get("chunks_processed", 0),
        "emotion_frames": len(session_emotion_frames.get(session_id, [])),
        "watch_readings": len(session_watch_data.get(session_id, [])),
        "has_face_video": session_id in session_face_video,
    }


# ────────────────────────────────────────────────────────────
#   WEBSOCKET — LIVE WATCH DATA
# ────────────────────────────────────────────────────────────

@app.websocket("/v1/sessions/{session_id}/watch-stream")
async def watch_stream(ws: WebSocket, session_id: str):
    s = sessions.get(session_id)
    if not s:
        await ws.close(code=4004)
        return
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            reading = {
                "timestamp_sec": data.get("timestamp_sec", time.time() - s.get("created_at", time.time())),
                "heart_rate": data.get("heart_rate", 0),
                "hrv_rmssd": data.get("hrv_rmssd", 0),
                "hrv_sdnn": data.get("hrv_sdnn", 0),
                "movement_variance": data.get("movement_variance", 0),
            }
            if session_id not in session_watch_data:
                session_watch_data[session_id] = []
            session_watch_data[session_id].append(reading)
            await ws.send_json({"status": "ok", "readings_count": len(session_watch_data[session_id])})
    except WebSocketDisconnect:
        pass

# ────────────────────────────────────────────────────────────
#   HEALTH CHECK
# ────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "PlayPulse v2",
        "version": "2.0.0",
        "projects": len(projects),
        "sessions": len(sessions),
    }


# ── Run ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
