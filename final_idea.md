# PatchLab — Multimodal Neuro-Symbolic Playtest Engine

**Hacklytics 2026 — Entertainment Track**

---

## 1. CORE PRODUCT DEFINITION

**One-Line Definition:**
Real-time multimodal playtest engine that measures player emotion, compares it to developer intent, and automatically identifies broken game mechanics.

**Core Insight:**
Studios record what players *do*.
PatchLab measures what players *feel*.

---

## 2. SYSTEM ARCHITECTURE

PatchLab is a four-component system:

| Component | Stack | Port | Purpose |
|-----------|-------|------|---------|
| **Website** | React + Vite + Tailwind | 5173 | Marketing landing page, interactive demo dashboard |
| **Web App** | React + Vite | 5174 | DFA setup, session management, review, cross-tester aggregate, Sphinx |
| **Backend API** | FastAPI + Python | 8000 | 30-endpoint REST/WS service, 3-stage pipeline, Gemini/Snowflake/VectorAI |
| **Desktop Client** | Python + tkinter + MediaPipe | — | Screen capture, webcam emotion, Apple Watch BLE, chunk upload |

Additionally, an **in-browser game recorder** (`patchlab/game/`) enables HTML5 games to self-capture gameplay via `canvas.captureStream()`.

---

## 3. INPUT MODALITIES

| Stream | Frequency | Source | Purpose |
|--------|-----------|--------|---------|
| Gameplay Video | 1-30 FPS (chunked 5-30s) | Desktop screen capture or browser canvas | DFA state extraction via Gemini Vision |
| Webcam Emotion | 10 Hz | Desktop MediaPipe FaceLandmarker (478-point mesh, 52 ARKit blendshapes) | 6 emotions: engagement, delight, surprise, frustration, confusion, boredom |
| Apple Watch BLE | 1 Hz | Standard BLE HR Service (0x180D) | HR, HRV (RMSSD + SDNN), RR intervals, movement variance |
| Developer Intent | Pre-session | Web App DFA editor | Intended emotion per state, acceptable range, expected duration |

---

## 4. WEBSITE (`frontend/`)

**Purpose:** Public-facing marketing landing page with interactive demo.

**Key Features:**
- **Scroll-driven animation:** 207-frame PNG canvas animation with 0.5 lerp smooth interpolation
- **Hero section:** "#1 AI Video Game Analyzer" headline with CTA -> dashboard
- **Feature showcase:** 6 feature cards + 4-step pipeline visualization (Capture -> Analyze -> Fuse -> Verdict) with IntersectionObserver reveal animations
- **Interactive demo dashboard:** Full Super Mario Bros 1-1 mock data (590 lines)
  - 6 DFA states with 72 seconds of generated emotion data
  - `EmotionTimeline` — canvas-based 4-emotion line chart
  - `CrossTesterChart` — 5-tester recharts overlay
  - `HealthRing` — SVG radial 0-100 gauge
  - `VerdictCard` — per-state PASS/WARN/FAIL
  - 3 tabs: Session Review, Cross-Tester, Sphinx AI
- **FAQ:** 8 accordion items with bottom CTA -> setup
- **Navigation:** PatchLab logo, Pricing, Desktop, Contact

---

## 5. WEB APP (`patchlab/frontend/`)

**Purpose:** Developer-facing webapp for project setup, live monitoring, and post-session analysis.

### Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | **ProjectSetup** | DFA state editor: name, intended emotion (9 options), expected duration, acceptable range, description, visual cues, failure/success indicators. Mario 1-1 preset (5 states). DFA transition editor with auto-generate. Optimal playthrough video upload. |
| `/sessions` | **SessionManagement** | Session creation, 3s-poll live collection monitor, stream health indicators (Screen/Presage/Watch: Live/Waiting), configurable chunk duration 5-30s slider |
| `/review` | **SessionReview** | 4-tab analysis: Overview (emotion timeline + HR chart), Chunks (per-chunk Gemini results), Events (severity icons, death counter, bar chart), Verdicts (intended vs actual, score bar, deviation). Fetches 6 endpoints in parallel. |
| `/aggregate` | **CrossTesterAggregate** | Project-level cross-tester summary, health trend over sessions, pain point ranking |
| `/sphinx` | **SphinxExplorer** | Natural language query interface for Snowflake + VectorAI analytics |

---

## 6. DESKTOP CLIENT (`patchlab/desktop/`)

