#!/usr/bin/env python3
"""
End-to-end test: Create project, session, upload data, finalize, verify Snowflake + VectorAI.
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def main():
    print("=" * 60)
    print("E2E Test: Data Flow to Snowflake + VectorAI")
    print("=" * 60)
    
    # 1. Create project
    print("\n[1/6] Creating project...")
    project_data = {
        "name": "E2E Test Game",
        "description": "Test to verify data persistence",
        "dfa_states": [
            {
                "name": "tutorial",
                "description": "Learning basic controls",
                "intended_emotion": "delight",
                "acceptable_range": [0.4, 0.8],
                "expected_duration_sec": 30,
                "visual_cues": ["tutorial UI", "tooltips"],
                "failure_indicators": ["player stuck", "confusion"],
                "success_indicators": ["progress"],
            },
            {
                "name": "puzzle_room",
                "description": "First puzzle challenge",
                "intended_emotion": "confusion",
                "acceptable_range": [0.2, 0.5],
                "expected_duration_sec": 45,
                "visual_cues": ["puzzle elements"],
                "failure_indicators": ["frustration spike"],
                "success_indicators": ["solving puzzle"],
            },
        ],
        "transitions": [
            {"from_state": "tutorial", "to_state": "puzzle_room", "trigger": "tutorial_complete"}
        ],
    }
    
    resp = requests.post(f"{BASE_URL}/v1/projects", json=project_data)
    resp.raise_for_status()
    project = resp.json()
    project_id = project["project_id"]
    print(f"   ✓ Project created: {project_id}")
    
    # 2. Create session
    print("\n[2/6] Creating session...")
    session_data = {"tester_name": "test_user", "chunk_duration_sec": 10.0}
    resp = requests.post(f"{BASE_URL}/v1/projects/{project_id}/sessions", json=session_data)
    resp.raise_for_status()
    session = resp.json()
    session_id = session["session_id"]
    print(f"   ✓ Session created: {session_id}")
    
    # 3. Upload test chunk (minimal video data)
    print("\n[3/6] Uploading test video chunk...")
    # Create a minimal valid video file (1 second of black frames)
    import cv2
    import numpy as np
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(tmp.name, fourcc, 30.0, (640, 480))
        for _ in range(30):  # 1 second at 30fps
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            out.write(frame)
        out.release()
        
        with open(tmp.name, "rb") as f:
            video_bytes = f.read()
    
    files = {"file": ("chunk_0.mp4", video_bytes, "video/mp4")}
    data = {"chunk_index": "0"}
    resp = requests.post(f"{BASE_URL}/v1/sessions/{session_id}/upload-chunk", files=files, data=data)
    resp.raise_for_status()
    print(f"   ✓ Video chunk uploaded (background processing)")
    
    # Wait for chunk processing
    print("   Waiting 5s for chunk processing...")
    time.sleep(5)
    
    # 4. Upload emotion data
    print("\n[4/6] Uploading emotion frames...")
    emotion_frames = [
        {"timestamp_sec": i, "frustration": 0.2, "confusion": 0.3, "delight": 0.6, 
         "boredom": 0.1, "surprise": 0.2, "engagement": 0.7}
        for i in range(0, 10, 1)
    ]
    resp = requests.post(f"{BASE_URL}/v1/sessions/{session_id}/emotion-frames", 
                        json={"frames": emotion_frames})
    resp.raise_for_status()
    print(f"   ✓ {len(emotion_frames)} emotion frames uploaded")
    
    # 5. Upload watch data
    print("\n[5/6] Uploading watch data...")
    watch_data = [
        {"timestamp_sec": i, "hr": 75 + i, "hrv_rmssd": 50, "hrv_sdnn": 45}
        for i in range(0, 10, 1)
    ]
    for reading in watch_data:
        requests.post(f"{BASE_URL}/v1/sessions/{session_id}/watch-data", json=reading)
    print(f"   ✓ {len(watch_data)} watch readings uploaded")
    
    # 6. Finalize session (triggers Snowflake + VectorAI writes)
    print("\n[6/6] Finalizing session (triggers data processing)...")
    resp = requests.post(f"{BASE_URL}/v1/sessions/{session_id}/finalize", timeout=60)
    resp.raise_for_status()
    result = resp.json()
    print(f"   ✓ Session finalized!")
    print(f"      Health Score: {result.get('health_score', 'N/A')}")
    print(f"      Verdicts: {result.get('verdicts_count', 0)}")
    
    # Verify data
    print("\n" + "=" * 60)
    print("VERIFICATION")   
    print("=" * 60)
    
    # Check VectorAI fallback file
    print("\n[VectorAI] Checking persistent storage...")
    import os
    fallback_path = "backend/vectorai_fallback.json"
    if os.path.exists(fallback_path):
        with open(fallback_path) as f:
            embeddings = json.load(f)
        print(f"   ✓ VectorAI fallback file exists: {len(embeddings)} embeddings")
        if embeddings:
            print(f"      Sample embedding ID: {embeddings[0]['id']}")
            print(f"      Vector dimension: {len(embeddings[0]['vector'])}")
    else:
        print(f"   ✗ VectorAI fallback file not found")
    
    # Check Snowflake (query timeline)
    print("\n[Snowflake] Checking fused timeline...")
    resp = requests.get(f"{BASE_URL}/v1/sessions/{session_id}/timeline")
    if resp.status_code == 200:
        timeline = resp.json()
        print(f"   ✓ Timeline retrieved: {len(timeline)} rows")
        if timeline:
            print(f"      Sample row: t={timeline[0].get('t')}, state={timeline[0].get('state')}")
    else:
        print(f"   ✗ Timeline query failed: {resp.status_code}")
    
    # Check verdicts
    print("\n[Snowflake] Checking verdicts...")
    resp = requests.get(f"{BASE_URL}/v1/sessions/{session_id}/verdicts")
    if resp.status_code == 200:
        verdicts = resp.json()
        print(f"   ✓ Verdicts retrieved: {len(verdicts)}")
        for v in verdicts:
            print(f"      {v['state_name']}: {v['verdict']}")
    else:
        print(f"   ✗ Verdicts query failed: {resp.status_code}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print(f"\nProject ID: {project_id}")
    print(f"Session ID: {session_id}")
    print(f"\nView in frontend: http://localhost:3000")
    print(f"API docs: http://localhost:8000/docs")

if __name__ == "__main__":
    main()
