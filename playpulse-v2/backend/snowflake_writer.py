"""
Crashout — Snowflake Writer (Medallion Architecture)

Writes session data to Snowflake in three layers:

  BRONZE  — Raw streams exactly as received (append-only, never modified)
             Tables: BRONZE_PRESAGE, BRONZE_WATCH, BRONZE_CHUNKS

  SILVER  — Clean fused 1-Hz DataFrame rows
             Table: SILVER_FUSED

  GOLD    — Per-state aggregated verdicts + overall Playtest Health Score
             Tables: GOLD_STATE_VERDICTS, GOLD_SESSION_SUMMARY

Session isolation: every row includes session_id as a partition key so
multiple testers can run concurrently without interfering.

Public API (called by main.py):
    write_bronze_presage(session_id, project_id, frames)
    write_bronze_watch(session_id, project_id, readings)
    write_bronze_chunks(session_id, project_id, chunk_results)
    write_silver(session_id, project_id, fused_df)
    write_gold(session_id, project_id, fused_df, dfa_config)
    write_all(session_id, project_id, presage, watch, chunks, fused_df, dfa_config)

Set MOCK_MODE=true in .env to skip all Snowflake calls during development.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from config import (
    EMOTION_COLUMN_MAP,
    MOCK_MODE,
    SNOWFLAKE_ACCOUNT,
    SNOWFLAKE_DATABASE,
    SNOWFLAKE_PASSWORD,
    SNOWFLAKE_SCHEMA,
    SNOWFLAKE_USER,
    SNOWFLAKE_WAREHOUSE,
    WARN_DELTA_THRESHOLD,
)
from models import ChunkResult, DFAConfig

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Connection management
# ─────────────────────────────────────────────────────────────────────────────

def _get_connection():
    """
    Returns a live Snowflake connection.
    Raises RuntimeError if credentials are missing.
    """
    if not all([SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD]):
        raise RuntimeError(
            "Snowflake credentials missing. Set SNOWFLAKE_ACCOUNT, "
            "SNOWFLAKE_USER, SNOWFLAKE_PASSWORD in .env"
        )
    import snowflake.connector
    conn = snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
    )
    return conn


def _execute(conn, sql: str, params=None):
    """Execute a single SQL statement, log errors but don't crash."""
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    except Exception as exc:
        logger.error(f"[snowflake] SQL error: {exc}\nSQL: {sql[:200]}")
        raise


