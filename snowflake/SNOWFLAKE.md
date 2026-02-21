# PlayPulse — Snowflake Data Warehouse

## Overview

PlayPulse uses a **medallion architecture** (Bronze → Silver → Gold) to store and aggregate playtest telemetry across three sensor sources: Presage (facial emotions), Gemini (gameplay video analysis), and Apple Watch (heart rate / HRV).

---

## Medallion Architecture — Concrete Walkthrough

### The scenario
A tester plays the demo game for **120 seconds**. The game has 5 DFA states. Here's exactly what flows into Snowflake and how it transforms at each layer.

---

### BRONZE — Raw data, exactly as it arrived

Think of Bronze as an audit log. Data goes in and is never changed. Three tables, one per source.

#### `bronze_presage_emotions`
Presage fires ~10 readings per second. For a 120-second session that's **~1,200 rows**.

| session_id | recorded_at | frustration | confusion | delight | engagement | camera_hr |
|---|---|---|---|---|---|---|
| sess_abc | 2026-02-21 14:00:00.000 | 0.12 | 0.08 | 0.71 | 0.80 | 72.1 |
| sess_abc | 2026-02-21 14:00:00.100 | 0.13 | 0.09 | 0.70 | 0.81 | 72.3 |
| sess_abc | 2026-02-21 14:00:00.200 | 0.11 | 0.10 | 0.72 | 0.79 | 72.0 |
| ... | ... | ... | ... | ... | ... | ... |

#### `bronze_gemini_chunks`
The gameplay video is split into 15-second chunks. Gemini analyzes each chunk as it uploads. For a 120-second session that's **8 rows** (one per chunk).

| session_id | chunk_index | chunk_start_sec | chunk_end_sec | dfa_state | behavior | summary |
|---|---|---|---|---|---|---|
| sess_abc | 0 | 0 | 15 | tutorial | progressing | Player learned controls, picked up key |
| sess_abc | 1 | 15 | 30 | tutorial | progressing | Player opened door, transitioning to puzzle |
| sess_abc | 2 | 30 | 45 | puzzle_room | stuck | Player hit the hidden wall 3 times, stood still for 8s |
| sess_abc | 3 | 45 | 60 | puzzle_room | stuck | Player still confused, backtracking |
| sess_abc | 4 | 60 | 75 | puzzle_room | progressing | Player found the hidden path |
| sess_abc | 5 | 75 | 90 | surprise_event | confused | Floor dropped, enemies appeared |
| sess_abc | 6 | 90 | 105 | gauntlet | dying | Player died twice on moving obstacles |
| sess_abc | 7 | 105 | 120 | victory | satisfied | YOU WIN screen displayed |

#### `bronze_watch_biometrics`
Apple Watch fires ~1 reading per second. For a 120-second session that's **~120 rows**.

| session_id | recorded_at | heart_rate | hrv |
|---|---|---|---|
| sess_abc | 2026-02-21 14:00:00 | 71 | 48.2 |
| sess_abc | 2026-02-21 14:00:01 | 72 | 47.9 |
| sess_abc | 2026-02-21 14:00:30 | 85 | 31.4 |
| ... | ... | ... | ... |

**Problem:** Three tables, three different time resolutions (100ms, 15s chunks, 1s). You can't query across them meaningfully yet.

---

### SILVER — Everything aligned to 1 row per second

The temporal fusion engine reads all three Bronze tables and produces exactly **120 rows** in `silver_fused_timeline` — one per second of gameplay.

How each source gets resampled:
- **Presage** (10 readings/sec → 1/sec): the 10 readings within each second are **averaged**
- **Gemini** (chunk result → every second): the DFA state is **forward-filled** — if Gemini says the player entered `puzzle_room` at t=30, then every row from t=30 through t=74 gets `dfa_state = "puzzle_room"`
- **Watch** (1/sec): already aligned, **copied directly**

| session_id | t_second | dfa_state | frustration | confusion | engagement | watch_hr | watch_hrv |
|---|---|---|---|---|---|---|---|
| sess_abc | 0 | tutorial | 0.12 | 0.09 | 0.80 | 71 | 48.2 |
| sess_abc | 1 | tutorial | 0.11 | 0.08 | 0.82 | 72 | 47.9 |
| sess_abc | 30 | puzzle_room | 0.31 | 0.52 | 0.60 | 85 | 31.4 |
| sess_abc | 45 | puzzle_room | 0.74 | 0.81 | 0.41 | 98 | 22.1 |
| sess_abc | 75 | surprise_event | 0.55 | 0.70 | 0.55 | 105 | 18.3 |
| sess_abc | 90 | gauntlet | 0.62 | 0.38 | 0.72 | 101 | 24.0 |
| sess_abc | 105 | victory | 0.08 | 0.04 | 0.90 | 88 | 40.1 |
| ... | ... | ... | ... | ... | ... | ... | ... |

Now you can ask: *"What was the player feeling at second 45?"* — one row answers it.

---

### GOLD — The answers the developer actually cares about

