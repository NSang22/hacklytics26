"""Smoke test for snowflake_writer.py in MOCK_MODE."""
import sys
sys.path.insert(0, '.')

import random
import pandas as pd
from models import DFAConfig, DFAState, ChunkResult, ChunkStateObservation, ChunkTransition
from fusion import fuse_streams
from snowflake_writer import write_all, _build_state_verdicts, _compute_playtest_health_score

# ── Build the same 60s mock session as test_fusion.py ────────────────────────

dfa = DFAConfig(states=[
    DFAState(name='tutorial',  intended_emotion='calm',        acceptable_range=(0.0,  0.35), expected_duration_sec=30),
    DFAState(name='pit',       intended_emotion='tense',       acceptable_range=(0.45, 0.75), expected_duration_sec=10),
    DFAState(name='boss',      intended_emotion='frustration', acceptable_range=(0.5,  0.9),  expected_duration_sec=20),
])

emotion_frames = [
    {"timestamp": t / 10.0, "frustration": round(random.uniform(0.1, 0.4), 3),
     "confusion": round(random.uniform(0.1, 0.3), 3), "delight": round(random.uniform(0.2, 0.5), 3),
     "boredom": round(random.uniform(0.1, 0.3), 3), "surprise": round(random.uniform(0.0, 0.2), 3)}
    for t in range(600)
]
watch = [{"timestamp": float(t), "hr": random.randint(68, 95), "hrv": round(random.uniform(30.0, 55.0), 1)}
         for t in range(60)]
chunk_results = [
    ChunkResult(
        chunk_index=i, time_range_sec=(i*10.0, (i+1)*10.0),
        states_observed=[ChunkStateObservation(
            state_name='tutorial' if i < 3 else ('pit' if i == 3 else 'boss'),
            entered_at_sec=float(i*10), exited_at_sec=float((i+1)*10), duration_sec=10.0,
            player_behavior='progressing', progress='normal')],
        transitions=(
            [ChunkTransition(from_state='tutorial', to_state='pit', timestamp_sec=30.0, confidence=0.9)] if i == 3 else
            ([ChunkTransition(from_state='pit', to_state='boss', timestamp_sec=40.0, confidence=0.85)] if i == 4 else [])
        ),
        events=[], end_state='tutorial' if i < 3 else ('pit' if i == 3 else 'boss'),
        end_status='progressing', cumulative_deaths=0,
    )
    for i in range(6)
]

fused_df = fuse_streams(
    emotion_frames=emotion_frames, watch_readings=watch,
    chunk_results=chunk_results, dfa_config=dfa,
    session_id='test-snf-001',
)

# ── Test write_all in MOCK_MODE (no real Snowflake calls) ─────────────────────
result = write_all(
    session_id='test-snf-001',
    project_id='proj-001',
    emotion_frames=emotion_frames,
    watch_readings=watch,
    chunk_results=chunk_results,
    fused_df=fused_df,
    dfa_config=dfa,
)

print("Gold result:")
print(f"  session_id   : {result['session_id']}")
print(f"  health_score : {result['health_score']}")
print(f"  state_verdicts:")
for v in result['state_verdicts']:
    print(f"    {v['state_name']:<12} intended={v['intended_emotion']:<12} "
          f"actual_avg={v['actual_avg_score']:.3f}  "
          f"delta={v['intent_delta_avg']:.3f}  "
          f"duration={v['actual_duration_sec']}s/{v['expected_duration_sec']}s  "
          f"verdict={v['verdict']}")

# ── Assertions ────────────────────────────────────────────────────────────────
assert "session_id"     in result
assert "health_score"   in result
assert "state_verdicts" in result
assert 0.0 <= result["health_score"] <= 100.0, "Health score out of range"

for v in result["state_verdicts"]:
    assert v["verdict"] in ("PASS", "WARN", "FAIL", "NO_DATA"), f"Bad verdict: {v['verdict']}"
    assert v["actual_duration_sec"] > 0
    assert v["intent_delta_avg"] >= 0

print("\nsnowflake_writer.py PASSED ✓")
