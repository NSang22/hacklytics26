===============================
AURA — Multimodal Neuro-Symbolic Playtest Engine
Hacklytics 2026 — Entertainment Track
===============================:
1. CORE PRODUCT DEFINITION
One-Line Definition

Real-time multimodal playtest engine that measures player emotion, compares it to developer intent, and automatically identifies broken game mechanics.

Core Insight

Studios record what players do.
AURA measures what players feel.

2. SYSTEM OVERVIEW
Input Modalities
Stream	Frequency	Purpose
Gameplay Video	30 FPS (chunked 10s)	Extract semantic state transitions
Webcam (Presage)	10 Hz	Facial affect (Frustration, Confusion, Delight, Boredom)
Apple Watch	1 Hz	HR + HRV (physiological stress/arousal)
Developer Intent	Pre-session	Intended emotional arc per DFA state
3. ARCHITECTURE OVERVIEW
Stage 1 — Data Collection (Local Machine)
Desktop Capture Agent (Python)

mss (screen capture)

OpenCV

tkinter (UI)

PyInstaller packaging

Responsibilities:

Capture screen at 30 FPS

Capture webcam

Stream Apple Watch BLE data

Chunk video into 10s segments

Upload chunks async to backend

Simplified loop:

while recording:
    chunk = capture_10_seconds(monitor, fps=30)
    upload_async(chunk, session_id, chunk_index)
    chunk_index += 1
Presage SDK

Outputs (0.0–1.0):

Frustration

Confusion

Delight

Boredom

10 Hz emotional signal.

Primary emotion sensor.

Apple Watch BLE

Heart Rate (fast arousal signal)

HRV (stress/cognitive load)

1 Hz physiological stream.

Developer Intent Annotation

For each DFA state:

State Name

Intended Primary Emotion

Acceptable Emotional Range (min/max)

Transforms system from “measurement” → “verdict”.

4. STAGE 2 — PROCESSING PIPELINE (Vultr)
4A. DFA State Extraction (Gemini Vision)

Game progression modeled as:

M = (Q, Σ, δ, q₀, F)

Where:

Q = Game states

Σ = Visual event tokens

δ = Gemini Vision (transition function)

F = Accepting states

Gemini processes each 10s chunk → returns strict JSON:

{
  "current_state": "First_Pit",
  "transitions": [
    {"event": "Player_Died", "timestamp": 24}
  ]
}

Output validated against optional game event log (if instrumented).

4B. Temporal Alignment (CPU)

Resample all streams to unified 1Hz timeline.

df_presage_1hz = df_presage.resample('1S').mean().interpolate(method='time')
df_watch_1hz = df_watch.resample('1S').mean().ffill()
df_states_1hz = expand_dfa_states_to_1hz(gemini_output)

df_fused = pd.concat([df_presage_1hz, df_watch_1hz, df_states_1hz], axis=1)

df_fused['intent_delta'] = abs(
    df_fused['frustration'] - intended_score[df_fused['state']]
)

Each row = 1 second of gameplay.

4C. Cross-Modal Embedding (GPU)

Serialize each 10s window:

state: Boss_Fight | t: 47 |
frustration: 0.82 | confusion: 0.41 |
delight: 0.12 | boredom: 0.03 |
HR: 94 | HRV: 28 |
intent_delta: 0.52

Embedded via:

bge-large-en

Stored in Actian VectorAI (HNSW index)

Purpose:
Semantic trajectory search across sessions.

5. STORAGE LAYER
Snowflake (Relational Time-Series)

Medallion:

Bronze: raw streams

Silver: resampled streams

Gold: fused + intent_delta

Used for:

Aggregations

Per-state health scores

Dashboard analytics

Actian VectorAI

Stores:

Cross-modal embeddings
Enables:

Similarity search

Cross-session pattern detection

6. VERDICT LAYER
Playtest Health Score

Based on intent_delta.

Thresholds:

Green < 0.2

Yellow 0.2–0.4

Red > 0.4

Directional verdict:

Too frustrated?

Not tense enough?

Unexpected boredom?

Supports longitudinal comparison across playtest iterations.

7. DASHBOARD FEATURES (React)
Core Panels

Emotion Timeline (per second)

DFA State Overlay

Intent vs Reality Histogram

Cross-Tester Overlay

Playtest Health Score

Pain Point Rankings

8. SPHINX AI COPILOT

Natural language analytics over:

Snowflake

VectorAI

Example:

"Group by DFA state. Show average frustration and HR per state."

Returns:

Executed SQL

Python plotting code

Matplotlib visualization

9. DEMO — Mario 1-1
Why Mario?

Universal recognition

Known emotional beats

Reliable failure points

Strong narrative hook

Core finding:
First pit appears before pit mechanics are taught.
Frustration spike > intended tense range.
Verdict: FAIL.

Memorable pitch line:
"We just found a 40-year-old design flaw in the most famous level ever made."

10. TEAM ALLOCATION (36 HOURS)
Role	Responsibility
Capture + Demo	Python agent, Mario setup, fallback game
Backend + Pipeline	FastAPI, resampling, Snowflake, intent delta
AI Intelligence	Gemini DFA, embeddings, Sphinx
Dashboard	React portal, live analytics
11. BUILD PRIORITY
MVP (0–18 hours)

Capture agent

FastAPI ingestion

Gemini DFA extraction

Presage integration

1Hz fusion

Basic dashboard

Should Have (18–28 hours)

Snowflake

Embeddings

Intent form

Cross-tester overlay

Nice to Have (28–36 hours)

Sphinx

Longitudinal comparison

VectorAI

Packaging

12. RISK MITIGATION

Gemini fails on NES → fallback HTML5 demo

Presage slow → use pre-recorded data

Watch fails → CSV fallback

Snowflake slow → PostgreSQL fallback

Time shortage → Cut Sphinx + VectorAI

Core MVP remains competitive.

FINAL EXECUTION RULE FOR TEAM

If something doesn’t directly improve:

Emotional fusion

DFA accuracy

Verdict clarity

Demo impact

Cut it.