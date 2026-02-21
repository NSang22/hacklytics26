"""Pydantic models for PlayPulse backend."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Request models ──────────────────────────────────────────────────────────


class SegmentDefinition(BaseModel):
    name: str
    intended_emotion: str
    order: int


class CreateProjectRequest(BaseModel):
    name: str
    segments: List[SegmentDefinition] = []
    optimal_playthrough_url: Optional[str] = None


class CreateSessionRequest(BaseModel):
    project_id: str
    tester_name: Optional[str] = None


# ── Event / Emotion schemas ────────────────────────────────────────────────


class GameEvent(BaseModel):
    session_id: str
    event_type: str  # session_start | session_end | game_event | player_action | state_change | milestone | metric
    event_name: str
    timestamp: float  # seconds since session start
    payload: Dict[str, Any] = {}
    received_at: Optional[str] = None


class EmotionFrame(BaseModel):
    timestamp: float
    emotions: Dict[str, float] = {}  # frustration, confusion, delight, surprise, boredom …
    heart_rate: Optional[float] = None
    breathing_rate: Optional[float] = None
    engagement: Optional[float] = None
    gaze: Optional[Dict[str, float]] = None  # {"x": 0.5, "y": 0.3}


# ── Stored entities ────────────────────────────────────────────────────────


class Project(BaseModel):
    id: str
    name: str
    api_key: str
    segments: List[SegmentDefinition] = []
    sessions: List[str] = []
    optimal_playthrough_url: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Session(BaseModel):
    id: str
    project_id: str
    tester_name: Optional[str] = None
    status: str = "created"  # created | active | completed
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ── Analysis response models ───────────────────────────────────────────────


class FusedEntry(BaseModel):
    timestamp: float
    event: Dict[str, Any]
    emotion: Dict[str, Any] = {}
    contextualized: str = ""


class IntentComparison(BaseModel):
    segment: str
    intended: str
    actual_dominant: Optional[str] = None
    actual_distribution: Dict[str, float] = {}
    intent_met: Optional[bool] = None
    deviation_score: Optional[float] = None


class AnalysisResponse(BaseModel):
    session_id: str
    fused_timeline: List[FusedEntry] = []
    intent_comparison: List[IntentComparison] = []
    summary_stats: Dict[str, Any] = {}
