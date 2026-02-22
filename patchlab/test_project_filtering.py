#!/usr/bin/env python3
"""Test project_id filtering across Snowflake tables."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from snowflake_client import SnowflakeClient
from config import MOCK_MODE


async def main():
    print("=== Testing Project ID Filtering ===\n")
    
    if MOCK_MODE is True or (isinstance(MOCK_MODE, str) and MOCK_MODE.lower() == "true"):
        print("❌ MOCK_MODE is enabled. Set MOCK_MODE=false in backend/.env")
        return
    
    client = SnowflakeClient()
    
    if not client.is_configured():
        print("❌ Snowflake not configured")
        return
    
    print("✅ Snowflake configured\n")
    
    # Step 1: Drop and recreate tables
    print("Step 1: Recreating tables with project_id column...")
    conn = client._get_connection()
    cursor = conn.cursor()
    
    tables = ["BRONZE_GAMEPLAY_EVENTS", "SILVER_FUSED", "GOLD_VERDICTS", "GOLD_HEALTH_SCORES"]
    for table in tables:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"  - Dropped {table}")
        except Exception as e:
            print(f"  ⚠️  Error dropping {table}: {e}")
    
    # Force recreation of tables with new schema
    client._ensure_tables()
    print("✅ Tables recreated with project_id column\n")
    
    # Step 2: Insert test data for two projects
    print("Step 2: Inserting test data for two projects...")
    
    # Project A - session 1
    fused_a1 = [
        {"t": 0, "state": "tutorial", "time_in_state_sec": 5, "frustration": 0.2, "confusion": 0.3,
         "delight": 0.7, "boredom": 0.1, "surprise": 0.4, "engagement": 0.8,
         "hr": 75.0, "hrv_rmssd": 40.0, "hrv_sdnn": 50.0,
         "intent_delta": 0.05, "dominant_emotion": "delight", "data_quality": 0.95}
    ]
    await client.store_fused_rows("session_a1", fused_a1, "project_a")
    
    verdicts_a1 = [
        {"state_name": "tutorial", "intended_emotion": "delight", "verdict": "PASS",
         "intent_delta_avg": 0.05, "actual_duration_sec": 5, "dominant_emotion": "delight",
         "raw_json": "{}"}
    ]
    await client.store_verdicts("session_a1", verdicts_a1, "project_a")
    
    await client.store_health_score("session_a1", 0.92, "project_a")
    print("  ✓ Project A, Session 1")
    
    # Project B - session 1
    fused_b1 = [
        {"t": 0, "state": "tutorial", "time_in_state_sec": 8, "frustration": 0.8, "confusion": 0.9,
         "delight": 0.1, "boredom": 0.7, "surprise": 0.2, "engagement": 0.3,
         "hr": 95.0, "hrv_rmssd": 25.0, "hrv_sdnn": 30.0,
         "intent_delta": -0.6, "dominant_emotion": "frustration", "data_quality": 0.88}
    ]
    await client.store_fused_rows("session_b1", fused_b1, "project_b")
    
    verdicts_b1 = [
        {"state_name": "tutorial", "intended_emotion": "delight", "verdict": "FAIL",
         "intent_delta_avg": -0.6, "actual_duration_sec": 8, "dominant_emotion": "frustration",
         "raw_json": "{}"}
    ]
    await client.store_verdicts("session_b1", verdicts_b1, "project_b")
    
    await client.store_health_score("session_b1", 0.35, "project_b")
    print("  ✓ Project B, Session 1\n")
    
    # Step 3: Query by project_id
    print("Step 3: Querying data by project_id...\n")
    
    # Query Project A
    print("Project A Results:")
    sessions_a = await client.get_project_sessions("project_a")
    print(f"  - Sessions: {len(sessions_a)}")
    
    verdicts_a = await client.get_project_verdicts("project_a")
    print(f"  - Verdicts: {len(verdicts_a)}")
    if verdicts_a:
        print(f"    Verdict: {verdicts_a[0]['VERDICT']} (intent_delta: {verdicts_a[0]['INTENT_DELTA_AVG']:.2f})")
    
    health_a = await client.get_project_health_scores("project_a")
    print(f"  - Health Scores: {len(health_a)}")
    if health_a:
        print(f"    Health: {health_a[0]['HEALTH_SCORE']:.2f}\n")
    
    # Query Project B
    print("Project B Results:")
    sessions_b = await client.get_project_sessions("project_b")
    print(f"  - Sessions: {len(sessions_b)}")
    
    verdicts_b = await client.get_project_verdicts("project_b")
    print(f"  - Verdicts: {len(verdicts_b)}")
    if verdicts_b:
        print(f"    Verdict: {verdicts_b[0]['VERDICT']} (intent_delta: {verdicts_b[0]['INTENT_DELTA_AVG']:.2f})")
    
    health_b = await client.get_project_health_scores("project_b")
    print(f"  - Health Scores: {len(health_b)}")
    if health_b:
        print(f"    Health: {health_b[0]['HEALTH_SCORE']:.2f}\n")
    
    # Step 4: Verify data isolation
    print("Step 4: Verifying data isolation...")
    if len(sessions_a) == 1 and len(sessions_b) == 1:
        print("  ✅ Each project has exactly 1 session (isolated)")
    else:
        print(f"  ❌ Unexpected session counts: A={len(sessions_a)}, B={len(sessions_b)}")
    
    if verdicts_a and verdicts_b:
        if verdicts_a[0]['VERDICT'] == 'PASS' and verdicts_b[0]['VERDICT'] == 'FAIL':
            print("  ✅ Verdicts are different (isolated)")
        else:
            print(f"  ❌ Unexpected verdicts: A={verdicts_a[0]['VERDICT']}, B={verdicts_b[0]['VERDICT']}")
    
    if health_a and health_b:
        if health_a[0]['HEALTH_SCORE'] > 0.9 and health_b[0]['HEALTH_SCORE'] < 0.5:
            print("  ✅ Health scores are different (isolated)")
        else:
            print(f"  ❌ Unexpected health scores: A={health_a[0]['HEALTH_SCORE']:.2f}, B={health_b[0]['HEALTH_SCORE']:.2f}")
    
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
