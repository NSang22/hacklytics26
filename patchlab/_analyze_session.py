#!/usr/bin/env python3
"""Quick analysis of session 14749b21 fallback data."""
import json

with open("patchlab/backend/vectorai_fallback.json") as f:
    data = json.load(f)

session_chunks = [d for d in data if d.get("metadata", {}).get("session_id") == "14749b21"]
print(f"Total chunks for session 14749b21: {len(session_chunks)}")
print()

states = {}
for c in session_chunks:
    m = c["metadata"]
    st = m.get("dfa_state", "unknown")
    ws = m.get("window_start_sec", 0)
    we = m.get("window_end_sec", 0)
    if st not in states:
        states[st] = {"count": 0, "min_start": ws, "max_end": we, "frustration": [], "dominant": []}
    states[st]["count"] += 1
    states[st]["min_start"] = min(states[st]["min_start"], ws)
    states[st]["max_end"] = max(states[st]["max_end"], we)
    states[st]["frustration"].append(m.get("frustration_score", 0))
    states[st]["dominant"].append(m.get("dominant_emotion", ""))

for st, info in sorted(states.items(), key=lambda x: x[1]["min_start"]):
    avg_frust = sum(info["frustration"]) / len(info["frustration"])
    dom_counts = {}
    for d in info["dominant"]:
        dom_counts[d] = dom_counts.get(d, 0) + 1
    print(f"State: {st}")
    print(f"  Chunks: {info['count']}")
    print(f"  Time: {info['min_start']}s - {info['max_end']}s")
    print(f"  Avg frustration: {avg_frust:.4f}")
    print(f"  Dominant emotions: {dom_counts}")
    print()

# Also show the full vector breakdown for a few interesting chunks
print("=" * 60)
print("Sample vectors (first, middle, last chunk):")
print("=" * 60)
indices = [0, len(session_chunks)//2, -1]
for i in indices:
    c = session_chunks[i]
    m = c["metadata"]
    print(f"\n  Chunk {c['id']}  (state={m.get('dfa_state')}, {m.get('window_start_sec')}-{m.get('window_end_sec')}s)")
    print(f"  Vector: {c['vector']}")
    print(f"  Dominant: {m.get('dominant_emotion')}  Frustration: {m.get('frustration_score')}  Confusion: {m.get('confusion_score')}")
