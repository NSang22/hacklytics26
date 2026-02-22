import json
import os
from typing import Optional

import snowflake.connector
from snowflake.connector import DictCursor


class SnowflakeClient:
    def __init__(
        self,
        account: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: str = None,
        schema: str = None,
        warehouse: str = None,
        role: Optional[str] = None,
    ):
        self._conn_params = {
            "account":   account   or os.environ["SNOWFLAKE_ACCOUNT"],
            "user":      user      or os.environ["SNOWFLAKE_USER"],
            "password":  password  or os.environ["SNOWFLAKE_PASSWORD"],
            "database":  database  or os.environ.get("SNOWFLAKE_DATABASE", "PATCHLAB_DB"),
            "schema":    schema    or os.environ.get("SNOWFLAKE_SCHEMA",   "PATCHLAB_SCHEMA"),
            "warehouse": warehouse or os.environ.get("SNOWFLAKE_WAREHOUSE", "PATCHLAB_WH"),
        }
        resolved_role = role or os.environ.get("SNOWFLAKE_ROLE")
        if resolved_role:
            self._conn_params["role"] = resolved_role
        self._conn = None

    def connect(self) -> "SnowflakeClient":
        self._conn = snowflake.connector.connect(**self._conn_params)
        return self

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "SnowflakeClient":
        return self.connect()

    def __exit__(self, *_):
        self.close()

    def _execute(self, sql: str, params=None, fetch: bool = False):
        cur = self._conn.cursor(DictCursor)
        cur.execute(sql, params)
        if fetch:
            rows = cur.fetchall()
            cur.close()
            return rows
        cur.close()

    def _executemany(self, sql: str, rows: list):
        cur = self._conn.cursor()
        cur.executemany(sql, rows)
        cur.close()

    def create_schema(self):
        statements = [
            """
            CREATE TABLE IF NOT EXISTS bronze_presage_emotions (
                id              STRING        DEFAULT UUID_STRING(),
                session_id      STRING        NOT NULL,
                project_id      STRING        NOT NULL,
                recorded_at     TIMESTAMP_NTZ NOT NULL,
                frustration     FLOAT,
                confusion       FLOAT,
                delight         FLOAT,
                boredom         FLOAT,
                surprise        FLOAT,
                engagement      FLOAT,
                camera_hr       FLOAT,
                camera_br       FLOAT,
                raw_payload     VARIANT,
                ingested_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bronze_gemini_chunks (
                id              STRING        DEFAULT UUID_STRING(),
                session_id      STRING        NOT NULL,
                project_id      STRING        NOT NULL,
                chunk_index     INTEGER       NOT NULL,
                chunk_start_sec FLOAT         NOT NULL,
                chunk_end_sec   FLOAT         NOT NULL,
                dfa_state       STRING,
                transitions     VARIANT,
                events          VARIANT,
                behavior        STRING,
                summary         STRING,
                raw_payload     VARIANT,
                ingested_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bronze_watch_biometrics (
                id              STRING        DEFAULT UUID_STRING(),
                session_id      STRING        NOT NULL,
                project_id      STRING        NOT NULL,
                recorded_at     TIMESTAMP_NTZ NOT NULL,
                heart_rate      FLOAT,
                hrv             FLOAT,
                raw_payload     VARIANT,
                ingested_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS silver_fused_timeline (
                id           STRING        DEFAULT UUID_STRING(),
                session_id   STRING        NOT NULL,
                project_id   STRING        NOT NULL,
                t_second     INTEGER       NOT NULL,
                dfa_state    STRING,
                frustration  FLOAT,
                confusion    FLOAT,
                delight      FLOAT,
                boredom      FLOAT,
                surprise     FLOAT,
                engagement   FLOAT,
                camera_hr    FLOAT,
                watch_hr     FLOAT,
                watch_hrv    FLOAT,
                data_quality FLOAT,
                created_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS gold_state_verdicts (
                id                    STRING        DEFAULT UUID_STRING(),
                session_id            STRING        NOT NULL,
                project_id            STRING        NOT NULL,
                dfa_state             STRING        NOT NULL,
                intended_emotion      STRING,
                actual_emotion        STRING,
                intended_score_avg    FLOAT,
                acceptable_min        FLOAT,
                acceptable_max        FLOAT,
                verdict               STRING,
                deviation_score       FLOAT,
                actual_duration_sec   FLOAT,
                expected_duration_sec FLOAT,
                time_delta_sec        FLOAT,
                computed_at           TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS gold_session_health (
                id                 STRING        DEFAULT UUID_STRING(),
                session_id         STRING        NOT NULL,
                project_id         STRING        NOT NULL,
                tester_id          STRING,
                health_score       FLOAT         NOT NULL,
                pass_count         INTEGER,
                warn_count         INTEGER,
                fail_count         INTEGER,
                total_duration_sec FLOAT,
                computed_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS gold_cross_session_aggregates (
                id                 STRING        DEFAULT UUID_STRING(),
                project_id         STRING        NOT NULL,
                dfa_state          STRING        NOT NULL,
                num_sessions       INTEGER,
                avg_frustration    FLOAT,
                avg_confusion      FLOAT,
                avg_delight        FLOAT,
                avg_heart_rate     FLOAT,
                pass_rate          FLOAT,
                fail_rate          FLOAT,
                avg_time_delta_sec FLOAT,
                computed_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
            """,
        ]
        for stmt in statements:
            self._execute(stmt)

    def insert_presage_batch(self, session_id: str, project_id: str, readings: list[dict]):
        sql = """
            INSERT INTO bronze_presage_emotions
                (session_id, project_id, recorded_at,
                 frustration, confusion, delight, boredom, surprise, engagement,
                 camera_hr, camera_br, raw_payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s))
        """
        rows = [
            (
                session_id, project_id, r["recorded_at"],
                r.get("frustration"), r.get("confusion"), r.get("delight"),
                r.get("boredom"), r.get("surprise"), r.get("engagement"),
                r.get("camera_hr"), r.get("camera_br"), json.dumps(r),
            )
            for r in readings
        ]
        self._executemany(sql, rows)

    def insert_gemini_chunk(self, session_id: str, project_id: str, chunk: dict):
        sql = """
            INSERT INTO bronze_gemini_chunks
                (session_id, project_id, chunk_index, chunk_start_sec, chunk_end_sec,
                 dfa_state, transitions, events, behavior, summary, raw_payload)
            VALUES (%s, %s, %s, %s, %s, %s,
                    PARSE_JSON(%s), PARSE_JSON(%s),
                    %s, %s, PARSE_JSON(%s))
        """
        self._execute(sql, (
            session_id, project_id,
            chunk["chunk_index"], chunk["chunk_start_sec"], chunk["chunk_end_sec"],
            chunk.get("dfa_state"),
            json.dumps(chunk.get("transitions", [])),
            json.dumps(chunk.get("events", [])),
            chunk.get("behavior"), chunk.get("summary"),
            json.dumps(chunk),
        ))

    def insert_watch_batch(self, session_id: str, project_id: str, readings: list[dict]):
        sql = """
            INSERT INTO bronze_watch_biometrics
                (session_id, project_id, recorded_at, heart_rate, hrv, raw_payload)
            VALUES (%s, %s, %s, %s, %s, PARSE_JSON(%s))
        """
        rows = [
            (
                session_id, project_id, r["recorded_at"],
                r.get("heart_rate"), r.get("hrv"), json.dumps(r),
            )
            for r in readings
        ]
        self._executemany(sql, rows)

    def insert_fused_timeline(self, session_id: str, project_id: str, rows: list[dict]):
        sql = """
            INSERT INTO silver_fused_timeline
                (session_id, project_id, t_second, dfa_state,
                 frustration, confusion, delight, boredom, surprise, engagement,
                 camera_hr, watch_hr, watch_hrv, data_quality)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        data = [
            (
                session_id, project_id, r["t_second"], r.get("dfa_state"),
                r.get("frustration"), r.get("confusion"), r.get("delight"),
                r.get("boredom"), r.get("surprise"), r.get("engagement"),
                r.get("camera_hr"), r.get("watch_hr"), r.get("watch_hrv"),
                r.get("data_quality", 1.0),
            )
            for r in rows
        ]
        self._executemany(sql, data)

    def insert_state_verdicts(self, session_id: str, project_id: str, verdicts: list[dict]):
        sql = """
            INSERT INTO gold_state_verdicts
                (session_id, project_id, dfa_state,
                 intended_emotion, actual_emotion,
                 intended_score_avg, acceptable_min, acceptable_max,
                 verdict, deviation_score,
                 actual_duration_sec, expected_duration_sec, time_delta_sec)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        rows = [
            (
                session_id, project_id, v["dfa_state"],
                v.get("intended_emotion"), v.get("actual_emotion"),
                v.get("intended_score_avg"), v.get("acceptable_min"), v.get("acceptable_max"),
                v.get("verdict"), v.get("deviation_score"),
                v.get("actual_duration_sec"), v.get("expected_duration_sec"), v.get("time_delta_sec"),
            )
            for v in verdicts
        ]
        self._executemany(sql, rows)

    def insert_session_health(self, session_id: str, project_id: str, health: dict):
        sql = """
            INSERT INTO gold_session_health
                (session_id, project_id, tester_id, health_score,
                 pass_count, warn_count, fail_count, total_duration_sec)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        self._execute(sql, (
            session_id, project_id, health.get("tester_id"), health["health_score"],
            health.get("pass_count"), health.get("warn_count"),
            health.get("fail_count"), health.get("total_duration_sec"),
        ))

    def refresh_cross_session_aggregates(self, project_id: str):
        self._execute(
            "DELETE FROM gold_cross_session_aggregates WHERE project_id = %s",
            (project_id,),
        )
        self._execute(
            """
            INSERT INTO gold_cross_session_aggregates
                (project_id, dfa_state, num_sessions,
                 avg_frustration, avg_confusion, avg_delight, avg_heart_rate,
                 pass_rate, fail_rate, avg_time_delta_sec)
            SELECT
                f.project_id,
                f.dfa_state,
                COUNT(DISTINCT f.session_id)                    AS num_sessions,
                AVG(f.frustration)                              AS avg_frustration,
                AVG(f.confusion)                                AS avg_confusion,
                AVG(f.delight)                                  AS avg_delight,
                AVG(COALESCE(f.watch_hr, f.camera_hr))         AS avg_heart_rate,
                AVG(IFF(v.verdict = 'PASS', 1.0, 0.0))        AS pass_rate,
                AVG(IFF(v.verdict = 'FAIL', 1.0, 0.0))        AS fail_rate,
                AVG(v.time_delta_sec)                           AS avg_time_delta_sec
            FROM silver_fused_timeline f
            LEFT JOIN gold_state_verdicts v
                   ON v.session_id = f.session_id
                  AND v.dfa_state  = f.dfa_state
            WHERE f.project_id = %s
            GROUP BY f.project_id, f.dfa_state
            """,
            (project_id,),
        )

    def get_session_verdicts(self, session_id: str) -> list[dict]:
        return self._execute(
            "SELECT * FROM gold_state_verdicts WHERE session_id = %s ORDER BY computed_at",
            (session_id,),
            fetch=True,
        )

    def get_session_health(self, session_id: str) -> Optional[dict]:
        rows = self._execute(
            "SELECT * FROM gold_session_health WHERE session_id = %s",
            (session_id,),
            fetch=True,
        )
        return rows[0] if rows else None

    def get_fused_timeline(self, session_id: str) -> list[dict]:
        return self._execute(
            "SELECT * FROM silver_fused_timeline WHERE session_id = %s ORDER BY t_second",
            (session_id,),
            fetch=True,
        )

    def get_cross_session_heatmap(self, project_id: str) -> list[dict]:
        return self._execute(
            """
            SELECT dfa_state, avg_frustration, avg_heart_rate,
                   pass_rate, fail_rate, num_sessions
            FROM gold_cross_session_aggregates
            WHERE project_id = %s
            ORDER BY avg_frustration DESC
            """,
            (project_id,),
            fetch=True,
        )

    def get_time_delta_vs_confusion(self, project_id: str) -> list[dict]:
        return self._execute(
            """
            SELECT v.session_id, v.dfa_state,
                   v.time_delta_sec,
                   AVG(f.confusion) AS avg_confusion
            FROM gold_state_verdicts v
            JOIN silver_fused_timeline f
              ON f.session_id = v.session_id
             AND f.dfa_state  = v.dfa_state
            WHERE v.project_id = %s
            GROUP BY v.session_id, v.dfa_state, v.time_delta_sec
            ORDER BY v.time_delta_sec DESC
            """,
            (project_id,),
            fetch=True,
        )

    def get_all_sessions_for_project(self, project_id: str) -> list[dict]:
        return self._execute(
            "SELECT * FROM gold_session_health WHERE project_id = %s ORDER BY computed_at",
            (project_id,),
            fetch=True,
        )

    def run_raw_query(self, sql: str, params=None) -> list[dict]:
        return self._execute(sql, params, fetch=True)