**Purpose:** Local capture agent that records screen, webcam, and Apple Watch data, processes emotion on-device, and streams everything to the backend.

### Core Application (`main.py` — 1,080 lines)

**UI:** Two-column tkinter layout — left controls, right live data, scrollable body.

**Left Column:**
- Backend connection: URL, project ID, tester name
- Screen capture: FPS (1/2/3/custom up to 30), monitor selector, chunk duration 5-30s, resolution (native/720p/540p)
- Camera settings: camera selector, gaze calibrate, face calibrate, head pose display
- Apple Watch BLE: device scanner, connect/disconnect, HR/HRV display
- Upload stats: chunks/emotions/watch counters

**Right Column:**
- Live camera feed (320x240 canvas)
- 6-bar emotion visualization (engagement, delight, surprise, frustration, confusion, boredom)
- Gaze tracking canvas (200x130) + screen preview with FPS overlay
- Timestamped activity log

### Face Emotion Analysis (`face_analyzer.py` — 643 lines)

**Engine:** MediaPipe FaceLandmarker in IMAGE mode, 1 face, 478-point mesh, 52 ARKit blendshapes.

**Blendshape -> Emotion Mapping:**

| Emotion | Blendshapes | Multiplier |
|---------|-------------|------------|
| Surprise | browInnerUp (0.25) + eyeWide (0.35) + jawOpen (0.40) | x1.4 |
| Delight | smile (0.65) + cheekSquint (0.35) + closed-mouth bonus | x1.4 |
| Frustration | browDown (0.40) + mouthPress (0.30) + noseSneer (0.30) | x1.5 |
| Confusion | browDown (0.35) + eyeSquint (0.25) + mouthFrown (0.25) + mouthPucker (0.15) + head tilt bonus | x1.5 |
| Boredom | sustained eye close >0.7 (0.50) + looking away <-20 deg (0.50) | — |
| Engagement | eye openness (0.40) + attention direction (0.35) + eye wide (0.10) + activity bonus (0.15) | — |

**Head Pose:** `cv2.solvePnP` with 6-point 3D face model -> pitch, yaw, roll.

**Gaze Tracking:** Iris-based (landmarks 468-477), fuses blendshape eye-look directions (60%) with iris landmark positions (40%).

**Temporal Smoothing:** Differential EMA — positive emotions alpha=0.75, engagement alpha=0.5, negative emotions alpha=0.35.

### Face Calibration (`face_calibration.py` — ~350 lines)

**3-step expression calibration overlay:**
1. **Neutral** (3s) — baseline expression
2. **Smile** (3s) — delight ceiling
3. **Eyes Wide** (3s) — surprise ceiling

Each phase: 1s settle + 2s capture. Computes per-person expression ranges -> scaling factors applied to `FaceAnalyzer`.

### Gaze Calibration (`gaze_calibration.py` — ~320 lines)

**9-point fullscreen calibration** (3x3 grid, 10% margin):
- 1s settle + 2s capture per point
- Fits 2nd-order polynomial model (6 features: 1, x, y, x^2, y^2, xy) via `np.linalg.lstsq`
- Reports mean error: green < 50px, amber < 100px, red >= 100px

### Other Desktop Modules

| Module | Purpose |
|--------|---------|
| `webcam_capture.py` (371 lines) | Camera capture + face analysis loop at 10 Hz, preview + recording (mp4v), `EmotionReading` 14-field dataclass |
| `screen_capture.py` (~270 lines) | mss screen capture at 1-30 FPS, auto-chunking on duration boundary, resolution scaling |
| `watch_ble.py` (395 lines) | BLE Heart Rate Service, device scanning by UUID + name keywords (Apple Watch, Polar, Garmin, Fitbit), HRV from RR-intervals (rolling 60s RMSSD/SDNN) |
| `chunk_uploader.py` (348 lines) | 3 upload threads: video chunks, emotion batches (2s interval), watch data (WebSocket with REST fallback). Session lifecycle: create -> upload -> finalize. |

---

## 7. BACKEND API (`patchlab/backend/`)

**Stack:** FastAPI, Pydantic, Google Gemini 2.5 Flash (`google-genai`), Snowflake, Actian VectorAI, `sentence-transformers` (bge-large-en), pandas, numpy.

### API Endpoints (30 total)

