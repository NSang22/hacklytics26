"""
Snowflake client — Real implementation using snowflake-connector-python.

Medallion architecture:
  Bronze: raw gameplay events, chunk results
  Silver: fused 1-second rows
  Gold:   verdicts, health scores, session summaries

Falls back to in-memory storage when Snowflake credentials are missing.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from config import (
    SNOWFLAKE_ACCOUNT,
    SNOWFLAKE_DATABASE,
    SNOWFLAKE_PASSWORD,
    SNOWFLAKE_SCHEMA,
    SNOWFLAKE_USER,
    SNOWFLAKE_WAREHOUSE,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# DDL — Snowflake table definitions (medallion architecture)
# ─────────────────────────────────────────────────────────────────────────────

_DDL = {
    "BRONZE_GAMEPLAY_EVENTS": """
        CREATE TABLE IF NOT EXISTS BRONZE_GAMEPLAY_EVENTS (
            ingested_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            session_id        VARCHAR(64)   NOT NULL,
            chunk_index       INT,
            abs_timestamp_sec FLOAT,
            type              VARCHAR(128),
            description       VARCHAR(1024),
            raw_json          VARIANT
        )
    """,
    "SILVER_FUSED": """
        CREATE TABLE IF NOT EXISTS SILVER_FUSED (
            ingested_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            session_id         VARCHAR(64)   NOT NULL,
            t                  INT           NOT NULL,
            state              VARCHAR(128),
            time_in_state_sec  INT,
            frustration        FLOAT,
            confusion          FLOAT,
            delight            FLOAT,
            boredom            FLOAT,
            surprise           FLOAT,
            engagement         FLOAT,
            hr                 FLOAT,
            hrv_rmssd          FLOAT,
            hrv_sdnn           FLOAT,
            presage_hr         FLOAT,
            breathing_rate     FLOAT,
            intent_delta       FLOAT,
            dominant_emotion   VARCHAR(64),
            data_quality       FLOAT
        )
    """,
    "GOLD_VERDICTS": """
        CREATE TABLE IF NOT EXISTS GOLD_VERDICTS (
            inserted_at           TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            session_id            VARCHAR(64)   NOT NULL,
            state_name            VARCHAR(128),
            intended_emotion      VARCHAR(64),
            verdict               VARCHAR(8),
            intent_delta_avg      FLOAT,
            actual_duration_sec   INT,
            dominant_emotion      VARCHAR(64),
            raw_json              VARIANT
        )
    """,
    "GOLD_HEALTH_SCORES": """
        CREATE TABLE IF NOT EXISTS GOLD_HEALTH_SCORES (
            inserted_at    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            session_id     VARCHAR(64)   NOT NULL,
            health_score   FLOAT         NOT NULL
        )
    """,
}


class SnowflakeClient:
    """Real Snowflake client with in-memory fallback."""

    def __init__(self):
        self._conn = None
        self._tables_created = False
        # In-memory fallback when Snowflake is not configured
        self._mem: Dict[str, List[Dict]] = {
            "bronze_gameplay_events": [],
            "silver_fused_rows": [],
            "gold_verdicts": [],
            "gold_health_scores": [],
        }

    # ── Connection management ────────────────────────────────

    def _get_connection(self):
        """Return a live Snowflake connection. Caches it for reuse."""
        if self._conn is not None:
            try:
                self._conn.cursor().execute("SELECT 1")
                return self._conn
            except Exception:
                self._conn = None

        import snowflake.connector
        self._conn = snowflake.connector.connect(
            account=SNOWFLAKE_ACCOUNT,
            user=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
            warehouse=SNOWFLAKE_WAREHOUSE,
            database=SNOWFLAKE_DATABASE,
            schema=SNOWFLAKE_SCHEMA,
        )
        logger.info(
            f"[snowflake] Connected to {SNOWFLAKE_ACCOUNT} "
            f"db={SNOWFLAKE_DATABASE} schema={SNOWFLAKE_SCHEMA}"
        )
        return self._conn

    def _ensure_tables(self):
        """Create all tables if they don't exist. Idempotent."""
        if self._tables_created:
            return
        conn = self._get_connection()
        for name, ddl in _DDL.items():
            try:
                conn.cursor().execute(ddl.strip())
                logger.debug(f"[snowflake] Table ready: {name}")
            except Exception as exc:
                logger.error(f"[snowflake] Failed to create {name}: {exc}")
                raise
        self._tables_created = True

    def _use_real(self) -> bool:
        """Check if real Snowflake should be used."""
        return bool(SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER and SNOWFLAKE_PASSWORD)

    # ── Generic insert / query ──────────────────────────────

    async def insert(self, table: str, rows: List[Dict]) -> int:
        """Insert rows into a logical table. Returns rows inserted."""
        if not self._use_real():
            if table not in self._mem:
                self._mem[table] = []
            self._mem[table].extend(rows)
            return len(rows)

        self._ensure_tables()
        conn = self._get_connection()
        for row in rows:
            try:
                conn.cursor().execute(
                    f"INSERT INTO {table} (session_id, raw_json) "
                    f"SELECT %s, PARSE_JSON(%s)",
                    (row.get("session_id", ""), json.dumps(row)),
                )
            except Exception as exc:
                logger.error(f"[snowflake] insert into {table} failed: {exc}")
        return len(rows)

    async def query(
        self, table: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """Query rows from a logical table with optional equality filters."""
        if not self._use_real():
            rows = self._mem.get(table, [])
            if not filters:
                return list(rows)
            return [
                r for r in rows
                if all(r.get(k) == v for k, v in filters.items())
            ]

        self._ensure_tables()
        conn = self._get_connection()
        where_clauses = []
        params = []
        if filters:
            for k, v in filters.items():
                where_clauses.append(f"{k} = %s")
                params.append(v)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {table} WHERE {where_sql}", params)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error(f"[snowflake] query {table} failed: {exc}")
            return []

    # ── Convenience wrappers (called by main.py) ────────────

    async def store_fused_rows(self, session_id: str, rows: List[Dict]) -> int:
        """Write fused 1-second timeline rows to SILVER_FUSED."""
        if not rows:
            return 0

        if not self._use_real():
            tagged = [{**r, "session_id": session_id} for r in rows]
            self._mem.setdefault("silver_fused_rows", []).extend(tagged)
            logger.info(f"[snowflake][mem] SILVER_FUSED: {len(rows)} rows for {session_id}")
            return len(rows)

        self._ensure_tables()
        conn = self._get_connection()
        sql = """
            INSERT INTO SILVER_FUSED
            (session_id, t, state, time_in_state_sec,
             frustration, confusion, delight, boredom, surprise, engagement,
             hr, hrv_rmssd, hrv_sdnn, presage_hr, breathing_rate,
             intent_delta, dominant_emotion, data_quality)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        batch = []
        for r in rows:
            batch.append((
                session_id,
                int(r.get("t", 0)),
                str(r.get("state", "unknown")),
                int(r.get("time_in_state_sec", 0)),
                float(r.get("frustration", 0)),
                float(r.get("confusion", 0)),
                float(r.get("delight", 0)),
                float(r.get("boredom", 0)),
                float(r.get("surprise", 0)),
                float(r.get("engagement", 0)),
                float(r.get("hr", 0)),
                float(r.get("hrv_rmssd", 0)),
                float(r.get("hrv_sdnn", 0)),
                float(r.get("presage_hr", 0)),
                float(r.get("breathing_rate", 0)),
                float(r.get("intent_delta", 0)),
                str(r.get("dominant_emotion", "unknown")),
                float(r.get("data_quality", 1.0)),
            ))
        try:
            conn.cursor().executemany(sql, batch)
            logger.info(f"[snowflake] SILVER_FUSED: inserted {len(batch)} rows for {session_id}")
        except Exception as exc:
            logger.error(f"[snowflake] SILVER_FUSED write failed: {exc}")
        return len(batch)

    async def store_verdicts(self, session_id: str, verdicts: List[Dict]) -> int:
        """Write per-state verdict cards to GOLD_VERDICTS."""
        if not verdicts:
            return 0

        if not self._use_real():
            tagged = [{**v, "session_id": session_id} for v in verdicts]
            self._mem.setdefault("gold_verdicts", []).extend(tagged)
            logger.info(f"[snowflake][mem] GOLD_VERDICTS: {len(verdicts)} for {session_id}")
            return len(verdicts)

        self._ensure_tables()
        conn = self._get_connection()
        sql = """
            INSERT INTO GOLD_VERDICTS
            (session_id, state_name, intended_emotion, verdict,
             intent_delta_avg, actual_duration_sec, dominant_emotion, raw_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s))
        """
        batch = []
        for v in verdicts:
            batch.append((
                session_id,
                str(v.get("state_name", "")),
                str(v.get("intended_emotion", "")),
                str(v.get("verdict", "NO_DATA")),
                float(v.get("intent_delta_avg", 0)),
                int(v.get("actual_duration_sec", 0)),
                str(v.get("dominant_emotion", "")),
                json.dumps(v),
            ))
        try:
            conn.cursor().executemany(sql, batch)
            logger.info(f"[snowflake] GOLD_VERDICTS: inserted {len(batch)} for {session_id}")
        except Exception as exc:
            logger.error(f"[snowflake] GOLD_VERDICTS write failed: {exc}")
        return len(batch)

    async def store_health_score(self, session_id: str, score: float) -> int:
        """Write overall Playtest Health Score to GOLD_HEALTH_SCORES."""
        if not self._use_real():
            self._mem.setdefault("gold_health_scores", []).append(
                {"session_id": session_id, "score": score}
            )
            logger.info(f"[snowflake][mem] GOLD_HEALTH: {session_id} → {score}")
            return 1

        self._ensure_tables()
        conn = self._get_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO GOLD_HEALTH_SCORES (session_id, health_score) VALUES (%s, %s)",
                (session_id, float(score)),
            )
            logger.info(f"[snowflake] GOLD_HEALTH: {session_id} → {score}")
        except Exception as exc:
            logger.error(f"[snowflake] GOLD_HEALTH write failed: {exc}")
        return 1

    async def store_gameplay_events(
        self,
        session_id: str,
        chunk_index: int,
        chunk_start_sec: float,
        events: List[Dict],
    ) -> int:
        """Write detected gameplay events to BRONZE_GAMEPLAY_EVENTS."""
        if not events:
            return 0

        tagged = [
            {
                **ev,
                "session_id": session_id,
                "chunk_index": chunk_index,
                "abs_timestamp_sec": chunk_start_sec + ev.get("timestamp_sec", 0),
            }
            for ev in events
        ]

        if not self._use_real():
            self._mem.setdefault("bronze_gameplay_events", []).extend(tagged)
            logger.info(f"[snowflake][mem] BRONZE_EVENTS: {len(events)} for {session_id} chunk {chunk_index}")
            return len(events)

        self._ensure_tables()
        conn = self._get_connection()
        sql = """
            INSERT INTO BRONZE_GAMEPLAY_EVENTS
            (session_id, chunk_index, abs_timestamp_sec, type, description, raw_json)
            VALUES (%s, %s, %s, %s, %s, PARSE_JSON(%s))
        """
        batch = []
        for ev in tagged:
            batch.append((
                session_id,
                chunk_index,
                float(ev.get("abs_timestamp_sec", 0)),
                str(ev.get("type", "")),
                str(ev.get("description", "")),
                json.dumps(ev),
            ))
        try:
            conn.cursor().executemany(sql, batch)
            logger.info(f"[snowflake] BRONZE_EVENTS: inserted {len(batch)} for {session_id} chunk {chunk_index}")
        except Exception as exc:
            logger.error(f"[snowflake] BRONZE_EVENTS write failed: {exc}")
        return len(batch)

    async def get_session_verdicts(self, session_id: str) -> List[Dict]:
        """Retrieve verdicts for a session."""
        return await self.query("gold_verdicts", {"session_id": session_id})

    async def get_project_sessions(self, project_id: str) -> List[Dict]:
        """Retrieve health scores for all sessions in a project."""
        return await self.query("gold_health_scores", {"project_id": project_id})

    async def run_query(self, sql: str, params: tuple = ()) -> List[Dict]:
        """Run a raw SQL query against Snowflake. Used by Sphinx for ad-hoc analytics."""
        if not self._use_real():
            logger.warning("[snowflake][mem] run_query called but no real connection")
            return []

        self._ensure_tables()
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.error(f"[snowflake] run_query failed: {exc}")
            return []

    def is_configured(self) -> bool:
        """Return True if real Snowflake credentials are available."""
        return bool(SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER and SNOWFLAKE_PASSWORD)
