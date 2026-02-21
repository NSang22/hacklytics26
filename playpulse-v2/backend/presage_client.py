"""
Presage client — abstracts the Presage Insights emotion-detection SDK.

Supports two modes:
  • Live mode (WebSocket) — receive ~10 Hz emotion frames during a session
  • Batch mode — analyse a recorded face-cam video after session ends

This is a STUB — real implementation would integrate with
https://presageinsights.com developer API.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any, Callable, Dict, List, Optional

from models import EmotionFrame

PRESAGE_API_KEY = os.getenv("PRESAGE_API_KEY", "")


class PresageClient:
    """Stub for the Presage emotion detection service."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or PRESAGE_API_KEY
        self._live_running = False
        self._callbacks: List[Callable] = []

    # ── Live mode ────────────────────────────────────────────
    async def start_live_stream(
        self,
        session_id: str,
        on_frame: Optional[Callable[[EmotionFrame], Any]] = None,
    ) -> None:
        """Open a live emotion stream for a session.
        In production this would maintain a WebSocket to the Presage SDK.
        """
        self._live_running = True
        if on_frame:
            self._callbacks.append(on_frame)
        # Stub: doesn't actually connect anywhere

    async def stop_live_stream(self, session_id: str) -> None:
        self._live_running = False
        self._callbacks.clear()

    # ── Batch mode ───────────────────────────────────────────
    async def analyse_video(
        self, video_bytes: bytes, session_id: str
    ) -> List[EmotionFrame]:
        """Analyse a face-cam recording and return emotion frames.

        STUB: returns synthetic frames every 100ms for a 60-second video.
        """
        duration_sec = 60  # Assume 60s; real impl would detect duration
        frames: List[EmotionFrame] = []
        t = 0.0
        while t < duration_sec:
            frames.append(
                EmotionFrame(
                    timestamp_sec=round(t, 2),
                    emotions={
                        "frustration": round(random.uniform(0, 0.4), 3),
                        "confusion": round(random.uniform(0, 0.3), 3),
                        "delight": round(random.uniform(0.2, 0.7), 3),
                        "boredom": round(random.uniform(0, 0.2), 3),
                        "surprise": round(random.uniform(0, 0.3), 3),
                        "engagement": round(random.uniform(0.3, 0.8), 3),
                    },
                )
            )
            t += 0.1
        return frames

    # ── Utility ──────────────────────────────────────────────
    def is_configured(self) -> bool:
        return bool(self.api_key)