def _executemany(conn, sql: str, rows: List[tuple]):
    """Bulk insert with executemany."""
    try:
        cur = conn.cursor()
        cur.executemany(sql, rows)
    except Exception as exc:
        logger.error(f"[snowflake] Bulk insert error: {exc}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# DDL — create tables if they don't exist
# ─────────────────────────────────────────────────────────────────────────────

_DDL = {
    "BRONZE_PRESAGE": """
        CREATE TABLE IF NOT EXISTS BRONZE_PRESAGE (
            ingested_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP,
            session_id      VARCHAR(64)   NOT NULL,
            project_id      VARCHAR(64),
            timestamp_sec   FLOAT,
            frustration     FLOAT,
            confusion       FLOAT,
            delight         FLOAT,
            boredom         FLOAT,
            surprise        FLOAT,
            engagement      FLOAT,
            presage_hr      FLOAT,
            breathing_rate  FLOAT,
            gaze_x          FLOAT,
            gaze_y          FLOAT,
            gaze_confidence FLOAT,
            head_pitch      FLOAT,
            head_yaw        FLOAT,
            head_roll       FLOAT,
            raw_json        VARIANT
        )
    """,
    "BRONZE_WATCH": """
        CREATE TABLE IF NOT EXISTS BRONZE_WATCH (
            ingested_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP,
            session_id      VARCHAR(64)   NOT NULL,
            project_id      VARCHAR(64),
            timestamp_sec   FLOAT,
            hr              FLOAT,
            hrv_rmssd       FLOAT,
            hrv_sdnn        FLOAT,
            movement_var    FLOAT,
            raw_json        VARIANT
        )
    """,
    "BRONZE_CHUNKS": """
        CREATE TABLE IF NOT EXISTS BRONZE_CHUNKS (
            ingested_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP,
            session_id      VARCHAR(64)   NOT NULL,
            project_id      VARCHAR(64),
            chunk_index     INT,
            chunk_start_sec FLOAT,
            chunk_end_sec   FLOAT,
            end_state       VARCHAR(128),
            end_status      VARCHAR(64),
            cumulative_deaths INT,
            raw_json        VARIANT
        )
    """,
    "SILVER_FUSED": """
        CREATE TABLE IF NOT EXISTS SILVER_FUSED (
            ingested_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP,
            session_id         VARCHAR(64)   NOT NULL,
            project_id         VARCHAR(64),
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
    "GOLD_STATE_VERDICTS": """
        CREATE TABLE IF NOT EXISTS GOLD_STATE_VERDICTS (
            inserted_at           TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP,
            session_id            VARCHAR(64)   NOT NULL,
            project_id            VARCHAR(64),
            state_name            VARCHAR(128)  NOT NULL,
            intended_emotion      VARCHAR(64),
            intended_score        FLOAT,
            acceptable_range_low  FLOAT,
            acceptable_range_high FLOAT,
            actual_avg_score      FLOAT,
            intent_delta_avg      FLOAT,
            actual_duration_sec   INT,
            expected_duration_sec FLOAT,
            duration_delta_sec    FLOAT,
            verdict               VARCHAR(8),
            dominant_emotion      VARCHAR(64)
        )
    """,
    "GOLD_SESSION_SUMMARY": """
        CREATE TABLE IF NOT EXISTS GOLD_SESSION_SUMMARY (
            inserted_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP,
            session_id          VARCHAR(64)   NOT NULL,
            project_id          VARCHAR(64),
            total_duration_sec  INT,
            health_score        FLOAT,
            pass_count          INT,
            warn_count          INT,
            fail_count          INT,
            total_deaths        INT,
            dominant_emotion    VARCHAR(64),
            state_summary_json  VARIANT
        )
    """,
}


def ensure_tables(conn):
    """Create all tables if they don't exist. Safe to call repeatedly."""
    for table_name, ddl in _DDL.items():
        try:
            _execute(conn, ddl.strip())
            logger.debug(f"[snowflake] Table ready: {table_name}")
        except Exception as exc:
            logger.error(f"[snowflake] Failed to create {table_name}: {exc}")
            raise


# ─────────────────────────────────────────────────────────────────────────────
# BRONZE writes
# ─────────────────────────────────────────────────────────────────────────────

def write_bronze_presage(
    session_id: str,
    project_id: str,
    frames: List[Any],
    conn=None,
) -> int:
    """
    Write raw Presage frames to BRONZE_PRESAGE.
    Accepts List[EmotionFrame] or List[dict].
    Returns number of rows inserted.
    """
    if MOCK_MODE:
        logger.info(f"[snowflake][MOCK] write_bronze_presage: {len(frames)} rows skipped")
        return len(frames)

    if not frames:
        return 0

    rows = []
    for f in frames:
        if hasattr(f, "timestamp_sec"):
            ts = f.timestamp_sec
            d = {
                "frustration":    f.frustration,
                "confusion":      f.confusion,
                "delight":        f.delight,
                "boredom":        f.boredom,
                "surprise":       f.surprise,
                "engagement":     f.engagement,
                "presage_hr":     f.heart_rate,
                "breathing_rate": f.breathing_rate,
            }
        else:
            ts = float(f.get("timestamp_sec", f.get("timestamp", 0.0)))
            d = {k: float(f.get(k, 0.0)) for k in
                 ["frustration", "confusion", "delight", "boredom", "surprise", "engagement"]}
            d["presage_hr"]     = float(f.get("heart_rate", f.get("hr", 0.0)))
            d["breathing_rate"] = float(f.get("breathing_rate", 0.0))
            d["gaze_x"]         = float(f.get("gaze_x", 0.5))
            d["gaze_y"]         = float(f.get("gaze_y", 0.5))
            d["gaze_confidence"] = float(f.get("gaze_confidence", 0.0))
            d["head_pitch"]     = float(f.get("head_pitch", 0.0))
            d["head_yaw"]       = float(f.get("head_yaw", 0.0))
            d["head_roll"]      = float(f.get("head_roll", 0.0))

        rows.append((
            session_id, project_id, ts,
            d["frustration"], d["confusion"], d["delight"],
            d["boredom"], d["surprise"], d["engagement"],
            d["presage_hr"], d["breathing_rate"],
            d["gaze_x"], d["gaze_y"], d["gaze_confidence"],
            d["head_pitch"], d["head_yaw"], d["head_roll"],
            json.dumps(d),
        ))

    close_after = conn is None
    if conn is None:
        conn = _get_connection()

    try:
        ensure_tables(conn)
        sql = """
            INSERT INTO BRONZE_PRESAGE
            (session_id, project_id, timestamp_sec,
             frustration, confusion, delight, boredom, surprise, engagement,
             presage_hr, breathing_rate,
             gaze_x, gaze_y, gaze_confidence,
             head_pitch, head_yaw, head_roll,
             raw_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s))
        """
        _executemany(conn, sql, rows)
        logger.info(f"[snowflake] BRONZE_PRESAGE: inserted {len(rows)} rows for session {session_id}")
        return len(rows)
    finally:
        if close_after:
            conn.close()


def write_bronze_watch(
    session_id: str,
    project_id: str,
    readings: List[Any],
    conn=None,
) -> int:
    """Write raw Apple Watch readings to BRONZE_WATCH."""
    if MOCK_MODE:
        logger.info(f"[snowflake][MOCK] write_bronze_watch: {len(readings)} rows skipped")
        return len(readings)

    if not readings:
        return 0

    rows = []
    for r in readings:
        if hasattr(r, "timestamp_sec"):
            ts = r.timestamp_sec
            hr, hrv_r, hrv_s, mv = r.heart_rate, r.hrv_rmssd, r.hrv_sdnn, r.movement_variance
        else:
            ts = float(r.get("timestamp_sec", r.get("timestamp", 0.0)))
            hr = float(r.get("heart_rate", r.get("hr", 0.0)))
            hrv_r = float(r.get("hrv_rmssd", r.get("hrv", 0.0)))
            hrv_s = float(r.get("hrv_sdnn", 0.0))
            mv    = float(r.get("movement_variance", 0.0))
        rows.append((session_id, project_id, ts, hr, hrv_r, hrv_s, mv,
                     json.dumps({"hr": hr, "hrv_rmssd": hrv_r})))

    close_after = conn is None
    if conn is None:
        conn = _get_connection()

    try:
        ensure_tables(conn)
        sql = """
            INSERT INTO BRONZE_WATCH
            (session_id, project_id, timestamp_sec, hr, hrv_rmssd, hrv_sdnn, movement_var, raw_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s))
        """
        _executemany(conn, sql, rows)
        logger.info(f"[snowflake] BRONZE_WATCH: inserted {len(rows)} rows for session {session_id}")
        return len(rows)
    finally:
        if close_after:
            conn.close()


def write_bronze_chunks(
    session_id: str,
    project_id: str,
    chunk_results: List[ChunkResult],
    conn=None,
) -> int:
    """Write raw Gemini chunk analysis results to BRONZE_CHUNKS."""
    if MOCK_MODE:
        logger.info(f"[snowflake][MOCK] write_bronze_chunks: {len(chunk_results)} chunks skipped")
        return len(chunk_results)

    if not chunk_results:
        return 0

    rows = []
    for cr in chunk_results:
        raw = {
            "chunk_index":        cr.chunk_index,
            "end_state":          cr.end_state,
            "end_status":         cr.end_status,
            "cumulative_deaths":  cr.cumulative_deaths,
            "transitions":        [t.dict() for t in cr.transitions],
            "events":             [e.dict() for e in cr.events],
        }
        rows.append((
            session_id, project_id,
            cr.chunk_index,
            cr.time_range_sec[0], cr.time_range_sec[1],
            cr.end_state, cr.end_status, cr.cumulative_deaths,
            json.dumps(raw),
        ))

    close_after = conn is None
    if conn is None:
        conn = _get_connection()

    try:
        ensure_tables(conn)
        sql = """
            INSERT INTO BRONZE_CHUNKS
            (session_id, project_id, chunk_index, chunk_start_sec, chunk_end_sec,
             end_state, end_status, cumulative_deaths, raw_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s))
        """
        _executemany(conn, sql, rows)
        logger.info(f"[snowflake] BRONZE_CHUNKS: inserted {len(rows)} chunks for session {session_id}")
        return len(rows)
    finally:
        if close_after:
            conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# SILVER write
# ─────────────────────────────────────────────────────────────────────────────

def write_silver(
    session_id: str,
    project_id: str,
    fused_df: pd.DataFrame,
    conn=None,
) -> int:
    """
    Write the clean 1-Hz fused DataFrame to SILVER_FUSED.
    Each row = 1 second of gameplay with all emotion + biometric columns.
    """
    if MOCK_MODE:
        logger.info(f"[snowflake][MOCK] write_silver: {len(fused_df)} rows skipped")
        return len(fused_df)

    if fused_df.empty:
        return 0

    rows = [
        (
            session_id, project_id,
            int(row["t"]),
            str(row["state"]),
            int(row["time_in_state_sec"]),
            float(row["frustration"]),
            float(row["confusion"]),
            float(row["delight"]),
            float(row["boredom"]),
            float(row["surprise"]),
            float(row["engagement"]),
            float(row["hr"]),
            float(row["hrv_rmssd"]),
            float(row["hrv_sdnn"]),
            float(row["presage_hr"]),
            float(row["breathing_rate"]),
            float(row["intent_delta"]),
            str(row["dominant_emotion"]),
            float(row["data_quality"]),
        )
        for _, row in fused_df.iterrows()
    ]

    close_after = conn is None
    if conn is None:
        conn = _get_connection()

    try:
        ensure_tables(conn)
        sql = """
            INSERT INTO SILVER_FUSED
            (session_id, project_id, t, state, time_in_state_sec,
             frustration, confusion, delight, boredom, surprise, engagement,
             hr, hrv_rmssd, hrv_sdnn, presage_hr, breathing_rate,
             intent_delta, dominant_emotion, data_quality)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s)
        """
        _executemany(conn, sql, rows)
        logger.info(f"[snowflake] SILVER_FUSED: inserted {len(rows)} rows for session {session_id}")
        return len(rows)
    finally:
        if close_after:
            conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# GOLD writes — verdict logic
# ─────────────────────────────────────────────────────────────────────────────

def _compute_verdict(
    actual_avg_score: float,
    intent_delta_avg: float,
    acceptable_range: tuple,
) -> str:
    """
    PASS  — actual score is within the acceptable range
    WARN  — outside range but delta < WARN_DELTA_THRESHOLD
    FAIL  — outside range and delta >= WARN_DELTA_THRESHOLD
    """
    lo, hi = acceptable_range
    if lo <= actual_avg_score <= hi:
        return "PASS"
    if intent_delta_avg < WARN_DELTA_THRESHOLD:
        return "WARN"
    return "FAIL"


def _compute_playtest_health_score(
    state_verdicts: List[Dict],
) -> float:
    """
    Weighted health score 0–100.
    PASS = 100, WARN = 60, FAIL = 0 per state.
    States without data count as WARN.
    """
    if not state_verdicts:
        return 0.0
    score_map = {"PASS": 100.0, "WARN": 60.0, "FAIL": 0.0, "NO_DATA": 60.0}
    scores = [score_map.get(v["verdict"], 60.0) for v in state_verdicts]
    return round(sum(scores) / len(scores), 1)


def write_gold(
    session_id: str,
    project_id: str,
    fused_df: pd.DataFrame,
    dfa_config: Optional[DFAConfig] = None,
    conn=None,
) -> Dict:
    """
    Aggregate SILVER_FUSED data into per-state verdicts and a session summary,
    then write to GOLD_STATE_VERDICTS and GOLD_SESSION_SUMMARY.

    Returns a dict with the computed verdicts and health score so the
    FastAPI backend can immediately return it to the client.
    """
    if MOCK_MODE:
        logger.info(f"[snowflake][MOCK] write_gold: skipped for session {session_id}")
        return _mock_gold_result(session_id, fused_df, dfa_config)

    if fused_df.empty:
        logger.warning(f"[snowflake] write_gold: empty DataFrame for session {session_id}")
        return {"health_score": 0.0, "state_verdicts": [], "session_id": session_id}

    state_verdicts = _build_state_verdicts(fused_df, dfa_config)
    health_score   = _compute_playtest_health_score(state_verdicts)

    close_after = conn is None
    if conn is None:
        conn = _get_connection()

    try:
        ensure_tables(conn)

        # Write per-state verdicts
        verdict_rows = [
            (
                session_id, project_id,
                v["state_name"],
                v["intended_emotion"],
                v["intended_score"],
                v["acceptable_range"][0],
                v["acceptable_range"][1],
                v["actual_avg_score"],
                v["intent_delta_avg"],
                v["actual_duration_sec"],
                v["expected_duration_sec"],
                v["duration_delta_sec"],
                v["verdict"],
                v["dominant_emotion"],
            )
            for v in state_verdicts
        ]
        if verdict_rows:
            _executemany(conn, """
                INSERT INTO GOLD_STATE_VERDICTS
                (session_id, project_id, state_name, intended_emotion, intended_score,
                 acceptable_range_low, acceptable_range_high,
                 actual_avg_score, intent_delta_avg,
                 actual_duration_sec, expected_duration_sec, duration_delta_sec,
                 verdict, dominant_emotion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, verdict_rows)

        # Write session summary
        total_deaths = int(fused_df.get("total_deaths", pd.Series([0])).sum()) \
            if "total_deaths" in fused_df.columns else 0
        dominant = fused_df["dominant_emotion"].mode()[0] if "dominant_emotion" in fused_df.columns else "unknown"

        _execute(conn, """
            INSERT INTO GOLD_SESSION_SUMMARY
            (session_id, project_id, total_duration_sec, health_score,
             pass_count, warn_count, fail_count, total_deaths,
             dominant_emotion, state_summary_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s))
        """, (
            session_id, project_id,
            len(fused_df),
            health_score,
            sum(1 for v in state_verdicts if v["verdict"] == "PASS"),
            sum(1 for v in state_verdicts if v["verdict"] == "WARN"),
            sum(1 for v in state_verdicts if v["verdict"] == "FAIL"),
            total_deaths,
            dominant,
            json.dumps(state_verdicts),
        ))

        logger.info(
            f"[snowflake] GOLD written for session {session_id} "
            f"health_score={health_score} verdicts={[v['verdict'] for v in state_verdicts]}"
        )

        return {
            "session_id":    session_id,
            "health_score":  health_score,
            "state_verdicts": state_verdicts,
        }
    finally:
        if close_after:
            conn.close()


def _build_state_verdicts(
    fused_df: pd.DataFrame,
    dfa_config: Optional[DFAConfig],
) -> List[Dict]:
    """
    Group fused_df by state, compute average emotion scores,
    compare against DFA intent, return list of verdict dicts.
    """
    if dfa_config is None or not dfa_config.states:
        # No DFA config — just return per-state duration summaries
        verdicts = []
        for state_name, group in fused_df.groupby("state"):
            verdicts.append({
                "state_name":          str(state_name),
                "intended_emotion":    "unknown",
                "intended_score":      0.0,
                "acceptable_range":    (0.0, 1.0),
                "actual_avg_score":    0.0,
                "intent_delta_avg":    float(group["intent_delta"].mean()),
                "actual_duration_sec": len(group),
                "expected_duration_sec": 0.0,
                "duration_delta_sec":  0.0,
                "verdict":             "NO_DATA",
                "dominant_emotion":    str(group["dominant_emotion"].mode()[0]) if len(group) > 0 else "unknown",
            })
        return verdicts

    # Build DFA lookup
    dfa_lookup = {s.name: s for s in dfa_config.states}
    verdicts = []

    for state_name, group in fused_df.groupby("state"):
        dfa_state = dfa_lookup.get(str(state_name))
        if dfa_state is None:
            continue  # skip states not in DFA (e.g. 'unknown')

        emotion_col = EMOTION_COLUMN_MAP.get(dfa_state.intended_emotion.lower(), "frustration")
        intended_score = (dfa_state.acceptable_range[0] + dfa_state.acceptable_range[1]) / 2.0
        actual_avg = float(group[emotion_col].mean()) if emotion_col in group.columns else 0.0
        delta_avg  = float(group["intent_delta"].mean())
        dom_emotion = str(group["dominant_emotion"].mode()[0]) if len(group) > 0 else "unknown"

        verdict = _compute_verdict(actual_avg, delta_avg, tuple(dfa_state.acceptable_range))

        verdicts.append({
            "state_name":          str(state_name),
            "intended_emotion":    dfa_state.intended_emotion,
            "intended_score":      round(intended_score, 3),
            "acceptable_range":    tuple(dfa_state.acceptable_range),
            "actual_avg_score":    round(actual_avg, 4),
            "intent_delta_avg":    round(delta_avg, 4),
            "actual_duration_sec": len(group),
            "expected_duration_sec": dfa_state.expected_duration_sec,
            "duration_delta_sec":  round(len(group) - dfa_state.expected_duration_sec, 1),
            "verdict":             verdict,
            "dominant_emotion":    dom_emotion,
        })

    return verdicts


def _mock_gold_result(
    session_id: str,
    fused_df: pd.DataFrame,
    dfa_config: Optional[DFAConfig],
) -> Dict:
    """Returns a mock Gold result dict identical in shape to the real one."""
    state_verdicts = _build_state_verdicts(fused_df, dfa_config)
    health_score   = _compute_playtest_health_score(state_verdicts)
    logger.info(
        f"[snowflake][MOCK] gold computed: session={session_id} "
        f"health_score={health_score} verdicts={[v['verdict'] for v in state_verdicts]}"
    )
    return {
        "session_id":     session_id,
        "health_score":   health_score,
        "state_verdicts": state_verdicts,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: write all three layers in one call
# ─────────────────────────────────────────────────────────────────────────────

def write_all(
    session_id: str,
    project_id: str,
    presage_frames: List[Any],
    watch_readings: List[Any],
    chunk_results: List[ChunkResult],
    fused_df: pd.DataFrame,
    dfa_config: Optional[DFAConfig] = None,
) -> Dict:
    """
    Write Bronze + Silver + Gold in a single connection for efficiency.
    Returns the Gold result dict (health_score + state_verdicts).
    """
    if MOCK_MODE:
        logger.info(f"[snowflake][MOCK] write_all for session {session_id}")
        write_bronze_presage(session_id, project_id, presage_frames)
        write_bronze_watch(session_id, project_id, watch_readings)
        write_bronze_chunks(session_id, project_id, chunk_results)
        write_silver(session_id, project_id, fused_df)
        return write_gold(session_id, project_id, fused_df, dfa_config)

    # Real mode: reuse a single connection for all writes
    conn = _get_connection()
    try:
        ensure_tables(conn)
        write_bronze_presage(session_id, project_id, presage_frames, conn=conn)
        write_bronze_watch(session_id, project_id, watch_readings, conn=conn)
        write_bronze_chunks(session_id, project_id, chunk_results, conn=conn)
        write_silver(session_id, project_id, fused_df, conn=conn)
        result = write_gold(session_id, project_id, fused_df, dfa_config, conn=conn)
        return result
    finally:
        conn.close()