**Projects:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/projects` | List all projects |
| POST | `/v1/projects` | Create project with DFA config |
| GET | `/v1/projects/{id}` | Get project details |
| PUT | `/v1/projects/{id}/dfa` | Update DFA config |
| POST | `/v1/projects/{id}/optimal-playthrough` | Upload + Gemini-analyze reference video |
| DELETE | `/v1/projects/{id}/data` | Clear project data |

**Sessions:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/projects/{id}/sessions` | Create session |
| GET | `/v1/sessions/{id}` | Get session details |
| GET | `/v1/sessions/{id}/status` | Session status |
| GET | `/v1/sessions/{id}/collection-status` | Live desktop stream health |

**Data Ingestion:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/sessions/{id}/upload-chunk` | Upload video chunk -> triggers background Gemini processing |
| POST | `/v1/sessions/{id}/upload-face-video` | Upload full face video |
| POST | `/v1/sessions/{id}/emotion-frames` | Desktop emotion frame batch |
| POST | `/v1/sessions/{id}/watch-data` | REST fallback for watch readings |
| WS | `/v1/sessions/{id}/watch-stream` | WebSocket for live watch data |

**Pipeline:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/sessions/{id}/finalize` | Run full 8-step pipeline |

**Results:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/sessions/{id}/timeline` | Fused 1Hz timeline |
| GET | `/v1/sessions/{id}/verdicts` | Per-state verdicts |
| GET | `/v1/sessions/{id}/insights` | Gemini-generated insights |
| GET | `/v1/sessions/{id}/health-score` | Playtest health score |
| GET | `/v1/sessions/{id}/chunks` | Per-chunk Gemini analysis |
| GET | `/v1/sessions/{id}/events` | Event timeline |

**Cross-Tester & Analytics:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/projects/{id}/aggregate` | Cross-tester summary |
| GET | `/v1/projects/{id}/aggregate/verdicts` | All verdicts by session |
| GET | `/v1/projects/{id}/aggregate/insights` | Gemini cross-tester insights |
| GET | `/v1/projects/{id}/health-trend` | Health score trend |
| POST | `/v1/projects/{id}/sphinx-query` | Sphinx NL query |
| POST | `/v1/projects/{id}/vector-search` | VectorAI similarity search |

---

## 8. THREE-STAGE PROCESSING PIPELINE

### Stage 1 — Gemini Vision DFA Extraction

Game progression modeled as a DFA:

```
M = (Q, Sigma, delta, q0, F)
```

Where Q = game states, Sigma = visual event tokens, delta = **Gemini Vision** (transition function), F = accepting states.

**Current approach:** Each video chunk is processed through `chunk_processor.py`:
1. `extract_frames()` — OpenCV extracts frames at configurable FPS (default 2), encodes as JPEG
2. Gaze overlay — if gaze data exists, a yellow crosshair is composited onto each frame at the gaze point
3. `_build_gemini_prompt()` — structured prompt with DFA states, visual cues, context chaining from previous chunk (end_state, cumulative_deaths)
4. `_call_gemini_with_retry()` — sends to Gemini 2.5 Flash with exponential backoff (3 retries, 1.5s x attempt)
5. `_parse_gemini_response()` — validates JSON into `ChunkResult` (states_observed, transitions, events, deaths, end_state)
6. `stitch_chunk_results()` — merges sequential chunk results, deduplicates adjacent same-state observations

**Context chaining:** Each chunk receives the previous chunk's `end_state`, `end_status`, and `cumulative_deaths` so Gemini knows where the player left off.

**Coming Next — Dual Frame Processing:**
Instead of uploading whole video files via the Gemini Files API, send extracted JPEG frames as inline `Part.from_bytes()` parts. This enables:
- Gemini to see individual frames sequentially (frame-by-frame comparison)
- Better state transition detection at frame boundaries
- DFA transition function framing in the prompt: "You are a DFA transition function, CURRENT STATE is X, process each frame and report transitions"
- Elimination of the video upload/wait/poll cycle

### Stage 2 — Temporal Fusion (`fusion.py` — 462 lines)

Resample all three data streams to a unified 1Hz timeline:

1. **Emotion data** — bucket by second -> mean -> forward-fill
2. **Watch data** — bucket by second -> last reading -> forward-fill
3. **DFA states** — expand Gemini chunk transitions to per-second state labels

Assemble into a unified DataFrame (19 columns per row):

