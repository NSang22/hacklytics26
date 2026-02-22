"""
End-to-end integration test for the PatchLab pipeline.

Tests the full HTTP flow:
  1. Create project (with DFA config)
  2. Create session
  3. Upload fake video chunks (x3)
  4. POST emotion frames
  5. Finalize session
  6. GET timeline + verdicts + health score

Run with the server already started:
  uvicorn main:app --reload --port 8000

Then in another terminal:
  python test_e2e.py
"""

import io
import json
import struct
import time

import requests

BASE = "http://localhost:8000"

# ── Helpers ──────────────────────────────────────────────────────────────────

def ok(resp: requests.Response, label: str) -> dict:
    if not resp.ok:
        print(f"FAIL [{label}] {resp.status_code}: {resp.text[:400]}")
        raise SystemExit(1)
    data = resp.json()
    print(f"  OK  [{label}]")
    return data


def make_fake_mp4_bytes(size_kb: int = 64) -> bytes:
    """Return a minimal valid-looking byte sequence (won't decode — that's fine in MOCK_MODE)."""
    header = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    pad = b"\x00" * (size_kb * 1024 - len(header))
    return header + pad


# ── Step 1: Create project ────────────────────────────────────────────────────

print("\n=== Step 1: Create project ===")
project_payload = {
    "name": "E2E Test Game",
    "description": "Automated end-to-end test",
    "dfa_states": [
        {
            "name": "tutorial",
            "intended_emotion": "delight",
            "acceptable_range": [0.3, 0.9],
            "expected_duration_sec": 20,
        },
        {
            "name": "pit",
            "intended_emotion": "frustration",
            "acceptable_range": [0.4, 0.85],
            "expected_duration_sec": 20,
        },
        {
            "name": "boss",
            "intended_emotion": "engagement",
            "acceptable_range": [0.5, 1.0],
            "expected_duration_sec": 20,
        },
    ],
    "transitions": [
        {"from_state": "tutorial", "to_state": "pit",  "trigger": "enter_pit"},
        {"from_state": "pit",      "to_state": "boss", "trigger": "boss_door"},
    ],
}
r = requests.post(f"{BASE}/v1/projects", json=project_payload)
proj = ok(r, "create_project")
project_id = proj.get("project_id")
print(f"       project_id = {project_id}")

# ── Step 2: Create session ────────────────────────────────────────────────────

print("\n=== Step 2: Create session ===")
r = requests.post(f"{BASE}/v1/projects/{project_id}/sessions", json={
    "tester_name": "E2E Tester",
    "chunk_duration_sec": 10,
})
sess = ok(r, "create_session")
session_id = sess.get("session_id")
print(f"       session_id = {session_id}")

# ── Step 3: Upload fake chunks (x3) ──────────────────────────────────────────

print("\n=== Step 3: Upload 3 video chunks ===")
for chunk_idx in range(3):
    fake_bytes = make_fake_mp4_bytes(64)
    files = {"file": (f"chunk_{chunk_idx}.mp4", io.BytesIO(fake_bytes), "video/mp4")}
    data  = {"chunk_index": str(chunk_idx)}
    r = requests.post(
        f"{BASE}/v1/sessions/{session_id}/upload-chunk",
        files=files,
        data=data,
    )
    ok(r, f"upload_chunk_{chunk_idx}")

# Give background tasks a moment to complete
print("       Waiting 2s for background chunk processing...")
time.sleep(2)

# ── Step 4: POST emotion frames ───────────────────────────────────────────────

print("\n=== Step 4: Post emotion frames ===")
frames = []
for t in range(30):          # 30 seconds of mock emotion data @ 1 Hz
    frames.append({
        "timestamp_sec": float(t),
        "frustration":   round(0.3 + 0.1 * (t % 7 == 0), 4),
        "confusion":     round(0.2 + 0.05 * (t % 3 == 0), 4),
        "delight":       round(0.5 - 0.05 * (t % 5 == 0), 4),
        "boredom":       round(0.1 + 0.02 * (t % 11 == 0), 4),
        "surprise":      round(0.15 + 0.1 * (t % 9 == 0), 4),
        "engagement":    round(0.6 + 0.1 * (t % 4 == 0), 4),
    })

r = requests.post(
    f"{BASE}/v1/sessions/{session_id}/emotion-frames",
    json={"frames": frames},
)
ok(r, "post_emotion_frames")

# ── Step 5: Finalize session ──────────────────────────────────────────────────

print("\n=== Step 5: Finalize session ===")
r = requests.post(f"{BASE}/v1/sessions/{session_id}/finalize")
fin = ok(r, "finalize")
print(f"       response = {json.dumps(fin, indent=2)[:400]}")

# ── Step 6: GET results ───────────────────────────────────────────────────────

print("\n=== Step 6: Read back results ===")

r = requests.get(f"{BASE}/v1/sessions/{session_id}/timeline")
timeline_resp = ok(r, "get_timeline")
rows = timeline_resp.get("rows", [])
print(f"       timeline rows = {len(rows)}")

r = requests.get(f"{BASE}/v1/sessions/{session_id}/verdicts")
verdicts_resp = ok(r, "get_verdicts")
verdicts = verdicts_resp.get("verdicts", [])
for v in verdicts:
    name    = v.get("state_name", "?")
    verdict = v.get("verdict", "?")
    score   = round(v.get("actual_avg_score", 0), 4)
    print(f"         {name:20s}  →  {verdict:8s}  (avg={score})")

r = requests.get(f"{BASE}/v1/sessions/{session_id}/health-score")
health_resp = ok(r, "get_health")
print(f"       health_score = {health_resp.get('health_score')}")

# ── Done ──────────────────────────────────────────────────────────────────────
print("\n✓ End-to-end test PASSED\n")
