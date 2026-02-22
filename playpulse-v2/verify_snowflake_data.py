#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, '/Users/dan_the_man0005/projects/hacklytics26/playpulse-v2/backend')

from dotenv import load_dotenv
load_dotenv('/Users/dan_the_man0005/projects/hacklytics26/playpulse-v2/backend/.env')

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
print("SNOWFLAKE DATA VERIFICATION")
print("=" * 60)

# Check SILVER_FUSED
print("\n[SILVER_FUSED] Checking fused timeline data...")
cur.execute("SELECT COUNT(*), session_id FROM SILVER_FUSED GROUP BY session_id LIMIT 10")
results = cur.fetchall()
if results:
    print(f"  ✓ Found {len(results)} session(s) with fused data:")
    for count, session_id in results:
        print(f"    - {session_id}: {count} rows")
else:
    print("  ✗ No fused data found")

# Check GOLD_VERDICTS  
print("\n[GOLD_VERDICTS] Checking verdict data...")
cur.execute("SELECT session_id, state_name, verdict FROM GOLD_VERDICTS LIMIT 10")
results = cur.fetchall()
if results:
    print(f"  ✓ Found {len(results)} verdict(s):")
    for session_id, state_name, verdict in results:
        print(f"    - {session_id} / {state_name}: {verdict}")
else:
    print("  ✗ No verdicts found")

# Check GOLD_HEALTH_SCORES
print("\n[GOLD_HEALTH_SCORES] Checking health scores...")
cur.execute("SELECT session_id, health_score FROM GOLD_HEALTH_SCORES LIMIT 10")
results = cur.fetchall()
if results:
    print(f"  ✓ Found {len(results)} health score(s):")
    for session_id, health_score in results:
        print(f"    - {session_id}: {health_score}")
else:
    print("  ✗ No health scores found")

# Check BRONZE_GAMEPLAY_EVENTS
print("\n[BRONZE_GAMEPLAY_EVENTS] Checking gameplay events...")
cur.execute("SELECT COUNT(*), session_id FROM BRONZE_GAMEPLAY_EVENTS GROUP BY session_id LIMIT 10")
results = cur.fetchall()
if results:
    print(f"  ✓ Found {len(results)} session(s) with events:")
    for count, session_id in results:
        print(f"    - {session_id}: {count} events")
else:
    print("  ✗ No gameplay events found")

print("\n" + "=" * 60)
print("DATA VERIFICATION COMPLETE")
print("=" * 60)

conn.close()
