===============================
PatchLab -- Multimodal Playtest Intelligence Engine
Hacklytics 2026 -- Entertainment Track
===============================
1. CORE PRODUCT DEFINITION

One-Line Definition:
Real-time multimodal playtest engine that measures player emotion via on-device facial analysis and biometrics, compares it to developer intent, and automatically identifies broken game mechanics.

Core Insight:
Studios record what players do.
PatchLab measures what players feel.

2. SYSTEM OVERVIEW

Input Modalities:
Stream              Frequency       Purpose
Gameplay Video      Configurable    Extract DFA state transitions via Gemini Vision
                    (1-30 FPS,
                    chunked 10-15s)
Webcam (MediaPipe)  10 Hz           Facial affect via 52 ARKit blendshapes + iris gaze tracking
Apple Watch BLE     1 Hz            HR + HRV (physiological stress/arousal)
Developer Intent    Pre-session     Intended emotional arc per DFA state

3. ARCHITECTURE OVERVIEW

+------------------------------------------------------------------+
|  STAGE 1 -- DATA COLLECTION (Desktop Client, Python/tkinter)     |
|                                                                  |
|  ScreenCapture --> .webm chunks (10-15s, VP9)                    |
|  WebcamCapture --> MediaPipe FaceAnalyzer (10 Hz emotions)       |
|  WatchBLE      --> Apple Watch HR/HRV via BLE (1 Hz)             |
|                                                                  |
|  ChunkUploader --> async upload to backend (3 workers)           |
|    * POST /upload-chunk (screen video chunks)                    |
|    * POST /emotion-frames (emotion batch every 2s)               |
|    * WS /watch-data (HR/HRV stream, REST fallback)               |
+----------------------------+-------------------------------------+
                             |
                             v
+------------------------------------------------------------------+
|  STAGE 2 -- PROCESSING PIPELINE (FastAPI Backend, Python)        |
|                                                                  |
|  On chunk upload:                                                |
|    ChunkProcessor --> extract frames (2 FPS) --> overlay gaze    |
|    --> Gemini 2.5 Flash vision prompt --> JSON: states, events   |
|                                                                  |
|  On session finalize:                                            |
|    1. Stitch all chunk results into unified timeline             |
|    2. Gather emotion frames from desktop client                  |
|    3. Gather Apple Watch HR/HRV data                             |
|    4. FUSION ENGINE --> 1-Hz aligned DataFrame                   |
|    5. Verdicts: actual emotions vs DFA intent per state          |
|    6. Health Score: weighted average of PASS/WARN/FAIL           |
|    7. Embeddings --> VectorAI (10-sec sliding windows)            |
|    8. Gemini 2.5 Flash --> markdown session insights             |
|    9. Snowflake write (Bronze -> Silver -> Gold)                 |
+----------------------------+-------------------------------------+
                             |
                             v
+------------------------------------------------------------------+
|  STAGE 3 -- STORAGE LAYER                                        |
|                                                                  |
|  Snowflake (Medallion Architecture)                              |
|  Actian VectorAI (Cross-session embeddings)                      |
|  In-memory fallback when credentials unavailable                 |
+----------------------------+-------------------------------------+
                             |
                             v
+------------------------------------------------------------------+
|  STAGE 4 -- DASHBOARD (React + Recharts + Tailwind)              |
|                                                                  |
|  Landing page with scroll-driven frame animation                 |
|  Full dashboard: Setup, Sessions, Review, Aggregate, Sphinx      |
+------------------------------------------------------------------+

All data processing is done in Python (FastAPI backend + desktop client).

Stage 1 -- Desktop Capture Agent (Python, tkinter)

1080-line tkinter GUI with two-column layout:
  Left:  connection settings, screen capture, camera, Apple Watch, upload stats
  Right: live camera feed, emotion bars, gaze visualizer, screen preview, activity log

Technologies:
  mss -- cross-platform screen capture
  OpenCV -- video encoding (VP9 .webm), webcam access
  MediaPipe FaceLandmarker -- facial expression + gaze analysis (replaces Presage SDK)
  bleak -- Apple Watch BLE (Heart Rate Profile 0x180D/0x2A37)
  tkinter + Pillow -- desktop GUI with live previews

