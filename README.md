Hacklytics Most Innovative Use of Sphinx API

PatchLab — Multimodal Playtest Intelligence Engine
Hacklytics 2026 — Entertainment Track
PatchLab is a real-time multimodal playtest engine that measures player emotion via on-device facial analysis and biometrics, compares it to developer intent, and automatically identifies broken game mechanics.

Core Insight: Studios record what players do. PatchLab measures what players feel.

🚀 System Overview
PatchLab bridges the gap between gameplay and physiology by fusing three primary data streams into a unified 1Hz timeline.

Modality	Stream	Frequency	Purpose
Gameplay Video	Configurable	1-30 FPS	Extract DFA state transitions via Gemini Vision
Webcam	MediaPipe	10 Hz	Facial affect (52 ARKit blendshapes) + gaze tracking
Apple Watch	BLE	1 Hz	HR + HRV (physiological stress and arousal)
Developer Intent	Pre-session	N/A	Intended emotional arc per DFA state
🏗 Architecture Overview
The system is divided into four distinct stages, moving from local data collection to cloud-based AI reasoning.

Code snippet
graph TD
    subgraph "Stage 1: Collection (Desktop Client)"
    A[Screen Capture] --> B[Chunk Uploader]
    C[Webcam/MediaPipe] --> B
    D[Apple Watch BLE] --> B
    end

    subgraph "Stage 2: Processing (FastAPI Backend)"
    B --> E[Gemini 2.5 Flash Vision]
    E --> F[DFA State Extraction]
    F --> G[Fusion Engine 1Hz]
    G --> H[Gemini Reasoning Layer]
    end

    subgraph "Stage 3: Storage"
    H --> I[(Snowflake Medallion)]
    H --> J[(Actian VectorAI)]
    end

    subgraph "Stage 4: Dashboard (React)"
    I --> K[Session Review]
    J --> L[Cross-Tester Analytics]
    end
🛠 Features & Capabilities
1. Facial Affect & Gaze Tracking (MediaPipe)
Replaces standard SDKs with a custom formula-based emotion engine using 52 ARKit blendshapes.

Emotion Formulas: Maps specific blendshapes (e.g., browInnerUp, eyeWide, jawOpen) to Surprise, Delight, Frustration, Confusion, Boredom, and Engagement.

Calibration: Features a 3-step face calibration (Neutral → Smile → Eyes Wide) and 9-point polynomial gaze calibration.

Temporal Smoothing: Uses Differential EMA where positive emotions persist longer than negative ones to mimic human psychological recovery.

2. Deterministic Finite Automata (DFA) Extraction
PatchLab models game progression as a DFA. A Gemini 2.5 Flash vision prompt analyzes video chunks to identify:

Observed States: (e.g., "Boss_Fight", "Inventory_Menu")

Transition Triggers: What caused the state change.

Failure Indicators: Visual cues that the player is stuck or the game is bugged.

3. The Fusion Engine & Verdict Layer
The backend aligns emotion frames, heart rate data, and DFA states into a SILVER_FUSED table.

Intent Delta: Computes ∣actual_emotion−intended_emotion∣.

Health Score: * 🟢 PASS: Delta < 0.2

🟡 WARN: Delta 0.2 - 0.4

🔴 FAIL: Delta > 0.4

4. Storage Layer (Snowflake & Actian)
Snowflake: Implements a Medallion Architecture (Bronze/Silver/Gold) to transform raw biometric pings into executive session summaries.

Actian VectorAI: Stores 10-second sliding window embeddings to find "similar gameplay moments" across different testers.

🎮 Demo: The "Mario 1-1" Test
We tested PatchLab on Super Mario Bros Level 1-1 to find design friction.

Finding: The first pit appears before the "jump" mechanic is fully reinforced.

Data: Frustration spikes (detected via browDown and RMSSD drop) exceeded the intended "Tense" range.

Verdict: FAIL.

The Pitch: "We just found a 40-year-old design flaw in the most famous level ever made."

💻 Tech Stack
Layer	Technology
Desktop Client	Python, tkinter, mss, OpenCV, Pillow
Biometrics	MediaPipe FaceLandmarker, bleak (BLE)
Backend	Python, FastAPI, Pydantic
AI / LLM	Google Gemini 2.5 Flash
Data/Vector	Snowflake, Actian VectorAI
Frontend	React, Recharts, Tailwind CSS, Vite
