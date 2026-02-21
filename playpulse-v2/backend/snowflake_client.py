"""
Snowflake client — CRUD helpers for the bronze / silver / gold medallion
data architecture.

  • Bronze: raw emotion frames, raw watch samples, raw chunk results
  • Silver: fused 1-second rows, per-chunk stitched observations
  • Gold:   verdicts, health scores, aggregate comparisons

STUB — stores everything in-memory with dict-of-lists.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT", "")
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER", "")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD", "")


class SnowflakeClient:
    """In-memory stub for Snowflake warehouse operations."""

    def __init__(self):
        self._tables: Dict[str, List[Dict]] = {
            # Bronze
            "bronze_emotion_frames": [],
            "bronze_watch_samples": [],
            "bronze_chunk_results": [],
            "bronze_gameplay_events": [],
            # Silver
            "silver_fused_rows": [],
            "silver_chunk_timeline": [],
            # Gold
            "gold_verdicts": [],
            "gold_health_scores": [],
            "gold_aggregate": [],
        }

    # ── Generic insert / query ──────────────────────────────
    async def insert(self, table: str, rows: List[Dict]) -> int:
        """Insert rows into a logical table. Returns rows inserted."""
        if table not in self._tables:
            self._tables[table] = []
        self._tables[table].extend(rows)
        return len(rows)

    async def query(
        self, table: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """Query rows from a logical table with optional equality filters."""
        rows = self._tables.get(table, [])
        if not filters:
            return list(rows)
        return [
            r for r in rows
            if all(r.get(k) == v for k, v in filters.items())
        ]

    # ── Convenience wrappers ────────────────────────────────
    async def store_fused_rows(self, session_id: str, rows: List[Dict]) -> int:
        tagged = [{**r, "session_id": session_id} for r in rows]
        return await self.insert("silver_fused_rows", tagged)

    async def store_verdicts(self, session_id: str, verdicts: List[Dict]) -> int:
        tagged = [{**v, "session_id": session_id} for v in verdicts]
        return await self.insert("gold_verdicts", tagged)

    async def store_health_score(self, session_id: str, score: float) -> int:
        return await self.insert("gold_health_scores", [
            {"session_id": session_id, "score": score}
        ])

    async def get_session_verdicts(self, session_id: str) -> List[Dict]:
        return await self.query("gold_verdicts", {"session_id": session_id})

    async def store_gameplay_events(
        self, session_id: str, chunk_index: int,
        chunk_start_sec: float, events: List[Dict],
    ) -> int:
        """Write detected gameplay events to bronze_gameplay_events."""
        tagged = [
            {
                **ev,
                "session_id": session_id,
                "chunk_index": chunk_index,
                "abs_timestamp_sec": chunk_start_sec + ev.get("timestamp_sec", 0),
            }
            for ev in events
        ]
        return await self.insert("bronze_gameplay_events", tagged)

    async def get_project_sessions(self, project_id: str) -> List[Dict]:
        return await self.query("gold_health_scores", {"project_id": project_id})

    def is_configured(self) -> bool:
        return bool(SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER)
