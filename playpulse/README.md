# PlayPulse

Multimodal video game beta testing analytics platform.

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm

### 1. Backend

```bash
cd playpulse/backend
pip install -r requirements.txt
python main.py
# → runs on http://localhost:8000
```

### 2. Frontend (Developer Dashboard)

```bash
cd playpulse/frontend
npm install
npm run dev
# → runs on http://localhost:3000
```

### 3. Demo Game

Open `playpulse/game/index.html` directly in a browser, or serve it:

```bash
# simple static server (Python)
cd playpulse/game
python -m http.server 8080
# → open http://localhost:8080/index.html?session_id=test1
```

### All-in-one (Windows)

```powershell
.\run.ps1
```

### All-in-one (Mac/Linux)

```bash
./run.sh
```

---

## Project Structure

```
playpulse/
├── sdk/playpulse-sdk.js          # Universal game event SDK
├── game/index.html               # Demo game (HTML5 Canvas)
├── backend/
│   ├── main.py                   # FastAPI app
│   ├── models.py                 # Pydantic models
│   ├── fusion.py                 # Event + emotion timestamp alignment
│   ├── snowflake_client.py       # Snowflake (stub)
│   ├── vectorai_client.py        # VectorAI (stub)
│   ├── gemini_client.py          # Gemini (stub)
│   ├── elevenlabs_client.py      # ElevenLabs (stub)
│   ├── requirements.txt
│   └── .env.example
├── frontend/                     # React + Vite dashboard
│   └── src/pages/
│       ├── CreateProject.jsx
│       ├── ProjectOverview.jsx
│       ├── LiveMonitor.jsx
│       ├── SessionReview.jsx
│       └── AggregateAnalytics.jsx
├── run.sh
├── run.ps1
└── README.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| WS | `/v1/stream?session_id=X&api_key=Y` | Game event ingestion |
| WS | `/v1/presage-stream?session_id=X` | Presage emotion ingestion |
| WS | `/v1/dashboard-stream/{session_id}` | Live broadcast to dashboard |
| POST | `/v1/projects` | Create project |
| GET | `/v1/projects/{id}` | Get project |
| POST | `/v1/projects/{id}/sessions` | Create session |
| GET | `/v1/sessions/{id}` | Get session |
| GET | `/v1/sessions/{id}/events` | List game events |
| GET | `/v1/sessions/{id}/emotions` | List emotion frames |
| GET | `/v1/sessions/{id}/analysis` | Fused analysis |