```
t, session_id, state, time_in_state_sec,
frustration, confusion, delight, boredom, surprise, engagement,
hr, hrv_rmssd, hrv_sdnn, presage_hr, breathing_rate, movement_variance,
intent_delta, dominant_emotion, data_quality
```

Derive `intent_delta = abs(measured[intended_emotion] - expected_midpoint)` per row.

### Stage 3 — Verdict + Analytics

**Verdict Engine (`verdict.py`):**
- Per-state PASS / WARN / FAIL based on `intent_delta` against `acceptable_range`
- Override: if dominant emotion != intended and exceeds by >0.2 -> FAIL
- Health score: weighted average (PASS=1.0, WARN=0.5, FAIL=max(0, 1-deviation))

**Embeddings (`embeddings.py` — 354 lines):**
- Serialize each 10s window as structured text (state, emotions, HR, HRV, intent_delta)
- Encode with `bge-large-en` (1024-dim), unit-normalized
- Store in Actian VectorAI (HNSW index) for cross-session semantic search

**Gemini Insights:**
- Session-level narrative analysis from fused data + verdicts
- Cross-tester comparison insights

### Finalize Pipeline (8 steps)

When `POST /v1/sessions/{id}/finalize` is called:

1. **Stitch chunks** -> unified DFA timeline
2. **Collect emotion data** — desktop live frames > face video fallback
3. **Collect watch data** — BLE readings
4. **Temporal fusion** -> 1Hz DataFrame
5. **Write Snowflake** — Bronze + Silver layers
6. **Compute verdicts + health score** -> Gold layer to Snowflake
7. **Embed + store** -> VectorAI (10s windows, 5s stride)
8. **Generate Gemini insights** -> session narrative

---

## 9. STORAGE LAYER

### Snowflake — Medallion Architecture

| Layer | Table | Content |
|-------|-------|---------|
| Bronze | `BRONZE_PRESAGE` | Raw emotion frames with gaze data |
| Bronze | `BRONZE_WATCH` | Raw HR/HRV readings |
| Bronze | `BRONZE_CHUNKS` | Raw Gemini chunk analysis results |
| Silver | `SILVER_FUSED` | Clean 1Hz fused DataFrame (19 columns) |
| Gold | `GOLD_STATE_VERDICTS` | Per-state PASS/WARN/FAIL verdicts (14 columns) |
| Gold | `GOLD_SESSION_SUMMARY` | Session summary: health score, P/W/F counts, dominant emotion |

**Writer** (`snowflake_writer.py` — 732 lines): Auto-creates tables, writes all layers in a single connection for efficiency. Supports MOCK_MODE (computes verdicts locally, skips Snowflake writes).

### Actian VectorAI

- Cross-modal embeddings (bge-large-en, 1024-dim)
- HNSW index for similarity search
- Enables: "find sessions where the player felt X during state Y"

---

## 10. SPHINX AI COPILOT

Natural language analytics over Snowflake + VectorAI.

**Example queries:**
- "Group by DFA state. Show average frustration and HR per state."
- "Find all sessions where players died more than 3 times in the gauntlet."

**Returns:** Executed SQL, Python plotting code, visualization.

*Status: Endpoint wired (`POST /v1/projects/{id}/sphinx-query`), client is a stub awaiting implementation.*

---

## 11. IN-BROWSER GAME RECORDER (`patchlab/game/`)

**Purpose:** Enables HTML5 games to self-capture gameplay and upload chunks directly — no desktop client needed.

**Demo game** (`index.html` — ~380 lines): 5-state game (tutorial -> puzzle_room -> surprise_event -> gauntlet -> victory) with death tracking.

**Recorder** (`chunked-recorder.js` — ~90 lines): `canvas.captureStream(30)` -> MediaRecorder (WebM VP9, 1.5 Mbps) -> 15s chunks auto-uploaded via `POST /upload-chunk`.

On game end: uploads face video -> finalizes session.

---

## 12. FEATURES — IMPLEMENTED