Key capabilities:
  * Screen capture at configurable FPS (1-30) and resolution
  * Auto-chunking into 10-15 second VP9 .webm segments
  * Webcam recording with real-time 10 Hz emotion analysis
  * Apple Watch BLE connection (HR + RR intervals -> RMSSD/SDNN)
  * 9-point gaze calibration (polynomial iris->screen mapping)
  * 3-step face calibration (neutral -> smile -> eyes wide)
  * Per-person baseline calibration from first ~30 frames
  * Async chunk upload to backend (3 parallel workers)
  * Preview-first: screen + webcam previews start on launch, independent of recording

MediaPipe Emotion Detection (replaces Presage):

Uses MediaPipe FaceLandmarker with output_face_blendshapes=True providing 52 ARKit-standard
blendshapes. Maps blendshapes to 6 emotions:

  Emotion        Formula
  Surprise       browInnerUp*0.25 + eyeWide*0.35 + jawOpen*0.40
  Delight        smile*0.65 + cheekSquint*0.35 + closed-mouth bonus
  Frustration    browDown*0.40 + mouthPress*0.30 + noseSneer*0.30
  Confusion      browDown + eyeSquint + mouthFrown + mouthPucker + head-tilt bonus
  Boredom        Sustained eye closure (>0.7 threshold) + looking away (>-20 deg pitch)
  Engagement     Eye openness*0.40 + attention direction*0.35 + eyeWide*0.10 + activity*0.15

Additional features:
  * Per-person baseline calibration: auto-calibrates from first ~30 frames, subtracts neutral face
  * Explicit 3-step calibration: Neutral -> Smile -> Eyes Wide, computes expression scaling factors
  * Temporal smoothing: Differential EMA -- positive emotions persist longer (a=0.75) than negative (a=0.35)

Iris-Based Gaze & Eye Tracking:

Two-source fusion:
  * Blendshape eye-look directions (60% weight): eyeLookIn/Out/Up/Down Left+Right
  * Iris landmark positions (40% weight): MediaPipe landmarks 468-477

Optional 9-point polynomial calibration:
  User fixates 9 screen points -> 2nd-order polynomial least-squares fit maps iris ratios -> screen px.
  Gaze position is overlaid as yellow crosshair on video frames sent to Gemini.

Head pose estimation via cv2.solvePnP (pitch/yaw/roll).

Apple Watch BLE:

  Heart Rate (fast arousal signal)
  HRV via RR intervals (RMSSD, SDNN -- stress/cognitive load)
  1 Hz physiological stream via BLE Heart Rate Profile.

Developer Intent Annotation:

  For each DFA state, developers define:
    State Name
    Description + Visual Cues
    Intended Primary Emotion
    Acceptable Emotional Range (min/max)
    Expected Duration
    Failure Indicators

  Transforms system from "measurement" -> "verdict".

4. STAGE 2 -- PROCESSING PIPELINE (FastAPI, Python)

All processing runs in the Python backend -- no separate GPU service needed.

4A. DFA State Extraction (Gemini 2.5 Flash Vision -- Frame-Based DFA)

Game progression modeled as a DFA where Gemini acts as the transition function:
  M = (Q, Σ, δ, q₀, F)
  Where:
    Q = Game states (developer-defined, with visual cues and expected durations)
    Σ = Consecutive JPEG frames extracted from gameplay video
    δ = Gemini 2.5 Flash (processes frame pairs to detect state transitions)
    q₀ = First developer-defined state
    F = Accepting states

Key insight: instead of sending a whole video to Gemini and asking "what states
are in this clip?", we send individual JPEG frames as inline image parts and
tell Gemini its current state. Gemini compares consecutive frame pairs to detect
when the visual content changes enough to indicate a state transition — exactly
like a DFA transition function δ(current_state, input) → next_state.

This solves the "single-state collapse" problem where Gemini would classify an
entire chunk as one state (e.g. overworld_start for 316s) because it had no
concept of "current state" or sequential frame-by-frame comparison.

