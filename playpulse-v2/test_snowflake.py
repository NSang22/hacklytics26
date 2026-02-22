#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, '/Users/dan_the_man0005/projects/hacklytics26/playpulse-v2/backend')

from dotenv import load_dotenv
load_dotenv('/Users/dan_the_man0005/projects/hacklytics26/playpulse-v2/backend/.env')

print("Testing Snowflake connection...")
try:
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
    cur.execute("SELECT CURRENT_VERSION()")
    version = cur.fetchone()[0]
    print(f"✓ Connected to Snowflake successfully!")
    print(f"  Version: {version}")
    print(f"  Database: {os.getenv('SNOWFLAKE_DATABASE')}")
    print(f"  Schema: {os.getenv('SNOWFLAKE_SCHEMA')}")
    
    # List tables
    cur.execute("SHOW TABLES")
    tables = cur.fetchall()
    print(f"\n  Existing tables: {len(tables)}")
    if tables:
        for table in tables[:10]:
            print(f"    - {table[1]}")
    else:
        print("    (no tables yet - will be created on first write)")
    
    conn.close()
except Exception as e:
    print(f"✗ Snowflake connection failed: {e}")
    import traceback
    traceback.print_exc()
