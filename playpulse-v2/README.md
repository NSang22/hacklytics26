# PlayPulse v2

**Multimodal Video Game Playtesting Analytics Platform**  
Hacklytics 2026 | Georgia Tech | Entertainment Track

## Architecture

```
playpulse-v2/
├── backend/          # FastAPI (Python 3.11+)
│   ├── main.py       # All endpoints
│   ├── models.py     # Pydantic models (DFA, sessions, verdicts)
│   ├── fusion.py     # Temporal fusion engine (3-stream → 1-sec rows)
│   ├── verdict.py    # Intent vs reality comparison + health score
│   ├── embedding.py  # 10-sec window embeddings for VectorAI
│   ├── chunk_processor.py  # Gemini chunk orchestration + stitching
│   ├── presage_client.py   # Presage emotion detection (stub)
│   ├── gemini_client.py    # Gemini 2.0 Flash (stub)
│   ├── snowflake_client.py # Snowflake medallion architecture (stub)
│   ├── vectorai_client.py  # Actian VectorAI (stub)
│   └── sphinx_client.py    # Sphinx NL query (stub)
├── game/             # Demo game (HTML5 Canvas, 5 DFA states)
│   ├── index.html    # Full game + webcam + recording
│   └── chunked-recorder.js  # 15-sec chunk capture + upload
├── frontend/         # React + Vite dashboard
│   └── src/pages/
│       ├── ProjectSetup.jsx        # DFA editor + project creation
│       ├── SessionManagement.jsx   # Create sessions, track status
│       ├── SessionReview.jsx       # Emotion timeline, verdicts, health score
│       ├── CrossTesterAggregate.jsx # Multi-tester comparison
│       └── SphinxExplorer.jsx      # Natural language queries
├── run.ps1           # Windows launcher
└── run.sh            # macOS/Linux launcher
```

## Quick Start

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
python main.py          # → http://localhost:8000
```

### 2. Frontend
```bash
cd frontend
npm install
npx vite                # → http://localhost:3000
```

### 3. Demo Game
```bash
cd game
python -m http.server 8080   # → http://localhost:8080
```

## Key Concepts

- **DFA Model**: Game progression modelled as a Deterministic Finite Automaton with 5 states
- **Chunked Recording**: Canvas gameplay captured as 15-sec .webm chunks, uploaded and processed by Gemini during gameplay
- **Three Data Streams**: Presage emotions (~10Hz) + Gemini DFA states + Apple Watch HR/HRV (~1Hz)
- **Temporal Fusion**: All streams resampled onto a unified 1-second timeline
- **Verdicts**: PASS / WARN / FAIL per DFA state based on intent vs reality deviation
- **Playtest Health Score**: Single 0-1 metric for the entire session

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/projects` | Create project with DFA config |
| GET | `/v1/projects/:id` | Get project details |
| PUT | `/v1/projects/:id/dfa` | Update DFA states |
| POST | `/v1/projects/:id/sessions` | Create tester session |
| POST | `/v1/sessions/:id/upload-chunk` | Upload 15-sec gameplay chunk |
| POST | `/v1/sessions/:id/upload-face-video` | Upload face video for Presage |
| POST | `/v1/sessions/:id/finalize` | Run full fusion + verdict pipeline |
| GET | `/v1/sessions/:id/timeline` | Fused 1-second timeline |
| GET | `/v1/sessions/:id/verdicts` | Per-state verdict cards |
| GET | `/v1/sessions/:id/health-score` | Playtest Health Score |
| GET | `/v1/sessions/:id/insights` | Gemini-generated analysis |
| GET | `/v1/projects/:id/aggregate` | Cross-tester summary |
| POST | `/v1/projects/:id/sphinx-query` | Natural language query |
| POST | `/v1/projects/:id/vector-search` | Similarity search |
| WS | `/v1/sessions/:id/watch-stream` | Live Apple Watch data |

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in API keys:
- `PRESAGE_API_KEY` — Presage Insights
- `GEMINI_API_KEY` — Google Gemini
- `SNOWFLAKE_*` — Snowflake credentials
- `VECTORAI_*` — Actian VectorAI
- `SPHINX_*` — Sphinx AI
