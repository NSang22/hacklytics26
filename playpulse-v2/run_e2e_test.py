"""
Full E2E test — simulates a Mario 1-1 playtest session.

1. Creates project with 5 DFA states
2. Creates session
3. Generates synthetic 10s video chunks (colored frames w/ state text)
4. Uploads chunks → triggers Gemini processing
5. Sends emotion frames (simulated Presage)
6. Sends watch data (simulated Apple Watch)
7. Finalizes session → fusion + verdicts + health score
8. Reads back all results

Run:  python run_e2e_test.py
"""

import time
import json
import random
import tempfile
import requests
import numpy as np

API = "http://localhost:8000"
NUM_CHUNKS = 6  # ~60 seconds of gameplay

# ── Helpers ──────────────────────────────────────────────────

def make_test_video(chunk_index: int, duration_sec: float = 10.0, fps: int = 3) -> bytes:
    """Create a small .mp4 with colored frames + overlaid state text.
    Uses OpenCV — produces a valid video the backend can process.
    """
    import cv2
    
    states = ["Spawn_Area", "First_Pit", "Underground_Bonus", "Platforming_Run", "Flagpole"]
    # Simulate progression: each chunk is ~10s, map to states
    state_idx = min(chunk_index, len(states) - 1)
    state_name = states[state_idx]
    
    colors = {
        "Spawn_Area": (60, 180, 75),
        "First_Pit": (200, 60, 60),
        "Underground_Bonus": (40, 40, 140),
        "Platforming_Run": (180, 130, 40),
        "Flagpole": (60, 200, 200),
    }
    color = colors.get(state_name, (128, 128, 128))
    
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(tmp_path, fourcc, fps, (320, 240))
    
    n_frames = int(duration_sec * fps)
    for f in range(n_frames):
        frame = np.full((240, 320, 3), color, dtype=np.uint8)
        # Add some variation
        noise = np.random.randint(-20, 20, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        # Overlay text
        cv2.putText(frame, f"State: {state_name}", (10, 30),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"Chunk {chunk_index} | Frame {f}/{n_frames}",
                     (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, f"Mario 1-1 Playtest", (10, 220),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        writer.write(frame)
    
    writer.release()
    
    with open(tmp_path, "rb") as f:
        data = f.read()
    
    import os
    os.unlink(tmp_path)
    return data


def generate_emotion_frames(duration_sec: int) -> list:
    """Simulate Presage emotion data at ~10 Hz."""
    frames = []
    states_by_time = [
        (0, 15, "delight_zone"),     # Spawn: happy
        (15, 25, "tense_zone"),      # First Pit: tense/frustrated
        (25, 45, "delight_zone"),    # Underground: happy collecting coins
        (45, 75, "excited_zone"),    # Platforming: excited but some frustration
        (75, 90, "victory_zone"),    # Flagpole: pure delight
    ]
    
    t = 0.0
    while t < duration_sec:
        # Determine zone
        zone = "neutral"
        for start, end, z in states_by_time:
            if start <= t < end:
                zone = z
                break
        
        if zone == "delight_zone":
            frame = {
                "timestamp_sec": round(t, 2),
                "frustration": round(random.uniform(0.05, 0.15), 3),
                "confusion": round(random.uniform(0.02, 0.10), 3),
                "delight": round(random.uniform(0.55, 0.85), 3),
                "boredom": round(random.uniform(0.01, 0.08), 3),
                "surprise": round(random.uniform(0.05, 0.20), 3),
                "engagement": round(random.uniform(0.60, 0.90), 3),
            }
        elif zone == "tense_zone":
            # First pit — high frustration spike (the famous design flaw!)
            frame = {
                "timestamp_sec": round(t, 2),
                "frustration": round(random.uniform(0.55, 0.85), 3),  # WAY above tense range
                "confusion": round(random.uniform(0.30, 0.60), 3),
                "delight": round(random.uniform(0.05, 0.15), 3),
                "boredom": round(random.uniform(0.01, 0.05), 3),
                "surprise": round(random.uniform(0.20, 0.45), 3),
                "engagement": round(random.uniform(0.40, 0.65), 3),
            }
        elif zone == "excited_zone":
            frame = {
                "timestamp_sec": round(t, 2),
                "frustration": round(random.uniform(0.15, 0.35), 3),
                "confusion": round(random.uniform(0.05, 0.20), 3),
                "delight": round(random.uniform(0.40, 0.70), 3),
                "boredom": round(random.uniform(0.02, 0.08), 3),
                "surprise": round(random.uniform(0.10, 0.30), 3),
                "engagement": round(random.uniform(0.55, 0.85), 3),
            }
        elif zone == "victory_zone":
            frame = {
                "timestamp_sec": round(t, 2),
                "frustration": round(random.uniform(0.02, 0.08), 3),
                "confusion": round(random.uniform(0.01, 0.05), 3),
                "delight": round(random.uniform(0.75, 0.95), 3),
                "boredom": round(random.uniform(0.01, 0.03), 3),
                "surprise": round(random.uniform(0.15, 0.35), 3),
                "engagement": round(random.uniform(0.80, 0.95), 3),
            }
        else:
            frame = {
                "timestamp_sec": round(t, 2),
                "frustration": round(random.uniform(0.10, 0.25), 3),
                "confusion": round(random.uniform(0.05, 0.15), 3),
                "delight": round(random.uniform(0.30, 0.50), 3),
                "boredom": round(random.uniform(0.05, 0.15), 3),
                "surprise": round(random.uniform(0.05, 0.15), 3),
                "engagement": round(random.uniform(0.40, 0.60), 3),
            }
        
        frames.append(frame)
        t += 0.1  # 10 Hz
    
    return frames


def generate_watch_data(duration_sec: int) -> list:
    """Simulate Apple Watch HR/HRV at 1 Hz."""
    readings = []
    for t in range(duration_sec):
        # HR varies by game state
        if t < 15:
            hr = random.uniform(72, 82)   # Spawn: calm
            hrv = random.uniform(45, 60)
        elif t < 25:
            hr = random.uniform(95, 115)  # First Pit: spike!
            hrv = random.uniform(20, 35)
        elif t < 45:
            hr = random.uniform(75, 88)   # Underground: slightly elevated
            hrv = random.uniform(40, 55)
        elif t < 75:
            hr = random.uniform(88, 105)  # Platforming: high
            hrv = random.uniform(28, 42)
        else:
            hr = random.uniform(78, 90)   # Flagpole: recovering
            hrv = random.uniform(38, 50)
        
        readings.append({
            "timestamp_sec": float(t),
            "heart_rate": round(hr, 1),
            "hrv_rmssd": round(hrv, 1),
            "hrv_sdnn": round(hrv * 0.8, 1),
            "movement_variance": round(random.uniform(0, 0.3), 3),
        })
    return readings


# ── Main E2E ──────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  PlayPulse v2 — Full E2E Test (Mario 1-1)")
    print("=" * 60)
    
    # 1. Check backend
    print("\n[1/8] Checking backend...")
    r = requests.get(f"{API}/")
    info = r.json()
    print(f"  ✓ Backend running: {info['service']} v{info['version']}")
    
    # 2. Create project
    print("\n[2/8] Creating Mario 1-1 project with 5 DFA states...")
    proj_body = {
        "name": "Super Mario Bros 1-1",
        "description": "NES Mario World 1-1 playtest — E2E test",
        "dfa_states": [
            {"name": "Spawn_Area", "description": "Flat ground, goombas walking",
             "intended_emotion": "delight", "acceptable_range": [0.3, 0.8],
             "expected_duration_sec": 15,
             "visual_cues": ["flat ground", "goomba", "question blocks"],
             "failure_indicators": ["death by goomba"],
             "success_indicators": ["collected mushroom"]},
            {"name": "First_Pit", "description": "First gap in ground — pit mechanics untaught",
             "intended_emotion": "tense", "acceptable_range": [0.2, 0.6],
             "expected_duration_sec": 10,
             "visual_cues": ["gap in ground", "sky visible below"],
             "failure_indicators": ["fell into pit", "death"],
             "success_indicators": ["jumped over pit"]},
            {"name": "Underground_Bonus", "description": "Underground coin room via pipe",
             "intended_emotion": "delight", "acceptable_range": [0.5, 0.9],
             "expected_duration_sec": 20,
             "visual_cues": ["underground", "rows of coins"],
             "failure_indicators": ["missed pipe"],
             "success_indicators": ["collected coins"]},
            {"name": "Platforming_Run", "description": "Main platforming section",
             "intended_emotion": "excited", "acceptable_range": [0.3, 0.8],
             "expected_duration_sec": 30,
             "visual_cues": ["pipes", "koopa troopas", "elevated platforms"],
             "failure_indicators": ["repeated deaths", "stuck"],
             "success_indicators": ["smooth progression"]},
            {"name": "Flagpole", "description": "End of level flagpole",
             "intended_emotion": "delight", "acceptable_range": [0.6, 1.0],
             "expected_duration_sec": 10,
             "visual_cues": ["staircase", "flagpole", "castle"],
             "failure_indicators": ["low flag grab"],
             "success_indicators": ["top of flagpole grab"]},
        ],
        "transitions": [
            {"from_state": "Spawn_Area", "to_state": "First_Pit", "trigger": "reaches gap"},
            {"from_state": "First_Pit", "to_state": "Underground_Bonus", "trigger": "enters pipe"},
            {"from_state": "First_Pit", "to_state": "Platforming_Run", "trigger": "clears pit"},
            {"from_state": "Underground_Bonus", "to_state": "Platforming_Run", "trigger": "exits underground"},
            {"from_state": "Platforming_Run", "to_state": "Flagpole", "trigger": "reaches staircase"},
        ],
    }
    r = requests.post(f"{API}/v1/projects", json=proj_body)
    proj = r.json()
    PROJECT_ID = proj["project_id"]
    print(f"  ✓ Project created: {PROJECT_ID}")
    
    # Verify
    r = requests.get(f"{API}/v1/projects/{PROJECT_ID}")
    p = r.json()
    for s in p["dfa_config"]["states"]:
        print(f"    {s['name']} → {s['intended_emotion']} [{s['acceptable_range']}]")
    
    # 3. Create session
    print("\n[3/8] Creating playtest session...")
    r = requests.post(f"{API}/v1/projects/{PROJECT_ID}/sessions",
                       json={"tester_name": "mario_e2e_tester", "chunk_duration_sec": 10})
    sess = r.json()
    SESSION_ID = sess["session_id"]
    print(f"  ✓ Session created: {SESSION_ID}")
    
    # 4. Upload video chunks
    print(f"\n[4/8] Generating & uploading {NUM_CHUNKS} video chunks (10s each)...")
    for i in range(NUM_CHUNKS):
        print(f"  Generating chunk {i}...", end=" ", flush=True)
        video_bytes = make_test_video(i, duration_sec=10.0, fps=3)
        print(f"({len(video_bytes)} bytes)", end=" ", flush=True)
        
        files = {"file": (f"chunk_{i}.mp4", video_bytes, "video/mp4")}
        data = {"chunk_index": str(i)}
        r = requests.post(f"{API}/v1/sessions/{SESSION_ID}/upload-chunk",
                           files=files, data=data)
        result = r.json()
        print(f"→ {result.get('status', 'error')}")
    
    # Wait for background Gemini processing
    print("\n  Waiting for chunk processing (Gemini)...", end="", flush=True)
    for _ in range(30):
        time.sleep(2)
        r = requests.get(f"{API}/v1/sessions/{SESSION_ID}/status")
        status = r.json()
        processed = status.get("chunks_processed", 0)
        print(f" [{processed}/{NUM_CHUNKS}]", end="", flush=True)
        if processed >= NUM_CHUNKS:
            break
    print(" ✓")
    
    # 5. Upload emotion frames
    print("\n[5/8] Uploading simulated emotion frames (Presage @ 10 Hz)...")
    emotion_frames = generate_emotion_frames(NUM_CHUNKS * 10)
    # Send in batches of 100
    batch_size = 100
    for start in range(0, len(emotion_frames), batch_size):
        batch = emotion_frames[start:start+batch_size]
        r = requests.post(f"{API}/v1/sessions/{SESSION_ID}/emotion-frames",
                           json={"frames": batch})
    print(f"  ✓ Sent {len(emotion_frames)} emotion frames")
    
    # 6. Upload watch data
    print("\n[6/8] Uploading simulated Apple Watch data (HR/HRV @ 1 Hz)...")
    watch_readings = generate_watch_data(NUM_CHUNKS * 10)
    for reading in watch_readings:
        requests.post(f"{API}/v1/sessions/{SESSION_ID}/watch-data", json=reading)
    print(f"  ✓ Sent {len(watch_readings)} watch readings")
    
    # 7. Finalize session
    print("\n[7/8] Finalizing session (fusion → verdicts → health score → insights)...")
    r = requests.post(f"{API}/v1/sessions/{SESSION_ID}/finalize")
    final = r.json()
    print(f"  ✓ Status: {final.get('status')}")
    print(f"  ✓ Health Score: {final.get('health_score')}")
    print(f"  ✓ Verdicts: {final.get('verdicts_count')}")
    
    # 8. Read back all results
    print("\n[8/8] Reading results...")
    
    # Health score
    r = requests.get(f"{API}/v1/sessions/{SESSION_ID}/health-score")
    hs = r.json()
    print(f"\n  ╔══════════════════════════════════════════╗")
    print(f"  ║  PLAYTEST HEALTH SCORE: {hs['health_score']:.4f}           ║")
    health = hs['health_score']
    if health >= 0.7:
        label = "GREEN ✓"
    elif health >= 0.5:
        label = "YELLOW ⚠"
    else:
        label = "RED ✗"
    print(f"  ║  Rating: {label:33s}║")
    print(f"  ╚══════════════════════════════════════════╝")
    
    # Verdicts
    r = requests.get(f"{API}/v1/sessions/{SESSION_ID}/verdicts")
    vds = r.json()
    print(f"\n  Per-State Verdicts:")
    print(f"  {'State':<22} {'Verdict':<8} {'Intended':<12} {'Actual':<8} {'Deviation':<10}")
    print(f"  {'─'*60}")
    for v in vds["verdicts"]:
        emoji = "✓" if v["verdict"] == "PASS" else ("⚠" if v["verdict"] == "WARN" else "✗")
        print(f"  {v['state_name']:<22} {emoji} {v['verdict']:<6} {v['intended_emotion']:<12} {v.get('actual_avg_score',0):.3f}    {v.get('deviation_score',0):.3f}")
    
    # Timeline sample
    r = requests.get(f"{API}/v1/sessions/{SESSION_ID}/timeline")
    tl = r.json()
    rows = tl.get("rows", [])
    print(f"\n  Fused Timeline: {len(rows)} rows (1 Hz)")
    if rows:
        print(f"  Sample (first 5 seconds):")
        for row in rows[:5]:
            print(f"    t={row.get('timestamp_sec',0):3d}s | state={row.get('current_state','?'):20s} | "
                  f"frust={row.get('frustration',0):.2f} confus={row.get('confusion',0):.2f} "
                  f"delight={row.get('delight',0):.2f} HR={row.get('watch_hr',0):.0f}")
    
    # Chunks
    r = requests.get(f"{API}/v1/sessions/{SESSION_ID}/chunks")
    chunks = r.json()
    print(f"\n  Chunk Results: {len(chunks.get('chunks',[]))} chunks")
    for c in chunks.get("chunks", []):
        states = [s["state"] for s in c.get("states_observed", [])]
        events = [e["type"] for e in c.get("events", [])]
        print(f"    Chunk {c['chunk_index']}: states={states} events={events} | {c.get('summary','')[:60]}")
    
    # Events
    r = requests.get(f"{API}/v1/sessions/{SESSION_ID}/events")
    evts = r.json()
    print(f"\n  Gameplay Events: {len(evts.get('events',[]))}")
    for e in evts.get("events", [])[:10]:
        print(f"    [{e.get('type','?'):10s}] t={e.get('timestamp_sec',0):.1f}s — {e.get('description','')}")
    
    # Insights
    r = requests.get(f"{API}/v1/sessions/{SESSION_ID}/insights")
    ins = r.json()
    print(f"\n  Session Insights (Gemini):")
    insight_text = ins.get("insights", "N/A")
    # Print first 500 chars
    for line in insight_text[:800].split("\n"):
        print(f"    {line}")
    
    print(f"\n{'='*60}")
    print(f"  E2E TEST COMPLETE")
    print(f"  Project: {PROJECT_ID} | Session: {SESSION_ID}")
    print(f"  Health Score: {health:.4f} ({label})")
    print(f"  Dashboard: http://localhost:3000/dashboard")
    print(f"  API docs: http://localhost:8000/docs")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
