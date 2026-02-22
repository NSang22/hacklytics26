#!/usr/bin/env python3
"""
Check what data exists in Snowflake and group by project.
"""
import os
import sys
sys.path.insert(0, '/Users/dan_the_man0005/projects/hacklytics26/patchlab/backend')

from dotenv import load_dotenv
load_dotenv('/Users/dan_the_man0005/projects/hacklytics26/patchlab/backend/.env')

import snowflake.connector

conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    schema=os.getenv("SNOWFLAKE_SCHEMA"),
)

cur = conn.cursor()

print("=" * 60)
print("SNOWFLAKE DATA BY PROJECT")
print("=" * 60)

# Note: Our current schema doesn't store project_id in Snowflake tables
# We only have session_id. This is a problem!

print("\n[SILVER_FUSED] Sessions with fused data:")
cur.execute("SELECT DISTINCT session_id, COUNT(*) FROM SILVER_FUSED GROUP BY session_id")
sessions = cur.fetchall()
for session_id, count in sessions:
    print(f"  - Session {session_id}: {count} rows")

print("\n[GOLD_HEALTH_SCORES] Health scores by session:")
cur.execute("SELECT session_id, health_score FROM GOLD_HEALTH_SCORES")
scores = cur.fetchall()
for session_id, score in scores:
    print(f"  - Session {session_id}: {score}")

print("\n" + "=" * 60)
print("ISSUE: Snowflake tables don't have project_id column!")
print("We can only filter by session_id, not project_id")
print("=" * 60)

conn.close()
