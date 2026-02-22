# Project ID Implementation Summary

## Overview
Successfully implemented project-level data organization and filtering across the entire PlayPulse data pipeline. All Snowflake tables now include a `project_id` column, enabling complete data isolation between projects.

## Changes Made

### 1. Snowflake Schema Updates
**File:** `backend/snowflake_client.py`

#### Added `project_id` column to all tables:
- `BRONZE_GAMEPLAY_EVENTS` - Raw gameplay events
- `SILVER_FUSED` - 1-second fused timelines
- `GOLD_VERDICTS` - Per-state verdict cards
- `GOLD_HEALTH_SCORES` - Overall health scores

#### Updated all store methods:
- `store_gameplay_events(session_id, events, project_id="")`
- `store_fused_rows(session_id, rows, project_id="")`
- `store_verdicts(session_id, verdicts, project_id="")`
- `store_health_score(session_id, score, project_id="")`

#### New query methods:
- `get_project_sessions(project_id)` - Retrieve all fused data for a project
- `get_project_verdicts(project_id)` - Retrieve all verdicts for a project
- `get_project_health_scores(project_id)` - Retrieve health scores for a project

#### New delete method:
- `delete_project_data(project_id)` - Delete all data for a project from all tables

#### Fixed GOLD_VERDICTS issue:
- Changed `raw_json` column from `VARIANT` to `VARCHAR(16777216)`
- Resolved "Invalid expression PARSE_JSON" error in VALUES clause
- JSON is now stored as a string (no parsing needed)

### 2. Backend API Updates
**File:** `backend/main.py`

#### Updated all snowflake.store_*() calls:
All calls in the `finalize_session()` and chunk processing now pass `s["project_id"]`:
```python
snowflake.store_gameplay_events(..., project_id=s["project_id"])
snowflake.store_fused_rows(session_id, fused_dicts, s["project_id"])
snowflake.store_verdicts(session_id, verdict_dicts, s["project_id"])
snowflake.store_health_score(session_id, health, s["project_id"])
```

#### New endpoint:
- `DELETE /v1/projects/{project_id}/data` - Delete all data for a project

### 3. Sphinx Query Engine Updates
**File:** `backend/sphinx_client.py`

#### Updated schema description:
- All table schemas now show `project_id VARCHAR` as first column
- Changed `raw_json VARIANT` → `raw_json VARCHAR` in GOLD_VERDICTS

#### Enhanced filtering:
Both `_query_sphinx_cli()` and `_query_gemini()` now:
- Accept `project_id` parameter
- Generate SQL with `WHERE project_id = '...'` clause
- Combine with session_id filtering when both provided
- Ensures all analytics are scoped to the correct project

Example generated WHERE clause:
```sql
WHERE project_id = 'abc123' AND session_id IN ('session1', 'session2')
```

## Testing

### Test Results
Created and ran `test_project_filtering.py`:

**Step 1:** Dropped old tables and recreated with new schema ✅
- All 4 tables now have `project_id VARCHAR(64)` column

**Step 2:** Inserted test data for two projects ✅
- Project A: 1 session, PASS verdict, health 0.92
- Project B: 1 session, FAIL verdict, health 0.35

**Step 3:** Queried data by project_id ✅
- Project A returned only its own data
- Project B returned only its own data

**Step 4:** Verified data isolation ✅
- Each project has exactly 1 session
- Verdicts are different (PASS vs FAIL)
- Health scores are different (0.92 vs 0.35)

## Usage

### Creating a Project with Sessions
```python
# Create project (automatic in UI)
project_id = "my_game_v1"

# Create session (links to project)
session = {
    "id": "session_abc",
    "project_id": project_id,
    "tester_name": "John Doe"
}

# Data automatically tagged with project_id during finalization
```

### Querying Project Data
```python
from backend.snowflake_client import SnowflakeClient

client = SnowflakeClient()

# Get all sessions for a project
sessions = await client.get_project_sessions("my_game_v1")

# Get verdicts for a project
verdicts = await client.get_project_verdicts("my_game_v1")

# Get health scores for a project
health = await client.get_project_health_scores("my_game_v1")
```

### Deleting Project Data
```bash
# Via API
curl -X DELETE http://localhost:8000/v1/projects/my_game_v1/data

# Response:
{
  "project_id": "my_game_v1",
  "deleted": {
    "BRONZE_GAMEPLAY_EVENTS": 42,
    "SILVER_FUSED": 156,
    "GOLD_VERDICTS": 5,
    "GOLD_HEALTH_SCORES": 3
  }
}
```

### Sphinx Analytics (Project-Scoped)
All Sphinx queries automatically filter by project_id when provided:

```python
from backend.sphinx_client import SphinxClient

sphinx = SphinxClient()

# Query scoped to project
result = await sphinx.query(
    question="What was the average frustration during the tutorial?",
    project_id="my_game_v1",
    session_ids=None  # All sessions in project
)

# Generated SQL will include: WHERE project_id = 'my_game_v1'
```

## Benefits

1. **Data Isolation**: Each project's data is completely separate
   - No cross-contamination between test runs
   - Clean analytics per game/version

2. **Easy Cleanup**: Delete all data for a project with one call
   - Remove old test data
   - Clean up failed experiments

3. **Scoped Analytics**: Sphinx queries automatically filter by project
   - Compare performance across versions
   - Track improvements over time

4. **Multi-Project Support**: Run multiple games/versions simultaneously
   - Different games in parallel
   - A/B testing different versions

## Migration Notes

### Existing Data (Pre-Migration)
Old data in Snowflake (before project_id was added) will have `NULL` project_id. 

To clean up:
```bash
# Run test to recreate tables with new schema
python test_project_filtering.py

# Or manually drop old tables and restart backend
# Tables will auto-recreate with new schema
```

### New Sessions
All new sessions created after this update will automatically be tagged with `project_id` from the parent project.

## Next Steps

1. **Frontend Integration**: Update UI to show project-scoped analytics
2. **Cross-Project Comparison**: Add endpoints to compare metrics across projects
3. **Project Metadata**: Store project creation time, description, tags in Snowflake
4. **Session Filtering**: Add UI to filter sessions by project before querying

## Files Modified

- `backend/snowflake_client.py` - Schema, store methods, query methods, delete method
- `backend/main.py` - Updated all snowflake.store_*() calls, added DELETE endpoint
- `backend/sphinx_client.py` - Updated schema description, added project_id filtering
- `test_project_filtering.py` - Created comprehensive test suite
