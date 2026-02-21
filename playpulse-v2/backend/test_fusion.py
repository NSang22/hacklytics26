"""Smoke test for fusion.py — exercises all three input paths."""
import sys
sys.path.insert(0, '.')

import random
import pandas as pd
from models import DFAConfig, DFAState, ChunkResult, ChunkStateObservation, ChunkTransition

from fusion import fuse_streams

# ── Build a 60-second mock session ───────────────────────────────────────────

# DFA with three states
dfa = DFAConfig(states=[
    DFAState(name='tutorial',  intended_emotion='calm',        acceptable_range=(0.0,  0.35), expected_duration_sec=30),
    DFAState(name='pit',       intended_emotion='tense',       acceptable_range=(0.45, 0.75), expected_duration_sec=10),
    DFAState(name='boss',      intended_emotion='frustration', acceptable_range=(0.5,  0.9),  expected_duration_sec=20),
])

# Presage: 10 Hz for 60 seconds = 600 readings (dict format with 'timestamp' key)
presage = [
    {
        "timestamp":   t / 10.0,
        "frustration": round(random.uniform(0.1, 0.4), 3),
        "confusion":   round(random.uniform(0.1, 0.3), 3),
        "delight":     round(random.uniform(0.2, 0.5), 3),
        "boredom":     round(random.uniform(0.1, 0.3), 3),
        "surprise":    round(random.uniform(0.0, 0.2), 3),
    }
    for t in range(600)
]

# Apple Watch: 1 Hz for 60 seconds (dict format with 'hrv' key from spec)
watch = [
    {
        "timestamp": float(t),
        "hr":        random.randint(68, 95),
        "hrv":       round(random.uniform(30.0, 55.0), 1),
    }
    for t in range(60)
]

# Gemini chunk results: 6 chunks of 10s each
chunk_results = [
    ChunkResult(
        chunk_index=i,
        time_range_sec=(i * 10.0, (i + 1) * 10.0),
        states_observed=[
            ChunkStateObservation(
                state_name='tutorial' if i < 3 else ('pit' if i == 3 else 'boss'),
                entered_at_sec=float(i * 10),
                exited_at_sec=float((i + 1) * 10),
                duration_sec=10.0,
                player_behavior='progressing',
                progress='normal',
            )
        ],
        transitions=[
            ChunkTransition(from_state='tutorial', to_state='pit', timestamp_sec=30.0, confidence=0.9)
        ] if i == 3 else (
            [ChunkTransition(from_state='pit', to_state='boss', timestamp_sec=40.0, confidence=0.85)] if i == 4 else []
        ),
        events=[],
        end_state='tutorial' if i < 3 else ('pit' if i == 3 else 'boss'),
        end_status='progressing',
        cumulative_deaths=0,
    )
    for i in range(6)
]

# ── Run fusion ────────────────────────────────────────────────────────────────
df = fuse_streams(
    presage_frames=presage,
    watch_readings=watch,
    chunk_results=chunk_results,
    dfa_config=dfa,
    session_id='test-session-fusion-001',
)

# ── Verify structure ──────────────────────────────────────────────────────────
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(f"\nFirst 3 rows:\n{df.head(3).to_string()}")
print(f"\nLast 3 rows:\n{df.tail(3).to_string()}")

# State distribution
print(f"\nState value counts:\n{df['state'].value_counts().to_string()}")

# Intent delta summary
print(f"\nIntent delta stats:\n{df['intent_delta'].describe().to_string()}")

# Assertions
assert df.shape == (60, 19), f"Expected (60, 19), got {df.shape}"
assert list(df.columns) == [
    "t", "session_id", "state", "time_in_state_sec",
    "frustration", "confusion", "delight", "boredom", "surprise", "engagement",
    "hr", "hrv_rmssd", "hrv_sdnn", "presage_hr", "breathing_rate", "movement_variance",
    "intent_delta", "dominant_emotion", "data_quality",
], f"Column mismatch\nGot: {list(df.columns)}"

# State transitions happened correctly
assert 'tutorial' in df['state'].values, "Expected 'tutorial' state"
assert 'pit'      in df['state'].values, "Expected 'pit' state"
assert 'boss'     in df['state'].values, "Expected 'boss' state"

# Watch HR populated (not all zero)
assert df['hr'].max() > 0, "Watch HR should not be all zero"

# Presage emotions populated
assert df['frustration'].max() > 0, "Frustration should not be all zero"

# intent_delta is non-negative
assert (df['intent_delta'] >= 0).all(), "intent_delta must be non-negative"

print("\nfusion.py PASSED ✓")
