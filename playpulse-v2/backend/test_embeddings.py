"""Smoke test for embeddings.py in MOCK_MODE."""
import sys
sys.path.insert(0, '.')

import random
import numpy as np
from models import DFAConfig, DFAState, ChunkResult, ChunkStateObservation, ChunkTransition
from fusion import fuse_streams
from embeddings import embed_and_store, similarity_search, _build_windows, _serialize_window, _mock_embed_texts

# ── Build same 60s mock session ───────────────────────────────────────────────
dfa = DFAConfig(states=[
    DFAState(name='tutorial',  intended_emotion='calm',        acceptable_range=(0.0,  0.35), expected_duration_sec=30),
    DFAState(name='pit',       intended_emotion='tense',       acceptable_range=(0.45, 0.75), expected_duration_sec=10),
    DFAState(name='boss',      intended_emotion='frustration', acceptable_range=(0.5,  0.9),  expected_duration_sec=20),
])
presage = [
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
    presage_frames=presage, watch_readings=watch,
    chunk_results=chunk_results, dfa_config=dfa,
    session_id='test-emb-001',
)

# ── Test window building ───────────────────────────────────────────────────────
windows = _build_windows(fused_df, window_sec=10)
print(f"Windows built: {len(windows)} (expected 6 for 60s / 10s)")
print(f"\nSample window texts:")
for w in windows:
    print(f"  [{w['meta']['t_start']:02d}-{w['meta']['t_end']:02d}s] {w['text']}")

# ── Test mock embeddings shape ─────────────────────────────────────────────────
texts = [w["text"] for w in windows]
vecs = _mock_embed_texts(texts)
print(f"\nMock embedding shape: {vecs.shape}  (expected ({len(windows)}, 1024))")
norms = np.linalg.norm(vecs, axis=1)
print(f"Vector norms: min={norms.min():.4f} max={norms.max():.4f}  (should all be ~1.0)")

# ── Test full embed_and_store in MOCK_MODE (no model load, no VectorAI) ────────
count = embed_and_store(
    session_id='test-emb-001',
    project_id='proj-001',
    fused_df=fused_df,
)
print(f"\nembed_and_store returned: {count} windows")

# ── Test similarity_search in MOCK_MODE ────────────────────────────────────────
results = similarity_search("frustration in pit state", top_k=3)
print(f"\nsimilarity_search results: {len(results)}")
for r in results:
    print(f"  score={r['score']}  session={r['session_id']}  state={r['state']}")

# ── Assertions ─────────────────────────────────────────────────────────────────
assert len(windows) == 6, f"Expected 6 windows, got {len(windows)}"
assert vecs.shape == (6, 1024), f"Expected (6, 1024), got {vecs.shape}"
assert all(abs(n - 1.0) < 1e-5 for n in norms), "Vectors not unit-normalized"
assert count == 6, f"Expected 6 stored, got {count}"
assert len(results) > 0
for w in windows:
    assert "|" in w["text"], "Text format malformed"
    assert w["text"].startswith("state:"), "Text should start with 'state:'"
    assert "intent_delta:" in w["text"]

print("\nembeddings.py PASSED ✓")
