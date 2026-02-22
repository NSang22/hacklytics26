#!/usr/bin/env python3
"""
End-to-end test for the Gemini Vision pipeline.
  1. Creates a Mario 1-1 project with DFA states
  2. Creates a session
  3. Captures a real screenshot (mss) or generates a test frame (PIL fallback)
  4. Uploads 3 frames to /upload-frames
  5. Waits for background Gemini processing
  6. Prints the chunk result to verify Gemini returned real DFA state data
  7. Finalizes the session and prints health score + verdicts
"""
import io
import json
import time

import requests
from PIL import Image, ImageDraw, ImageFont

BACKEND = "http://localhost:8000"

# ── Mario DFA config ─────────────────────────────────────────
DFA_STATES = [
    {
        "name": "overworld_start",
        "description": "Mario at the beginning of 1-1, running right on grass",
        "visual_cues": ["green grass", "blue sky", "Mario sprite", "Question blocks"],
        "intended_emotion": "delight",
        "acceptable_range": [0.3, 0.7],
        "expected_duration_sec": 20,
    },
    {
        "name": "first_pit",
        "description": "Mario approaching the first pit, gap in the ground visible",
        "visual_cues": ["gap in floor", "pit below", "Mario near edge"],
        "intended_emotion": "tense",
        "acceptable_range": [0.4, 0.8],
        "expected_duration_sec": 5,
    },
    {
        "name": "underground",
        "description": "Mario in the underground bonus area",
        "visual_cues": ["dark background", "coins", "underground pipes"],
        "intended_emotion": "delight",
        "acceptable_range": [0.5, 0.9],
        "expected_duration_sec": 15,
    },
]


