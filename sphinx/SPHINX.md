# PlayPulse — Sphinx Explorer

## What Sphinx Does

You give Sphinx a natural language question and database credentials.
Sphinx figures out the SQL, runs it against the database, and returns the answer.
You never write SQL. That is the entire point.

```
"Which game state frustrated players the most?"
                    ↓
              Sphinx AI
   (writes SQL + executes it + returns result)
                    ↓
         { "result": [...], "sql": "..." }
```

---

## How It Works — Step by Step

### 1. You ask a question

```python
QUESTION = "What is the average frustration score per DFA state?"
```

### 2. We build a prompt with the database credentials

```python
PROMPT = f"""
You have access to a Snowflake data warehouse.
Use snowflake.connector to connect:

  account   = "iac43738.us-east-1"
  user      = "GG1627"
  password  = "..."
  warehouse = "DATAMART_WH"
  database  = "DATAMART_DB"
  schema    = "DATAMART_SCHEMA"

Answer this question: {QUESTION}
Print the result as JSON.
"""
```

### 3. We call sphinx-cli as a subprocess

```python
subprocess.run([
    "sphinx-cli", "chat",
    "--notebook-filepath", nb_path,   # temp file, deleted after
    "--prompt", PROMPT,
    "--no-file-search",
    "--no-web-search",
])
```

### 4. Sphinx does everything else

- Decides what SQL to write
- Writes the `snowflake.connector` code into a Jupyter cell
- Executes it against your actual Snowflake warehouse
- Reads the output
- Prints the JSON result to the terminal

You never see the SQL. You never touch the database directly. Sphinx handles it.

### 5. Result streams to your terminal

```
Sphinx: I will connect to Snowflake and query the gold_cross_session_aggregates table...
Sphinx: Query successful. Here is the result.

{
  "question": "average frustration per DFA state",
  "result": [
    { "dfa_state": "puzzle_room", "avg_frustration": 0.71 },
    { "dfa_state": "gauntlet",    "avg_frustration": 0.58 },
    ...
  ],
  "sql": "SELECT dfa_state, AVG(avg_frustration) FROM gold_cross_session_aggregates GROUP BY dfa_state"
}
```

---

## What the Temp Notebook Is For

Sphinx needs a Jupyter kernel to execute code. The `.ipynb` file is its workspace.
We create an empty one, let Sphinx use it, then delete it when done.
The result lives in the terminal output — not the file.

```
temp.ipynb (sphinx writes code here)      Terminal (you see this)
┌─────────────────────────┐              ┌──────────────────────────┐
│ Cell: snowflake code    │──executes──► │ Sphinx: Connecting...    │
│ Output: JSON printed    │              │ Sphinx: Done.            │
└─────────────────────────┘              │ { "result": ... }        │
           │                             └──────────────────────────┘
      deleted after
```

---

## Snowflake Data Warehouse — What Sphinx Queries

PlayPulse stores all playtest data in Snowflake using three layers.

### Bronze — raw sensor data

| Table | Source | Rate |
|---|---|---|
| `bronze_presage_emotions` | Facial emotion (frustration, confusion, delight, surprise, engagement, boredom) | ~10/sec |
| `bronze_gemini_chunks` | Gemini's analysis of 15-second gameplay video chunks — DFA state, events, behavior | 1 per 15s |
| `bronze_watch_biometrics` | Apple Watch heart rate + HRV | ~1/sec |

### Silver — fused 1-second timeline

| Table | What it is |
|---|---|
| `silver_fused_timeline` | All three sources merged into one row per second. Presage averaged to 1/s, Gemini state forward-filled, Watch aligned 1:1 |

### Gold — computed analytics (what Sphinx mostly queries)

| Table | What it answers |
|---|---|
| `gold_state_verdicts` | Did each game segment make the player feel what the developer intended? PASS / WARN / FAIL per state per session |
| `gold_session_health` | One Playtest Health Score (0–1) per session |
| `gold_cross_session_aggregates` | Averages across all testers — frustration, HR, pass/fail rates per DFA state |

### DFA States (the 5 game segments)

| State | What it is | Intended emotion |
|---|---|---|
| `tutorial` | Player learns controls | Calm |
| `puzzle_room` | Hidden path puzzle, often fails | Curious |
| `surprise_event` | Floor drops, enemies appear | Surprised |
| `gauntlet` | Moving obstacles, player can die | Tense |
| `victory` | YOU WIN screen | Satisfied |

---

## The Three Killer Queries

These are the three questions Sphinx answers for the judge demo.

**Query 1 — The Heatmap ("where is it broken?")**
> "Show the average frustration and heart rate for each game state across all testers"

Sphinx queries `gold_cross_session_aggregates`. Result renders as a color-coded bar chart — red = broken, green = working.

**Query 2 — The Scatter ("why is it broken?")**
> "Show the relationship between how long players got stuck and how confused they were, per state"

Sphinx joins `gold_state_verdicts` with `silver_fused_timeline`. Result renders as a scatter plot — upper right cluster = stuck + confused = highest priority fix.

**Query 3 — The Health Bar ("is it getting better?")**
> "Show the playtest health score for every session"

Sphinx queries `gold_session_health`. Result renders as a bar chart colored by score. Run another round of tests after fixing something — the score should go up.

---

## Running It

```bash
# Direct test — Sphinx connects to Snowflake, runs query, prints JSON
python test_sphinx_cli.py

# Full server — question → Sphinx → Snowflake → chart at localhost:8000
python sphinx/sphinx_client.py
```

## Required Environment Variables

```
SNOWFLAKE_ACCOUNT    = iac43738.us-east-1
SNOWFLAKE_USER       = GG1627
SNOWFLAKE_PASSWORD   = ...
SNOWFLAKE_WAREHOUSE  = DATAMART_WH
SNOWFLAKE_DATABASE   = DATAMART_DB
SNOWFLAKE_SCHEMA     = DATAMART_SCHEMA
SPHINX_API_KEY       = sk_live_...   ← from dashboard.prod.sphinx.ai
GEMINI_API_KEY       = ...           ← fallback only, if Sphinx is unavailable
```
