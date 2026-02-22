"""
Sphinx client — proxy for Sphinx natural-language query engine.

Translates user plain-English questions into structured queries over
the PatchLab data, returning markdown-formatted answers.

STUB — returns canned responses.
"""

import subprocess
import tempfile
import os
import json
from typing import List, Optional

from dotenv import load_dotenv

BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
OUTPUTS_DIR = os.path.join(BACKEND_DIR, "outputs")

load_dotenv(os.path.join(BACKEND_DIR, ".env"))


class SphinxClient:
    """Stub client for Sphinx AI queries - to be implemented"""
    
    async def query(self, question: str, project_id: str, session_ids: Optional[List[str]] = None):
        """Execute natural language query against Snowflake data"""
        return {
            "success": False,
            "error": "SphinxClient not yet implemented",
            "question": question,
            "project_id": project_id
        }

# SF_ACCOUNT   = os.environ.get("SNOWFLAKE_ACCOUNT")
# SF_USER      = os.environ.get("SNOWFLAKE_USER")
# SF_PASSWORD  = os.environ.get("SNOWFLAKE_PASSWORD")
# SF_WAREHOUSE = os.environ.get("SNOWFLAKE_WAREHOUSE")
# SF_DATABASE  = os.environ.get("SNOWFLAKE_DATABASE")
# SF_SCHEMA    = os.environ.get("SNOWFLAKE_SCHEMA")

QUESTION = "What is the average grade per subject? Plot a line graph of average grade by subject (sorted ascending) and save it to outputs/line.png"

PROMPT = f"""
You have access to a PostgreSQL database.
Use psycopg2 to connect with this connection string:

  postgresql://jhonathanherrera@localhost:5432/postgres

Answer this question: {QUESTION}

Steps:
1. Run the SQL query to get average grade per subject, sorted ascending by average grade.
2. Use matplotlib to produce a line plot:
   - x-axis: subject names (sorted ascending by avg grade)
   - y-axis: average grade
   - Add markers on each point, a title "Average Grade by Subject", and labeled axes.
3. Save the figure to the absolute path: {OUTPUTS_DIR}/line.png
   Use: os.makedirs("{OUTPUTS_DIR}", exist_ok=True) then plt.savefig("{OUTPUTS_DIR}/line.png")
4. Also call plt.show() so it displays in the notebook output.
5. Print the result as a JSON object using json.dumps with indent=2.

The JSON must follow this structure:
{{
  "question": "<the question>",
  "result": {{"subject": "<avg_grade>"}},
  "sql": "<the SQL query you ran>",
  "summary": "<a natural language sentence summarizing which subject has the highest and lowest average grade>"
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
            cwd=BACKEND_DIR,
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