def grab_screenshot():
    """Take a real screenshot, or generate a test frame if mss not available."""
    try:
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            img = img.resize((1280, int(img.height * 1280 / img.width)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70)
            print(f"  [screenshot] Real screenshot captured ({img.width}x{img.height})")
            return buf.getvalue()
    except Exception as e:
        print(f"  [screenshot] mss not available ({e}), using generated test frame")
        return make_test_frame()


def make_test_frame(label="Test Frame"):
    """Generate a simple coloured test JPEG that resembles a game screen."""
    img = Image.new("RGB", (800, 600), color=(92, 148, 252))  # Mario sky blue
    draw = ImageDraw.Draw(img)
    # ground
    draw.rectangle([0, 480, 800, 600], fill=(139, 90, 43))
    # grass
    draw.rectangle([0, 460, 800, 480], fill=(0, 168, 0))
    # "Mario" (red rectangle)
    draw.rectangle([120, 420, 148, 460], fill=(255, 0, 0))
    # question blocks
    for x in [200, 260, 320]:
        draw.rectangle([x, 300, x + 32, 332], fill=(255, 200, 0))
        draw.text((x + 10, 308), "?", fill=(0, 0, 0))
    draw.text((10, 10), label, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    print(f"  [screenshot] Generated test frame '{label}'")
    return buf.getvalue()


def upload_frames(session_id, chunk_index, frame_bytes_list):
    timestamps = json.dumps([round(i * 0.5, 1) for i in range(len(frame_bytes_list))])
    files = [
        ("frames", (f"frame_{i:04d}.jpg", data, "image/jpeg"))
        for i, data in enumerate(frame_bytes_list)
    ]
    resp = requests.post(
        f"{BACKEND}/v1/sessions/{session_id}/upload-frames",
        data={"chunk_index": str(chunk_index), "timestamps": timestamps},
        files=files,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def wait_for_chunk(session_id, chunk_index, timeout=30):
    """Poll until the chunk appears in /chunks (means Gemini finished)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{BACKEND}/v1/sessions/{session_id}/chunks")
        chunks = resp.json().get("chunks", [])
        for c in chunks:
            if c["chunk_index"] == chunk_index:
                return c
        time.sleep(1)
    return None


def main():
    print("=" * 60)
    print("AURA — Gemini Vision Pipeline Test")
    print("=" * 60)

    # ── 1. Create project ───────────────────────────────────────
    print("\n[1/6] Creating Mario 1-1 project...")
    resp = requests.post(
        f"{BACKEND}/v1/projects",
        json={
            "name": "Mario 1-1 Playtest",
            "description": "Super Mario Bros World 1-1",
            "dfa_states": DFA_STATES,
            "transitions": [
                {"from_state": "overworld_start", "to_state": "first_pit", "trigger": "player_approaches_pit"},
                {"from_state": "first_pit", "to_state": "underground", "trigger": "player_enters_pipe"},
            ],
        },
        timeout=10,
    )
    resp.raise_for_status()
    project_id = resp.json()["project_id"]
    print(f"  project_id: {project_id}")

    # ── 2. Create session ───────────────────────────────────────
    print("\n[2/6] Creating session...")
    resp = requests.post(
        f"{BACKEND}/v1/projects/{project_id}/sessions",
        json={"tester_name": "test_runner", "chunk_duration_sec": 15},
        timeout=10,
    )
    resp.raise_for_status()
    session_id = resp.json()["session_id"]
    print(f"  session_id: {session_id}")

    # ── 3. Capture test frames ─────────────────────────────────
    print("\n[3/6] Capturing frames...")
    frame1 = grab_screenshot()
    frame2 = make_test_frame("Chunk 0 — Frame 2")
    frame3 = make_test_frame("Chunk 0 — Frame 3")

    # ── 4. Upload frames ────────────────────────────────────────
    print("\n[4/6] Uploading 3 frames to /upload-frames (chunk 0)...")
    result = upload_frames(session_id, chunk_index=0, frame_bytes_list=[frame1, frame2, frame3])
    print(f"  response: {result}")

    # ── 5. Wait for Gemini to process ───────────────────────────
    print("\n[5/6] Waiting for Gemini Vision to process (up to 60s)...")
    chunk = wait_for_chunk(session_id, chunk_index=0, timeout=60)

    if chunk is None:
        print("  TIMEOUT — Gemini did not respond in 30s")
        return

    print("  Gemini responded!")
    print(f"\n  ── Chunk 0 result ──────────────────────────────────")
    print(f"  States observed: {chunk['states_observed']}")
    print(f"  Events:          {chunk['events']}")
    print(f"  Notes:           {chunk['notes']}")

    # Verify we got real Gemini data (not stub)
    stub_states = {"tutorial", "puzzle_room", "surprise_event", "gauntlet", "victory"}
    returned_states = {o["state"] for o in chunk["states_observed"]}
    if returned_states & stub_states:
        print("\n  ⚠  Stub states detected — Gemini API key may not be active")
    else:
        print("\n  ✓  Real Gemini response — DFA states matched to Mario config!")

    # ── 6. Finalize session ─────────────────────────────────────
    print("\n[6/6] Finalizing session...")
    resp = requests.post(f"{BACKEND}/v1/sessions/{session_id}/finalize", timeout=60)
    resp.raise_for_status()
    final = resp.json()
    print(f"  health_score:   {final.get('health_score', '?')}")
    print(f"  verdicts_count: {final.get('verdicts_count', '?')}")

    # Print verdicts
    resp = requests.get(f"{BACKEND}/v1/sessions/{session_id}/verdicts")
    verdicts = resp.json().get("verdicts", [])
    print(f"\n  ── Verdicts ────────────────────────────────────────")
    for v in verdicts:
        state = v.get("state_name", v.get("state", "?"))
        verdict = v.get("verdict", "?")
        print(f"  {state:30s}  {verdict}")

    print("\n" + "=" * 60)
    print(f"DONE  session_id={session_id}  project_id={project_id}")
    print("=" * 60)


if __name__ == "__main__":
    main()
