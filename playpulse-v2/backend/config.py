"""
Crashout — Shared configuration.

Single place to flip MOCK_MODE and load all environment variables.
Set MOCK_MODE = True during development to avoid burning API quotas.
Set MOCK_MODE = False when you're ready to go live with real Gemini calls.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env — try backend/.env first, then repo root ───────────────────────
_BACKEND_DIR = Path(__file__).resolve().parent           # playpulse-v2/backend/
_ROOT = _BACKEND_DIR.parents[1]                          # hacklytics26/
load_dotenv(_BACKEND_DIR / ".env", override=False)       # backend/.env (primary)
load_dotenv(_ROOT / ".env", override=False)              # repo root fallback

# ── Master mock switch ────────────────────────────────────────────────────────
# Flip to False when you're ready to use real Gemini / Snowflake / VectorAI
MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() in ("true", "1", "yes")

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_CHUNK: str = "gemini-2.5-flash"
GEMINI_MODEL_INSIGHT: str = "gemini-2.5-flash"
CHUNK_FPS: int = int(os.getenv("CHUNK_FPS", "2"))   # frames per second to sample

# ── Snowflake ─────────────────────────────────────────────────────────────────
SNOWFLAKE_ACCOUNT: str = os.getenv("SNOWFLAKE_ACCOUNT", "")
SNOWFLAKE_USER: str = os.getenv("SNOWFLAKE_USER", "")
SNOWFLAKE_PASSWORD: str = os.getenv("SNOWFLAKE_PASSWORD", "")
SNOWFLAKE_WAREHOUSE: str = os.getenv("SNOWFLAKE_WAREHOUSE", "CRASHOUT_WH")
SNOWFLAKE_DATABASE: str = os.getenv("SNOWFLAKE_DATABASE", "CRASHOUT_DB")
SNOWFLAKE_SCHEMA: str = os.getenv("SNOWFLAKE_SCHEMA", "CRASHOUT_SCHEMA")

# ── VectorAI ──────────────────────────────────────────────────────────────────
VECTORAI_URL: str = os.getenv("VECTORAI_URL", "")
VECTORAI_API_KEY: str = os.getenv("VECTORAI_API_KEY", "")
VECTORAI_COLLECTION: str = os.getenv("VECTORAI_COLLECTION", "crashout_embeddings")

# ── Pipeline tuning ───────────────────────────────────────────────────────────
CHUNK_DURATION_SEC: float = float(os.getenv("CHUNK_DURATION_SEC", "10"))
FUSION_RESAMPLE_HZ: int = int(os.getenv("FUSION_RESAMPLE_HZ", "1"))
EMBEDDING_WINDOW_SEC: int = int(os.getenv("EMBEDDING_WINDOW_SEC", "10"))

# ── Verdict thresholds ────────────────────────────────────────────────────────
WARN_DELTA_THRESHOLD: float = 0.25   # delta >= this -> FAIL, else WARN

# ── Emotion name → measured column mapping ───────────────────────────────────
# Maps DFA intended_emotion strings to actual Presage DataFrame column names.
EMOTION_COLUMN_MAP: dict = {
    "frustration": "frustration",
    "confusion":   "confusion",
    "delight":     "delight",
    "boredom":     "boredom",
    "surprise":    "surprise",
    "engagement":  "engagement",
    "tense":       "frustration",
    "calm":        "frustration",
    "excited":     "delight",
    "satisfied":   "delight",
    "curious":     "confusion",
    "angry":       "frustration",
    "scared":      "surprise",
}