#### `gold_state_verdicts`
The verdict engine filters the Silver timeline by DFA state and compares against what the developer intended.

**Example for `puzzle_room`:**
- Developer said: intended emotion = `curious`, acceptable range = `[0.4, 0.8]`
- Silver rows where `dfa_state = "puzzle_room"` span t=30 to t=74 (44 seconds)
- Average `confusion` score across those 44 rows = **0.71** — and `confusion` was the dominant emotion, not `curious` (avg = 0.22)
- `curious` score 0.22 is below the acceptable minimum of 0.4 → **FAIL**
- Time delta: player spent 44s, developer expected 20s → time_delta = +24s

| session_id | dfa_state | intended_emotion | actual_emotion | intended_score_avg | verdict | deviation_score | time_delta_sec |
|---|---|---|---|---|---|---|---|
| sess_abc | tutorial | calm | calm | 0.74 | PASS | 0.05 | +2s |
| sess_abc | puzzle_room | curious | confused | 0.22 | FAIL | 0.78 | +24s |
| sess_abc | surprise_event | surprised | surprised | 0.68 | PASS | 0.12 | -1s |
| sess_abc | gauntlet | tense | tense | 0.55 | WARN | 0.32 | +8s |
| sess_abc | victory | satisfied | satisfied | 0.88 | PASS | 0.04 | 0s |

#### `gold_session_health`
Rolls all verdicts into a single Playtest Health Score.

| session_id | health_score | pass_count | warn_count | fail_count | total_duration_sec |
|---|---|---|---|---|---|
| sess_abc | 0.72 | 3 | 1 | 1 | 120 |

Health score formula: `(PASS×1.0 + WARN×0.5 + FAIL×0.0) / total_states` → `(3 + 0.5 + 0) / 5 = 0.72`

#### `gold_cross_session_aggregates`
After 5 testers have played, `refresh_cross_session_aggregates()` aggregates across all sessions.

| dfa_state | num_sessions | avg_frustration | avg_heart_rate | pass_rate | fail_rate |
|---|---|---|---|---|---|
| puzzle_room | 5 | 0.69 | 94.2 | 0.20 | 0.60 |
| tutorial | 5 | 0.10 | 73.1 | 1.00 | 0.00 |
| gauntlet | 5 | 0.58 | 99.7 | 0.40 | 0.20 |

This powers the **heatmap** (Query 1) and feeds directly into Sphinx queries.

---

## Tables Reference

| Layer | Table | Rows per session | Written by |
|---|---|---|---|
| Bronze | `bronze_presage_emotions` | ~1,200 (10/sec × 120s) | Presage integration |
| Bronze | `bronze_gemini_chunks` | ~8 (one per 15s chunk) | Chunk processor |
| Bronze | `bronze_watch_biometrics` | ~120 (1/sec) | Watch WebSocket handler |
| Silver | `silver_fused_timeline` | 120 (one per second) | Temporal fusion engine |
| Gold | `gold_state_verdicts` | 5 (one per DFA state) | Verdict engine |
| Gold | `gold_session_health` | 1 | Verdict engine |
| Gold | `gold_cross_session_aggregates` | 5 (recomputed each session) | `refresh_cross_session_aggregates()` |

---

## Environment Variables

```
SNOWFLAKE_ACCOUNT=     # e.g. abc12345.us-east-1
SNOWFLAKE_USER=        # your Snowflake username
SNOWFLAKE_PASSWORD=    # your Snowflake password
SNOWFLAKE_DATABASE=    # default: PLAYPULSE
SNOWFLAKE_SCHEMA=      # default: PUBLIC
SNOWFLAKE_WAREHOUSE=   # default: COMPUTE_WH
SNOWFLAKE_ROLE=        # optional
```

---

## Usage

```python
from snowFlakeClient import SnowflakeClient

# One-time setup
with SnowflakeClient() as sf:
    sf.create_schema()

# During a session — bronze writes happen as data arrives
with SnowflakeClient() as sf:
    sf.insert_presage_batch(session_id, project_id, presage_readings)
    sf.insert_gemini_chunk(session_id, project_id, chunk_result)
    sf.insert_watch_batch(session_id, project_id, watch_readings)

# After session ends — silver + gold
with SnowflakeClient() as sf:
    sf.insert_fused_timeline(session_id, project_id, fused_rows)
    sf.insert_state_verdicts(session_id, project_id, verdicts)
    sf.insert_session_health(session_id, project_id, health)
    sf.refresh_cross_session_aggregates(project_id)

# Dashboard reads
with SnowflakeClient() as sf:
    verdicts  = sf.get_session_verdicts(session_id)
    health    = sf.get_session_health(session_id)
    timeline  = sf.get_fused_timeline(session_id)
    heatmap   = sf.get_cross_session_heatmap(project_id)
    scatter   = sf.get_time_delta_vs_confusion(project_id)

# Sphinx-generated SQL
with SnowflakeClient() as sf:
    result = sf.run_raw_query(sphinx_generated_sql)
```
