"""
Chunk Uploader — asynchronously uploads screen capture chunks, emotion data,
and watch readings to the AURA backend API.

Handles:
  • Video chunk upload (POST /v1/sessions/{sid}/upload-chunk)
  • Emotion data streaming (POST /v1/sessions/{sid}/emotion-frames)
  • Watch data streaming (WebSocket /v1/sessions/{sid}/watch-stream)
  • Face video upload (POST /v1/sessions/{sid}/upload-face-video)
  • Session finalization (POST /v1/sessions/{sid}/finalize)
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import requests


class ChunkUploader:
    """Manages async upload of data streams to the AURA backend."""

    def __init__(
        self,
        backend_url: str = "http://localhost:8000",
        session_id: str = "",
        project_id: str = "",
    ):
        self.backend_url = backend_url.rstrip("/")
        self.session_id = session_id
        self.project_id = project_id

        # Upload queue for chunks
        self._chunk_queue: queue.Queue = queue.Queue()
        self._emotion_queue: queue.Queue = queue.Queue()
        self._watch_queue: queue.Queue = queue.Queue()

        self._running = False
        self._upload_thread: Optional[threading.Thread] = None
        self._emotion_thread: Optional[threading.Thread] = None
        self._watch_thread: Optional[threading.Thread] = None

        # Stats
        self.chunks_uploaded = 0
        self.chunks_failed = 0
        self.emotion_frames_sent = 0
        self.watch_readings_sent = 0

        # Callbacks
        self._on_upload_complete: Optional[Callable[[int, bool], None]] = None
        self._on_status_change: Optional[Callable[[str], None]] = None

    def start(
        self,
        on_upload_complete: Optional[Callable[[int, bool], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Start the upload worker threads.

        Args:
            on_upload_complete: Callback ``(chunk_index, success)`` after each upload.
            on_status_change: Callback ``(status_message)`` for UI updates.
        """
        if self._running:
            return

        self._on_upload_complete = on_upload_complete
        self._on_status_change = on_status_change
        self._running = True
        self.chunks_uploaded = 0
        self.chunks_failed = 0
        self.emotion_frames_sent = 0
        self.watch_readings_sent = 0

        # Video chunk upload thread
        self._upload_thread = threading.Thread(target=self._chunk_upload_worker, daemon=True)
        self._upload_thread.start()

        # Emotion batch upload thread
        self._emotion_thread = threading.Thread(target=self._emotion_upload_worker, daemon=True)
        self._emotion_thread.start()

        # Watch data upload thread
        self._watch_thread = threading.Thread(target=self._watch_upload_worker, daemon=True)
        self._watch_thread.start()

        self._emit_status("Uploader started")

    def stop(self) -> Dict[str, int]:
        """Stop upload workers and flush remaining data.

        Returns stats dict.
        """
        self._running = False

        # Wait for queues to drain (with timeout)
        for _ in range(50):  # 5 seconds max
            if self._chunk_queue.empty():
                break
            time.sleep(0.1)

        if self._upload_thread and self._upload_thread.is_alive():
            self._upload_thread.join(timeout=5.0)
        if self._emotion_thread and self._emotion_thread.is_alive():
            self._emotion_thread.join(timeout=3.0)
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=3.0)

        return {
            "chunks_uploaded": self.chunks_uploaded,
            "chunks_failed": self.chunks_failed,
            "emotion_frames_sent": self.emotion_frames_sent,
            "watch_readings_sent": self.watch_readings_sent,
        }

    # ── Public enqueue methods ──────────────────────────────

    def enqueue_chunk(self, video_bytes: bytes, chunk_index: int) -> None:
        """Add a video chunk to the upload queue."""
        self._chunk_queue.put((video_bytes, chunk_index))

    def enqueue_emotion(self, emotion_data: Dict) -> None:
        """Add an emotion reading to the batch queue."""
        self._emotion_queue.put(emotion_data)

    def enqueue_watch(self, watch_data: Dict) -> None:
        """Add a watch reading to the batch queue."""
        self._watch_queue.put(watch_data)

    def upload_face_video(self, video_path: str) -> bool:
        """Upload the full face video file (called at session end)."""
        if not self.session_id or not video_path:
            return False

        url = f"{self.backend_url}/v1/sessions/{self.session_id}/upload-face-video"
        try:
            with open(video_path, "rb") as f:
                resp = requests.post(url, files={"file": ("face.mp4", f, "video/mp4")}, timeout=60)
            if resp.status_code == 200:
                self._emit_status("Face video uploaded")
                return True
            else:
                self._emit_status(f"Face video upload failed: {resp.status_code}")
                return False
        except Exception as e:
            self._emit_status(f"Face video upload error: {e}")
            return False

    def finalize_session(self) -> Optional[Dict]:
        """Trigger session finalization on the backend."""
        if not self.session_id:
            return None

        url = f"{self.backend_url}/v1/sessions/{self.session_id}/finalize"
        try:
            resp = requests.post(url, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                self._emit_status(f"Session finalized: health={data.get('health_score', '?')}")
                return data
            else:
                self._emit_status(f"Finalize failed: {resp.status_code}")
                return None
        except Exception as e:
            self._emit_status(f"Finalize error: {e}")
            return None

    def create_session(self, tester_name: str = "desktop_tester") -> Optional[str]:
        """Create a new session on the backend and set self.session_id.

        Returns session_id or None.
        """
        url = f"{self.backend_url}/v1/projects/{self.project_id}/sessions"
        try:
            resp = requests.post(
                url,
                json={"tester_name": tester_name, "chunk_duration_sec": 10.0},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.session_id = data.get("session_id", "")
                self._emit_status(f"Session created: {self.session_id}")
                return self.session_id
            else:
                self._emit_status(f"Create session failed: {resp.status_code}")
                return None
        except Exception as e:
            self._emit_status(f"Create session error: {e}")
            return None

    # ── Internal workers ────────────────────────────────────

    def _chunk_upload_worker(self) -> None:
        """Worker thread that uploads video chunks from the queue."""
        while self._running or not self._chunk_queue.empty():
            try:
                video_bytes, chunk_index = self._chunk_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            success = self._upload_chunk(video_bytes, chunk_index)
            if success:
                self.chunks_uploaded += 1
            else:
                self.chunks_failed += 1

            if self._on_upload_complete:
                try:
                    self._on_upload_complete(chunk_index, success)
                except Exception:
                    pass

            self._chunk_queue.task_done()

    def _upload_chunk(self, video_bytes: bytes, chunk_index: int) -> bool:
        """Upload a single chunk to the backend."""
        if not self.session_id:
            return False

        url = f"{self.backend_url}/v1/sessions/{self.session_id}/upload-chunk"
        try:
            resp = requests.post(
                url,
                data={"chunk_index": str(chunk_index)},
                files={"file": (f"chunk_{chunk_index}.mp4", video_bytes, "video/mp4")},
                timeout=30,
            )
            if resp.status_code == 200:
                self._emit_status(f"Chunk {chunk_index} uploaded ({len(video_bytes)} bytes)")
                return True
            else:
                self._emit_status(f"Chunk {chunk_index} failed: {resp.status_code}")
                return False
        except Exception as e:
            self._emit_status(f"Chunk {chunk_index} error: {e}")
            return False

    def _emotion_upload_worker(self) -> None:
        """Batch emotion frames and upload every 2 seconds."""
        while self._running:
            batch = []
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                try:
                    item = self._emotion_queue.get(timeout=0.5)
                    batch.append(item)
                    self._emotion_queue.task_done()
                except queue.Empty:
                    continue

            if batch and self.session_id:
                self._upload_emotion_batch(batch)

        # Flush remaining
        batch = []
        while not self._emotion_queue.empty():
            try:
                batch.append(self._emotion_queue.get_nowait())
                self._emotion_queue.task_done()
            except queue.Empty:
                break
        if batch and self.session_id:
            self._upload_emotion_batch(batch)

    def _upload_emotion_batch(self, batch: List[Dict]) -> None:
        """Upload a batch of emotion frames."""
        url = f"{self.backend_url}/v1/sessions/{self.session_id}/emotion-frames"
        try:
            resp = requests.post(url, json={"frames": batch}, timeout=10)
            if resp.status_code == 200:
                self.emotion_frames_sent += len(batch)
            else:
                # Endpoint may not exist yet — store locally
                pass
        except Exception:
            pass

    def _watch_upload_worker(self) -> None:
        """Stream watch readings to the backend WebSocket or REST fallback."""
        ws = None
        try:
            import websocket
            ws_url = self.backend_url.replace("http", "ws") + f"/v1/sessions/{self.session_id}/watch-stream"
            ws = websocket.WebSocket()
            ws.connect(ws_url, timeout=5)
        except Exception:
            ws = None

        while self._running:
            try:
                item = self._watch_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if ws:
                try:
                    ws.send(json.dumps(item))
                    self.watch_readings_sent += 1
                except Exception:
                    ws = None  # Fall through to REST

            if not ws:
                # REST fallback
                self._upload_watch_rest(item)

            self._watch_queue.task_done()

        if ws:
            try:
                ws.close()
            except Exception:
                pass

    def _upload_watch_rest(self, reading: Dict) -> None:
        """REST fallback for watch data upload."""
        url = f"{self.backend_url}/v1/sessions/{self.session_id}/watch-data"
        try:
            resp = requests.post(url, json=reading, timeout=5)
            if resp.status_code == 200:
                self.watch_readings_sent += 1
        except Exception:
            pass

    # ── Helpers ─────────────────────────────────────────────

    def _emit_status(self, msg: str) -> None:
        """Notify status callback."""
        print(f"[Uploader] {msg}")
        if self._on_status_change:
            try:
                self._on_status_change(msg)
            except Exception:
                pass

    def check_backend(self) -> bool:
        """Check if the backend is reachable."""
        try:
            resp = requests.get(self.backend_url, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