Processing per chunk:
  1. Receive .webm video chunk (~10-15s)
  2. Extract JPEG frames at configurable FPS (default 2) using OpenCV
  3. If gaze data available, overlay yellow crosshair at gaze position on each frame
  4. Build DFA transition prompt that includes:
     - CURRENT STATE (from previous chunk's end_state, or first DFA state)
     - All DFA state definitions (names, visual_cues, expected_duration, indicators)
     - Expected progression order or explicit transition graph
     - Context from previous chunk (end_state, end_status, cumulative_deaths)
     - Frame timestamps (absolute session seconds)
  5. Send frames as inline JPEG image parts (types.Part.from_bytes) + text prompt
     to Gemini 2.5 Flash — NOT as a video upload
  6. Gemini processes frames sequentially and returns JSON:
     {
       "states_observed": [
         {"state_name": "overworld_start", "entered_at_sec": 0.0, "exited_at_sec": 7.5,
          "player_behavior": "progressing", "progress": "normal"}
       ],
       "transitions": [
         {"from_state": "overworld_start", "to_state": "ground_run",
          "timestamp_sec": 7.5, "confidence": 0.92}
       ],
       "events": [
         {"type": "death", "description": "Fell into pit",
          "timestamp_sec": 24.0, "state": "first_pit"}
       ],
       "end_state": "first_pit",
       "end_status": "progressing",
       "chunk_summary": "Player progressed through overworld into ground run..."
     }
  7. _parse_gemini_response() converts raw JSON into typed ChunkResult models
  8. stitch_chunk_results() merges all chunk results into unified timeline

Retry logic: up to 3 attempts with exponential backoff per chunk.
Mock mode: returns realistic fake data with simulated state progression.
Graceful degradation: falls back to mock if no API key, no video, or 0 frames extracted.

4B. Temporal Alignment & Fusion (Python)

Three-stream fusion engine aligns to unified 1Hz timeline:
  - Emotion frames (10 Hz -> 1 Hz averaging)
  - Watch data (1 Hz -> forward-fill)
  - DFA states (event-based -> expanded to 1 Hz)

  Computes intent_delta = |actual_emotion - intended_emotion| per state per second.
  Each row = 1 second of gameplay with all streams merged.

4C. Cross-Modal Embedding (CPU)

10-second sliding windows -> feature vector concatenation (no external ML model):
  - 6 emotion averages (frustration, confusion, delight, boredom, surprise, engagement)
  - Normalized HR + normalized HRV + HR variance
  - Movement score
  - One-hot DFA state encoding

Stored in Actian VectorAI with cosine similarity search.
Purpose: Cross-session pattern detection ("find similar gameplay moments").

4D. Session Insights (Gemini 2.5 Flash)

After fusion + verdicts, Gemini generates markdown session insights summarizing
key findings, emotional patterns, and design recommendations.

5. STORAGE LAYER

Snowflake (Medallion Architecture):

  Bronze Layer:
    BRONZE_GAMEPLAY_EVENTS  -- raw game events from Gemini extraction
    BRONZE_PRESAGE          -- raw emotion frames (with gaze_x/y, head pose, AUs)
    BRONZE_WATCH            -- raw HR/HRV readings
    BRONZE_CHUNKS           -- per-chunk Gemini analysis results

  Silver Layer:
    SILVER_FUSED            -- 1-Hz aligned rows with all streams merged

  Gold Layer:
    GOLD_STATE_VERDICTS     -- per-state PASS/WARN/FAIL verdicts
    GOLD_SESSION_SUMMARY    -- session health scores, dominant emotions

  write_all() writes Bronze -> Silver -> Gold in a single connection.
  Falls back to in-memory storage when Snowflake credentials unavailable.

Actian VectorAI:

  Collection: patchlab_embeddings
  10-sec window vectors stored with session/project metadata
  Cosine similarity search for cross-session comparison
  Fallback: persistent JSON file (vectorai_fallback.json) with manual cosine similarity

6. VERDICT LAYER

Playtest Health Score based on intent_delta:

  Thresholds:
    PASS  (Green)  -- intent_delta < 0.2
    WARN  (Yellow) -- intent_delta 0.2-0.4
    FAIL  (Red)    -- intent_delta > 0.4

  Directional verdict per DFA state:
    Too frustrated?
    Not tense enough?
    Unexpected boredom?

  Session health score = weighted average of all state verdicts.
  Supports longitudinal comparison across playtest iterations.

7. DASHBOARD (React + Recharts + Tailwind)

Landing Page:
  Scroll-driven 207-frame animation, Hero section, "What Is It" explainer, FAQ.

Dashboard Pages:

  Project Setup:
    Full DFA state editor (name, intended_emotion, acceptable_range, expected_duration,
    visual_cues, failure_indicators). Includes Mario 1-1 preset. Calls POST /v1/projects.

  Session Management:
    Create sessions with configurable chunk duration, list sessions with health scores,
    generate tester game URL with embedded SDK.

  Session Review:
    Deep-dive tabs:
      Overview -- emotion timeline (Recharts), HR chart, Gemini-generated insights
      Chunks -- per-chunk analysis details
      Events -- game events with severity levels
      Verdicts -- per-state PASS/WARN/FAIL cards with directional feedback

  Cross-Tester Aggregate:
    Health score trend line, bar comparison, per-state verdict summary table,
    pain point rankings, cross-tester Gemini insights.

  Sphinx Explorer:
    NL query input + example queries. UI fully built. (Backend stub -- not yet implemented.)

8. SPHINX AI COPILOT

Frontend UI is fully built with NL query input and example queries.
Backend returns stub response -- not yet implemented.
Static demo available in the landing page dashboard mockup.

9. GAME SDK

HTML5 Canvas demo game with 5 DFA states + ChunkedGameRecorder (chunked-recorder.js):
  - MediaRecorder API with VP9 codec
  - Auto-chunks gameplay video and uploads to backend
  - Game event reporting via postMessage
  - Loadable via iframe with session_id + backend_url params

10. DEMO -- Mario 1-1

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

11. TECH STACK SUMMARY

  Layer               Technology
  Desktop Client      Python, tkinter, mss, OpenCV, Pillow
  Emotion Detection   MediaPipe FaceLandmarker (52 ARKit blendshapes)
  Eye/Gaze Tracking   MediaPipe iris landmarks (468-477) + blendshape fusion
  Physiological       bleak (BLE Heart Rate Profile)
  Backend             Python, FastAPI, uvicorn, OpenCV (frame extraction), Pydantic
  AI/Vision           Google Gemini 2.5 Flash (google-genai SDK, inline frame parts)
  Storage             Snowflake (snowflake-connector-python), Actian VectorAI (REST)
  Frontend            React, React Router, Recharts, Tailwind CSS, Vite
  Game SDK            Vanilla JS, Canvas API, MediaRecorder (VP9)

12. WHAT'S FULLY IMPLEMENTED

  [x] MediaPipe face analysis (blendshape->emotion, gaze, head pose, calibration, smoothing)
  [x] Face calibration (3-step) + gaze calibration (9-point polynomial)
  [x] Screen capture with configurable FPS/resolution/chunking
  [x] Webcam capture with threaded ~10 Hz emotion analysis
  [x] Apple Watch BLE connection (HR + RR intervals -> RMSSD/SDNN)
  [x] Full 1080-line desktop GUI with live previews
  [x] Chunk processor (OpenCV frame extraction, gaze overlay, DFA transition prompt)
  [x] Gemini 2.5 Flash frame-based DFA extraction (inline JPEG parts, not video upload)
  [x] Gemini 2.5 Flash session insights generation
  [x] 3-stream fusion engine (1 Hz alignment, intent_delta)
  [x] Verdict system (PASS/WARN/FAIL per state, health score)
  [x] Embedding generation (feature vectors, 10-sec windows)
  [x] Snowflake full medallion write (Bronze -> Silver -> Gold)
  [x] VectorAI upsert + cosine similarity search
  [x] All 5 dashboard pages (Setup, Sessions, Review, Aggregate, Sphinx UI)
  [x] Landing page with scroll-driven frame animation
  [x] Demo HTML5 Canvas game with ChunkedGameRecorder SDK
  [x] Async 3-worker chunk upload pipeline

  [ ] Sphinx AI Copilot -- frontend UI built, backend stub only
  [ ] Presage SDK -- fully replaced by MediaPipe (presage_client.py is a random-data stub)
