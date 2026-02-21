"""
test_sphinx_cli.py

Tells sphinx-cli to connect to the Snowflake data warehouse,
run a query, and return the result as JSON in the terminal. No .ipynb saved.

Run:
    python test_sphinx_cli.py
"""

import subprocess
import tempfile
import os
import json

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# SF_ACCOUNT   = os.environ.get("SNOWFLAKE_ACCOUNT")
# SF_USER      = os.environ.get("SNOWFLAKE_USER")
# SF_PASSWORD  = os.environ.get("SNOWFLAKE_PASSWORD")
# SF_WAREHOUSE = os.environ.get("SNOWFLAKE_WAREHOUSE")
# SF_DATABASE  = os.environ.get("SNOWFLAKE_DATABASE")
# SF_SCHEMA    = os.environ.get("SNOWFLAKE_SCHEMA")

QUESTION = "Return the names of all students that start with the letter D"

PROMPT = f"""
You have access to a PostgreSQL database.
Use psycopg2 to connect with this connection string:

  postgresql://jhonathanherrera@localhost:5432/postgres

Answer this question: {QUESTION}

Run the appropriate SQL query, then print the result as a JSON object using json.dumps with indent=2.

The JSON must follow this structure:
{{
  "question": "<the question>",
  "result": <value or dict>,
  "sql": "<the SQL query you ran>"
}}

Print only the JSON — nothing else.
"""


def main():
    api_key = os.environ.get("SPHINX_API_KEY", "")
    if not api_key:
        print("ERROR: SPHINX_API_KEY not set in .env")
        return

    # Write a minimal valid empty notebook so sphinx-cli can open it
    with tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False, mode="w") as tmp:
        json.dump({
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "cells": [],
        }, tmp)
        nb_path = tmp.name

    print(f"sphinx-cli → Postgres: {QUESTION}")
    print("─" * 50)

    try:
        subprocess.run(
            [
                "sphinx-cli", "chat",
                "--notebook-filepath", nb_path,
                "--prompt",           PROMPT.strip(),
                "--no-file-search",
                "--no-web-search",
            ],
            timeout=120,
            env={**os.environ, "SPHINX_API_KEY": api_key},
        )

        # Read cell outputs from the notebook sphinx wrote
        with open(nb_path) as f:
            nb = json.load(f)

        print("\n" + "─" * 50)
        for cell in nb.get("cells", []):
            for output in cell.get("outputs", []):
                text = (
                    output.get("text")
                    or output.get("data", {}).get("text/plain")
                )
                if text:
                    print("".join(text) if isinstance(text, list) else text)

    finally:
        if os.path.exists(nb_path):
            os.remove(nb_path)


if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired:
        print("Timed out after 120s")
    except KeyboardInterrupt:
        print("\nCancelled")