| Feature | Status | Component |
|---------|--------|-----------|
| DFA state editor with Mario 1-1 preset | Done | Web App |
| DFA transition editor with auto-generate | Done | Web App |
| Optimal playthrough video analysis | Done | Web App + Backend |
| Session creation + live monitoring | Done | Web App + Desktop |
| Screen capture at 1-30 FPS with chunking | Done | Desktop |
| MediaPipe 6-emotion face analysis | Done | Desktop |
| Apple Watch BLE HR/HRV collection | Done | Desktop |
| Gaze tracking (iris-based + blendshape fusion) | Done | Desktop |
| Face calibration (3-step: neutral/smile/eyes wide) | Done | Desktop |
| Gaze calibration (9-point polynomial fit) | Done | Desktop |
| Per-chunk Gemini Vision DFA extraction | Done | Backend |
| Context chaining between chunks | Done | Backend |
| Gaze overlay on extracted frames | Done | Backend |
| 1Hz temporal fusion (3 streams -> DataFrame) | Done | Backend |
| PASS/WARN/FAIL verdict per state | Done | Backend |
| Playtest health score (0-100) | Done | Backend |
| Snowflake medallion writes (Bronze->Silver->Gold) | Done | Backend |
| bge-large-en embeddings -> VectorAI | Done | Backend |
| Gemini session + cross-tester insights | Done | Backend |
| Session review with 4 tabs + 6 charts | Done | Web App |
| Cross-tester aggregate + health trend | Done | Web App |
| Interactive landing page demo (Mario data) | Done | Website |
| Scroll-driven 207-frame canvas animation | Done | Website |
| In-browser game recorder (WebM chunks) | Done | Game |
| 3 upload threads (chunks, emotions, watch) | Done | Desktop |
| MOCK_MODE for all external services | Done | Backend |

---

## 13. FEATURES — COMING NEXT

| Feature | Description | Component |
|---------|-------------|-----------|
| **Dual Frame Processing** | Send extracted JPEG frames as inline `Part.from_bytes()` to Gemini instead of uploading whole video. Enables frame-by-frame DFA comparison and eliminates the video upload/wait cycle. | Backend (`gemini_client.py`, `chunk_processor.py`) |
| **DFA Transition Function Prompt** | Reframe the Gemini prompt as "You are a DFA transition function. CURRENT STATE is X. Process each frame sequentially and report state transitions." Passes current state context for precise transition detection. | Backend (`chunk_processor.py`) |
| **Sphinx NL Analytics** | Full natural language -> SQL/visualization pipeline over Snowflake + VectorAI data. Endpoint exists, client needs implementation. | Backend (`sphinx_client.py`) |

---

## 14. DATA FLOW

```
Desktop Client / Browser Game
  |-- Screen Capture (chunks) --> POST /upload-chunk --> Gemini Vision DFA
  |-- Webcam (emotion frames) --> POST /emotion-frames --> Bronze_Presage
  |-- Apple Watch BLE (HR/HRV) --> WS /watch-stream --> Bronze_Watch
  +-- Face Video ---------------> POST /upload-face-video
                                          |
                              POST /finalize
                                          |
                          +---------------+------------------+
                          v               v                  v
                    Stitch Chunks    Fuse Streams      Write Snowflake
                    (DFA timeline)   (1Hz DataFrame)   (Bronze->Silver->Gold)
                          |               |                  |
                          +-------+-------+                  |
                                  v                          |
                           Verdicts + Health ----------------+
                                  |
                                  v
                         Embeddings -> VectorAI
                         Gemini Insights
```

---

## 15. DEMO — Mario 1-1

**Why Mario?** Universal recognition, known emotional beats, reliable failure points, strong narrative hook.

**Core finding:**
First pit appears before pit mechanics are taught.
Frustration spike > intended tense range.
Verdict: FAIL.

**Memorable pitch line:**
*"We just found a 40-year-old design flaw in the most famous level ever made."*

---

## 16. TECH STACK SUMMARY

| Layer | Technology |
|-------|------------|
| Website | React 19, Vite 7, Tailwind CSS 4, Recharts 3 |
| Web App | React 19, Vite 7, Recharts 3 |
| Backend | FastAPI, Python 3.13, Pydantic |
| AI/Vision | Google Gemini 2.5 Flash (`google-genai`) |
| Emotion | MediaPipe FaceLandmarker (478-point mesh, 52 blendshapes) |
| Embeddings | sentence-transformers (bge-large-en, 1024-dim) |
| Data Warehouse | Snowflake (Medallion: Bronze -> Silver -> Gold) |
| Vector DB | Actian VectorAI (HNSW index) |
| Desktop | Python tkinter, OpenCV, mss, bleak (BLE) |
| Game Capture | HTML5 Canvas, MediaRecorder (WebM VP9) |
