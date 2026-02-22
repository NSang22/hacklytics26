"""
PlayPulse v2 — Pydantic models.

Covers: DFA config, projects, sessions, events, emotions, verdicts, fused rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


# ── DFA State & Project Config ──────────────────────────────────────────────


class DFAState(BaseModel):
    name: str
    description: str = ""
    visual_cues: List[str] = []
    failure_indicators: List[str] = []
    success_indicators: List[str] = []
    intended_emotion: str  # frustration, confusion, delight, boredom, surprise, tense, calm, excited, satisfied, curious
    acceptable_range: Tuple[float, float] = (0.3, 0.8)
    expected_duration_sec: float = 30.0


class DFATransitionDef(BaseModel):
    from_state: str
    to_state: str
    trigger: str = ""


class DFAConfig(BaseModel):
    states: List[DFAState] = []
    transitions: List[DFATransitionDef] = []


# ── Request models ──────────────────────────────────────────────────────────


class CreateProjectRequest(BaseModel):
    name: str
    game_name: str = ""
    dfa_config: DFAConfig = DFAConfig()
    optimal_playthrough_url: Optional[str] = None


class UpdateDFARequest(BaseModel):
    dfa_config: DFAConfig


class CreateSessionRequest(BaseModel):
    tester_name: Optional[str] = None


# ── Stored entities ─────────────────────────────────────────────────────────


class Project(BaseModel):
    id: str
    name: str
    game_name: str = ""
    api_key: str
    dfa_config: DFAConfig = DFAConfig()
    optimal_playthrough_url: Optional[str] = None
    optimal_trace: Optional[Dict[str, Any]] = None
    sessions: List[str] = []
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Session(BaseModel):
    id: str
    project_id: str
    tester_name: Optional[str] = None
    status: str = "created"  # created | recording | processing | complete
    face_video_path: Optional[str] = None
    duration_sec: Optional[float] = None
    health_score: Optional[float] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ── Emotion / Biometric frames ─────────────────────────────────────────────


class EmotionFrame(BaseModel):
    timestamp_sec: float
    frustration: float = 0.0
    confusion: float = 0.0
    delight: float = 0.0
    boredom: float = 0.0
    surprise: float = 0.0
    engagement: float = 0.0
    heart_rate: float = 0.0
    breathing_rate: float = 0.0


class WatchReading(BaseModel):
    timestamp_sec: float
    heart_rate: float = 0.0
    hrv_rmssd: float = 0.0
    hrv_sdnn: float = 0.0
    movement_variance: float = 0.0


# ── Gemini chunk results ───────────────────────────────────────────────────


class ChunkStateObservation(BaseModel):
    state_name: str
    entered_at_sec: float = 0.0
    exited_at_sec: float = 0.0
    duration_sec: float = 0.0
    player_behavior: str = ""
    progress: str = "normal"  # fast | normal | slow | stuck
    matches_success_indicators: bool = False
    matches_failure_indicators: bool = False


class ChunkTransition(BaseModel):
    from_state: Optional[str] = None
    to_state: str
    timestamp_sec: float
    confidence: float = 1.0


class ChunkEvent(BaseModel):
    type: str  # death | stuck | backtrack | close_call | pause | exploration
    timestamp_sec: float
    description: str = ""
    state: str = ""


class ChunkResult(BaseModel):
    chunk_index: int
    time_range_sec: Tuple[float, float]
    states_observed: List[ChunkStateObservation] = []
    transitions: List[ChunkTransition] = []
    events: List[ChunkEvent] = []
    end_state: str = ""
    end_status: str = ""
    cumulative_deaths: int = 0
    chunk_summary: str = ""


# ── Fused timeline row ──────────────────────────────────────────────────────


class FusedRow(BaseModel):
    session_id: str = ""
    timestamp_sec: int
    current_state: str = "unknown"
    time_in_state_sec: int = 0
    frustration: float = 0.0
    confusion: float = 0.0
    delight: float = 0.0
    boredom: float = 0.0
    surprise: float = 0.0
    engagement: float = 0.0
    presage_hr: float = 0.0
    breathing_rate: float = 0.0
    watch_hr: float = 0.0
    hrv_rmssd: float = 0.0
    hrv_sdnn: float = 0.0
    movement_variance: float = 0.0
    dominant_emotion: str = ""
    hr_agreement: Optional[bool] = None
    data_quality: float = 0.0


# ── Verdict (per DFA state) ────────────────────────────────────────────────


class StateVerdict(BaseModel):
    state_name: str
    intended_emotion: str
    acceptable_range: Tuple[float, float] = (0.0, 1.0)
    actual_avg_score: float = 0.0
    actual_dominant_emotion: str = ""
    actual_distribution: Dict[str, float] = {}
    actual_duration_sec: float = 0.0
    expected_duration_sec: float = 0.0
    time_delta_sec: float = 0.0
    intent_met: bool = False
    deviation_score: float = 0.0
    verdict: str = "NO_DATA"  # PASS | WARN | FAIL | NO_DATA
