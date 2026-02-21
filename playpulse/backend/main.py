"""
PlayPulse Backend — FastAPI application.

Endpoints:
  WS  /v1/stream                          Game event ingestion
  WS  /v1/presage-stream                   Presage emotion ingestion
  WS  /v1/dashboard-stream/{session_id}    Live broadcast to dashboard
  POST /v1/projects                        Create a project
  POST /v1/projects/{project_id}/sessions  Create a tester session
  GET  /v1/projects/{project_id}           Get project info
  GET  /v1/sessions/{session_id}           Get session info
  GET  /v1/sessions/{session_id}/events    List game events
  GET  /v1/sessions/{session_id}/emotions  List emotion frames
  GET  /v1/sessions/{session_id}/analysis  Fused analysis
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from models import (
    CreateProjectRequest,
    CreateSessionRequest,
    Project,
    Session,
)
from fusion import compare_intent_vs_reality, compute_session_stats, fuse_events_and_emotions

# ── App & CORS ──────────────────────────────────────────────────────────────

app = FastAPI(title="PlayPulse API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory stores ───────────────────────────────────────────────────────

projects: Dict[str, Dict[str, Any]] = {}
sessions: Dict[str, Dict[str, Any]] = {}
session_events: Dict[str, List[Dict[str, Any]]] = {}
session_emotions: Dict[str, List[Dict[str, Any]]] = {}

# Dashboard WebSocket subscribers: session_id -> list[WebSocket]
dashboard_clients: Dict[str, List[WebSocket]] = {}

# ── Helpers ─────────────────────────────────────────────────────────────────


async def broadcast_to_dashboard(session_id: str, data: Dict[str, Any]) -> None:
    """Send a JSON message to every dashboard client watching *session_id*."""
    dead: List[WebSocket] = []
    for ws in dashboard_clients.get(session_id, []):
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    # Clean up disconnected clients
    for ws in dead:
        dashboard_clients[session_id].remove(ws)


# ── WebSocket — Game event ingestion ───────────────────────────────────────


@app.websocket("/v1/stream")
async def stream_events(
    websocket: WebSocket,
    session_id: str = Query(...),
    api_key: str = Query(""),
):
    await websocket.accept()

    if session_id not in session_events:
        session_events[session_id] = []

    # Mark session active if it exists
    if session_id in sessions:
        sessions[session_id]["status"] = "active"

    try:
        while True:
            data = await websocket.receive_text()
            event = json.loads(data)
            event["received_at"] = datetime.utcnow().isoformat()
            session_events[session_id].append(event)

            # Broadcast to dashboard watchers
            await broadcast_to_dashboard(session_id, {"type": "game_event", **event})

    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ── WebSocket — Presage emotion ingestion ──────────────────────────────────


@app.websocket("/v1/presage-stream")
async def presage_stream(
    websocket: WebSocket,
    session_id: str = Query(...),
):
    await websocket.accept()

    if session_id not in session_emotions:
        session_emotions[session_id] = []

    try:
        while True:
            data = await websocket.receive_text()
            frame = json.loads(data)
            session_emotions[session_id].append(frame)

            await broadcast_to_dashboard(
                session_id,
                {"type": "emotion", **frame},
            )

    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ── WebSocket — Dashboard live stream ──────────────────────────────────────


@app.websocket("/v1/dashboard-stream/{session_id}")
async def dashboard_stream(websocket: WebSocket, session_id: str):
    await websocket.accept()

    if session_id not in dashboard_clients:
        dashboard_clients[session_id] = []
    dashboard_clients[session_id].append(websocket)

    try:
        # Keep connection open; client only receives, doesn't send
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        dashboard_clients[session_id].remove(websocket)
    except Exception:
        if websocket in dashboard_clients.get(session_id, []):
            dashboard_clients[session_id].remove(websocket)


# ── REST — Projects ────────────────────────────────────────────────────────


@app.post("/v1/projects")
async def create_project(req: CreateProjectRequest):
    project_id = str(uuid.uuid4())[:8]
    api_key = f"pp_{uuid.uuid4().hex[:16]}"

    project = {
        "id": project_id,
        "name": req.name,
        "api_key": api_key,
        "segments": [s.model_dump() for s in req.segments],
        "sessions": [],
        "optimal_playthrough_url": req.optimal_playthrough_url,
        "created_at": datetime.utcnow().isoformat(),
    }
    projects[project_id] = project

    return {"project_id": project_id, "api_key": api_key}


@app.get("/v1/projects/{project_id}")
async def get_project(project_id: str):
    if project_id not in projects:
        raise HTTPException(404, "Project not found")
    return projects[project_id]


# ── REST — Sessions ────────────────────────────────────────────────────────


@app.post("/v1/projects/{project_id}/sessions")
async def create_session(project_id: str, req: CreateSessionRequest):
    if project_id not in projects:
        raise HTTPException(404, "Project not found")

    session_id = str(uuid.uuid4())[:8]
    session = {
        "id": session_id,
        "project_id": project_id,
        "tester_name": req.tester_name,
        "status": "created",
        "created_at": datetime.utcnow().isoformat(),
    }
    sessions[session_id] = session
    session_events[session_id] = []
    session_emotions[session_id] = []
    projects[project_id]["sessions"].append(session_id)

    join_url = f"http://localhost:8080/game/index.html?session_id={session_id}"
    return {"session_id": session_id, "join_url": join_url}


@app.get("/v1/sessions/{session_id}")
async def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")
    return sessions[session_id]


@app.get("/v1/sessions/{session_id}/events")
async def get_session_events(session_id: str):
    if session_id not in session_events:
        raise HTTPException(404, "Session not found")
    return session_events[session_id]


@app.get("/v1/sessions/{session_id}/emotions")
async def get_session_emotions(session_id: str):
    if session_id not in session_emotions:
        raise HTTPException(404, "Session not found")
    return session_emotions[session_id]


@app.get("/v1/sessions/{session_id}/analysis")
async def get_analysis(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    events = session_events.get(session_id, [])
    emotions = session_emotions.get(session_id, [])

    # Resolve project segments
    project_id = sessions[session_id]["project_id"]
    segments = projects.get(project_id, {}).get("segments", [])

    fused = fuse_events_and_emotions(events, emotions)
    intent = compare_intent_vs_reality(fused, segments)
    stats = compute_session_stats(fused)

    return {
        "session_id": session_id,
        "fused_timeline": fused,
        "intent_comparison": intent,
        "summary_stats": stats,
    }


# ── Entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
