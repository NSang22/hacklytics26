#!/usr/bin/env python3
"""
AURA Desktop Capture Agent
===========================
Captures the screen at a configurable FPS, bundles frames into chunks,
and streams them to the PlayPulse backend for Gemini Vision DFA analysis.

Works with any game running on the desktop — emulators, native games, anything.

Usage
-----
  # Create a new session automatically:
  python capture_agent.py --project PROJECT_ID

  # Attach to an existing session:
  python capture_agent.py --project PROJECT_ID --session SESSION_ID

  # Full options:
  python capture_agent.py --project PROJECT_ID --tester "Player 1" \
      --backend http://localhost:8000 --fps 2 --chunk-sec 15 --monitor 1 \
      --width 1280

Press Ctrl+C to stop and auto-finalize the session.

Dependencies (see capture_requirements.txt):
  pip install mss Pillow requests
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import threading
import time
from typing import List, Tuple

try:
    import mss
    import mss.tools
except ImportError:
    sys.exit("[AURA] mss not installed. Run: pip install mss")

try:
    from PIL import Image
except ImportError:
    sys.exit("[AURA] Pillow not installed. Run: pip install Pillow")

try:
    import requests
except ImportError:
    sys.exit("[AURA] requests not installed. Run: pip install requests")


# ── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_BACKEND = "http://localhost:8000"
DEFAULT_FPS = 2          # 2 FPS → 30 frames per 15s chunk; enough for Gemini
DEFAULT_CHUNK_SEC = 15   # seconds per chunk
DEFAULT_WIDTH = 1280     # resize capture to this width (preserves aspect ratio)
DEFAULT_QUALITY = 70     # JPEG quality (0-95); lower = smaller payload


# ── Screen capture ───────────────────────────────────────────────────────────

def list_monitors() -> None:
    with mss.mss() as sct:
        for i, m in enumerate(sct.monitors):
            print(f"  Monitor {i}: {m}")


def capture_chunk(
    monitor_idx: int,
    fps: float,
    duration_sec: float,
    width: int,
    quality: int,
) -> List[Tuple[bytes, float]]:
    """Capture JPEG frames for one chunk duration.

    Returns list of (jpeg_bytes, timestamp_sec_within_chunk).
    Timestamps are relative to chunk start so Gemini can reason about timing.
    """
    frames: List[Tuple[bytes, float]] = []
    interval = 1.0 / fps

    with mss.mss() as sct:
        monitor = sct.monitors[monitor_idx]
        chunk_start = time.monotonic()
        deadline = chunk_start + duration_sec

        while True:
            frame_start = time.monotonic()
            elapsed = frame_start - chunk_start
            if elapsed >= duration_sec:
                break

            # Grab screen
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

            # Resize for bandwidth efficiency
            if img.width > width:
                ratio = width / img.width
                img = img.resize((width, int(img.height * ratio)), Image.LANCZOS)

            # Encode as JPEG
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            frames.append((buf.getvalue(), round(elapsed, 2)))

            # Sleep the remainder of the interval
            used = time.monotonic() - frame_start
            sleep = interval - used
            if sleep > 0:
                time.sleep(sleep)

    return frames


# ── Upload ───────────────────────────────────────────────────────────────────

def upload_frames(
    backend: str,
    session_id: str,
    chunk_index: int,
    frames: List[Tuple[bytes, float]],
) -> dict:
    """POST JPEG frames to /v1/sessions/{session_id}/upload-frames."""
    timestamps = json.dumps([ts for _, ts in frames])
    files = [
        ("frames", (f"frame_{i:04d}.jpg", data, "image/jpeg"))
        for i, (data, _) in enumerate(frames)
    ]
    try:
        resp = requests.post(
            f"{backend}/v1/sessions/{session_id}/upload-frames",
            data={"chunk_index": str(chunk_index), "timestamps": timestamps},
            files=files,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[AURA] Upload error (chunk {chunk_index}): {e}")
        return {}


def _upload_async(backend, session_id, chunk_index, frames):
    """Fire-and-forget upload so recording continues without blocking."""
    result = upload_frames(backend, session_id, chunk_index, frames)
    if result.get("status") == "received":
        print(f"[AURA] Chunk {chunk_index} uploaded ({result.get('frames_count')} frames)")
    else:
        print(f"[AURA] Chunk {chunk_index} upload response: {result}")


# ── Session management ───────────────────────────────────────────────────────

def create_session(backend: str, project_id: str, tester: str, chunk_sec: float) -> str:
    resp = requests.post(
        f"{backend}/v1/projects/{project_id}/sessions",
        json={"tester_name": tester, "chunk_duration_sec": chunk_sec},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["session_id"]


def finalize_session(backend: str, session_id: str) -> dict:
    resp = requests.post(
        f"{backend}/v1/sessions/{session_id}/finalize",
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


# ── Main loop ────────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    backend = args.backend.rstrip("/")

    # Resolve session
    session_id = args.session
    if not session_id:
        print(f"[AURA] Creating session for project {args.project}...")
        session_id = create_session(backend, args.project, args.tester, args.chunk_sec)
        print(f"[AURA] Session ID: {session_id}")

    print(
        f"[AURA] Capturing monitor {args.monitor} at {args.fps} FPS "
        f"| {args.chunk_sec}s chunks | resize to {args.width}px wide"
    )
    print("[AURA] Press Ctrl+C to stop and finalize.")
    print()

    chunk_index = 0
    try:
        while True:
            print(f"[AURA] ● Recording chunk {chunk_index}...", end=" ", flush=True)
            frames = capture_chunk(
                monitor_idx=args.monitor,
                fps=args.fps,
                duration_sec=args.chunk_sec,
                width=args.width,
                quality=args.quality,
            )
            print(f"{len(frames)} frames captured — uploading async")

            threading.Thread(
                target=_upload_async,
                args=(backend, session_id, chunk_index, frames),
                daemon=True,
            ).start()

            chunk_index += 1

    except KeyboardInterrupt:
        print(f"\n[AURA] Stopping. Finalizing session {session_id}...")
        try:
            result = finalize_session(backend, session_id)
            score = result.get("health_score", "?")
            print(f"[AURA] Done! Health score: {score}")
            print(f"[AURA] Session ID: {session_id}")
        except Exception as e:
            print(f"[AURA] Finalize error: {e}")
            print(f"[AURA] Manually finalize: POST {backend}/v1/sessions/{session_id}/finalize")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AURA Desktop Capture Agent — streams screen to Gemini Vision pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--project", required=True, help="PlayPulse project ID")
    parser.add_argument("--session", default="", help="Existing session ID (created if omitted)")
    parser.add_argument("--tester", default="player", help="Tester name")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, help="Backend URL")
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS, help="Capture FPS")
    parser.add_argument("--chunk-sec", type=float, default=DEFAULT_CHUNK_SEC,
                        help="Chunk duration in seconds")
    parser.add_argument("--monitor", type=int, default=1,
                        help="Monitor index (0=all, 1=primary, 2=secondary...)")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH,
                        help="Max frame width in pixels (maintains aspect ratio)")
    parser.add_argument("--quality", type=int, default=DEFAULT_QUALITY,
                        help="JPEG quality 0-95")
    parser.add_argument("--list-monitors", action="store_true",
                        help="Print available monitors and exit")

    args = parser.parse_args()

    if args.list_monitors:
        list_monitors()
        return

    run(args)


if __name__ == "__main__":
    main()
