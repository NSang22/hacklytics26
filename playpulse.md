# PlayPulse — Implementation Guide for Claude Code

> This document contains everything needed to build PlayPulse, a multimodal video game beta testing analytics platform. Read this fully before writing any code.

---

## Project Overview

PlayPulse is a platform that lets game developers run playtests where the PLAYER is monitored (facial emotions, heart rate, behavior) alongside game telemetry (events, actions, state changes). The system compares the player's actual emotional journey against the developer's intended emotional design to surface actionable game design insights.

### Components to Build

1. **PlayPulse JS SDK** — lightweight client library games integrate to emit events
2. **Demo Game** — 2D browser game (HTML5 Canvas) with 5 emotional segments
3. **Tester Client Page** — browser page combining the game + Presage SDK webcam
4. **Backend API** — WebSocket + REST server for event ingestion, session management, fusion
5. **Developer Portal / Dashboard** — React app for creating tests, monitoring live, reviewing analytics
6. **Data Pipeline** — Snowflake (structured storage) + Actian VectorAI (embeddings)
7. **AI Layer** — Gemini (playthrough analysis + insight generation) + ElevenLabs (audio reports)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Demo Game | HTML5 Canvas + vanilla JS (single file, runs in browser) |
| Tester Client | HTML/JS page embedding game + Presage SDK |
| PlayPulse SDK | Vanilla JS class (~50 lines), distributed as single file |
| Backend | Python FastAPI on Vultr |
| WebSocket | FastAPI WebSocket endpoints (or `websockets` library) |
| Database | Snowflake (structured data) + Actian VectorAI (embeddings) |
| Frontend | React (developer portal + analytics dashboard) |
| AI | Google Gemini API (vision + text) + ElevenLabs API (voice) |
| Hosting | Vultr cloud instance |

---

## 1. PlayPulse JS SDK

This is the universal client library any game integrates. Keep it minimal — single file, no dependencies, ~50 lines.

### File: `playpulse-sdk.js`

```javascript
class PlayPulseSDK {
  constructor(sessionId, apiKey, endpoint) {
    this.sessionId = sessionId;
    this.apiKey = apiKey;
    this.startTime = Date.now();
    this.queue = [];
    this.endpoint = endpoint || 'ws://localhost:8000/v1/stream';
    this.ws = new WebSocket(`${this.endpoint}?session_id=${sessionId}&api_key=${apiKey}`);
    
    this.ws.onopen = () => {
      this.connected = true;
      this.send('session_start', 'connected');
      // Flush queue
      this.queue.forEach(msg => this.ws.send(JSON.stringify(msg)));
      this.queue = [];
    };
    
    this.ws.onerror = (err) => console.error('[PlayPulse] WebSocket error:', err);
    this.ws.onclose = () => { this.connected = false; };
  }

  _getTimestamp() {
    return (Date.now() - this.startTime) / 1000;
  }

  send(eventType, eventName, payload = {}) {
    const msg = {
      session_id: this.sessionId,
      event_type: eventType,
      event_name: eventName,
      timestamp: this._getTimestamp(),
      payload
    };
    if (this.connected) {
      this.ws.send(JSON.stringify(msg));
    } else {
      this.queue.push(msg);
    }
  }

  gameEvent(name, payload = {})    { this.send('game_event', name, payload); }
  playerAction(name, payload = {}) { this.send('player_action', name, payload); }
  stateChange(name, payload = {})  { this.send('state_change', name, payload); }
  milestone(name, payload = {})    { this.send('milestone', name, payload); }
  metric(name, payload = {})       { this.send('metric', name, payload); }

  endSession(payload = {}) {
    this.send('session_end', 'complete', {
      ...payload,
      total_time_sec: this._getTimestamp()
    });
    setTimeout(() => this.ws.close(), 500);
  }
}
```

### Event Schema

Every event follows this JSON structure:

```json
{
  "session_id": "string — unique session ID",
  "event_type": "session_start | session_end | game_event | player_action | state_change | milestone | metric",
  "event_name": "string — developer-defined name",
  "timestamp": 0.000,
  "payload": {}
}
```

**event_type definitions:**
- `session_start` / `session_end` — session lifecycle
- `game_event` — something happened in the game (death, pickup, spawn)
- `player_action` — deliberate player input (jump, attack, open menu)
- `state_change` — game state transition (entered level, cutscene start)
- `milestone` — developer-marked key moment (surprise trigger, boss encounter)
- `metric` — continuous polled measurement (position, health, score)

---

## 2. Demo Game

A 2D browser game with 5 intentional emotional segments. Build with HTML5 Canvas. Total playtime: 2-3 minutes.

### Game Segments

| # | Segment | Duration | Intended Emotion | Mechanics |
|---|---|---|---|---|
| 1 | Tutorial | 30s | Calm, confident | Move with arrow keys / WASD, pick up key, open door |
| 2 | Puzzle Room | 45-60s | Curious, mildly challenging | Find a hidden path or item. Make it slightly non-obvious so ~50% of testers get stuck for 20-30s. |
| 3 | Surprise Event | 10s | Surprise, excitement | Sudden event: floor drops, enemies appear, screen shakes. Something unexpected. |
| 4 | Gauntlet | 45-60s | Tense but fair | Dodge obstacles (moving platforms, spikes). Timing-based. Player can die and respawn. |
| 5 | Victory | 15s | Satisfaction, relief | Win screen with celebration effects. |

### Implementation Notes

- Single HTML file with `<canvas>` element
- Simple geometric shapes (colored rectangles/circles) — do NOT spend time on art
- Player: colored square that moves with arrow keys
- Enemies/obstacles: red shapes that kill on contact
- Key: yellow circle, door: brown rectangle that disappears when key collected
- Hidden path: a section of wall that looks solid but can be walked through (non-obvious for testers)
- Death: respawn at segment start, increment death counter
- Emit PlayPulse SDK events at every state transition, death, pickup, milestone
- Include a "stuck detector" — if player position hasn't changed significantly in 30s within a puzzle area, emit `stuck_detected` event
- Position polling: emit `metric('player_state', {x, y, hp})` every 2 seconds

### Integration with Presage

The game page should also initialize the Presage SDK to capture webcam data:

```html
<div id="game-container">
  <canvas id="game" width="800" height="600"></canvas>
</div>
<script src="playpulse-sdk.js"></script>
<script src="game.js"></script>
<script>
  // Initialize PlayPulse SDK
  const pp = new PlayPulseSDK(SESSION_ID, API_KEY, WS_ENDPOINT);
  
  // Initialize Presage SDK (follow their docs for exact API)
  // Presage data should stream to the same backend via its own WebSocket or REST calls
  // Key: use the same session_id so data can be joined by timestamp
</script>
```

---

## 3. Backend API (FastAPI)

### Project Structure

```
backend/
├── main.py              # FastAPI app, WebSocket + REST endpoints
├── models.py            # Pydantic models for events, sessions, projects
├── fusion.py            # Timestamp alignment + emotion-event fusion
├── snowflake_client.py  # Snowflake read/write
├── vectorai_client.py   # Actian VectorAI embedding store
├── gemini_client.py     # Gemini API calls (playthrough analysis, insights)
├── elevenlabs_client.py # ElevenLabs voice report generation
├── requirements.txt
└── .env                 # API keys (GEMINI_KEY, ELEVENLABS_KEY, SNOWFLAKE_*, etc.)
```

### Core Endpoints

#### WebSocket — Real-Time Event Ingestion

```python
from fastapi import FastAPI, WebSocket
from datetime import datetime
import json

app = FastAPI()

# In-memory session stores (replace with Snowflake for persistence)
sessions = {}        # session_id -> session metadata
session_events = {}  # session_id -> list of game events
session_emotions = {} # session_id -> list of presage emotion frames

@app.websocket("/v1/stream")
async def stream_events(websocket: WebSocket, session_id: str, api_key: str):
    await websocket.accept()
    
    if session_id not in session_events:
        session_events[session_id] = []
    
    try:
        while True:
            data = await websocket.receive_text()
            event = json.loads(data)
            event['received_at'] = datetime.utcnow().isoformat()
            session_events[session_id].append(event)
            
            # Broadcast to any dashboard clients watching this session
            await broadcast_to_dashboard(session_id, event)
            
            # Write to Snowflake bronze layer (async/batched)
            await write_to_snowflake_bronze(session_id, event)
    except Exception:
        pass  # Client disconnected


@app.websocket("/v1/presage-stream")
async def presage_stream(websocket: WebSocket, session_id: str):
    """Separate stream for Presage SDK emotion data."""
    await websocket.accept()
    
    if session_id not in session_emotions:
        session_emotions[session_id] = []
    
    try:
        while True:
            data = await websocket.receive_text()
            frame = json.loads(data)
            # Expected format:
            # {
            #   "timestamp": 12.5,
            #   "emotions": {"frustration": 0.2, "confusion": 0.1, "delight": 0.7, ...},
            #   "heart_rate": 78,
            #   "breathing_rate": 14,
            #   "engagement": 0.8,
            #   "gaze": {"x": 0.5, "y": 0.3}
            # }
            session_emotions[session_id].append(frame)
            await broadcast_to_dashboard(session_id, {'type': 'emotion', **frame})
    except Exception:
        pass
```

#### REST — Session Management

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
import uuid

class CreateProjectRequest(BaseModel):
    name: str
    segments: List[Dict]  # [{"name": "tutorial", "intended_emotion": "calm", "order": 1}, ...]
    optimal_playthrough_url: Optional[str] = None

class CreateSessionRequest(BaseModel):
    project_id: str
    tester_name: Optional[str] = None

@app.post("/v1/projects")
async def create_project(req: CreateProjectRequest):
    project_id = str(uuid.uuid4())[:8]
    api_key = f"pp_{uuid.uuid4().hex[:16]}"
    # Store project config (segments, intents, optimal playthrough)
    projects[project_id] = {
        "id": project_id,
        "name": req.name,
        "api_key": api_key,
        "segments": req.segments,
        "sessions": [],
        "created_at": datetime.utcnow().isoformat()
    }
    return {"project_id": project_id, "api_key": api_key}

@app.post("/v1/projects/{project_id}/sessions")
async def create_session(project_id: str, req: CreateSessionRequest):
    session_id = str(uuid.uuid4())[:8]
    session = {
        "id": session_id,
        "project_id": project_id,
        "tester_name": req.tester_name,
        "status": "created",
        "created_at": datetime.utcnow().isoformat()
    }
    sessions[session_id] = session
    session_events[session_id] = []
    session_emotions[session_id] = []
    projects[project_id]["sessions"].append(session_id)
    
    join_url = f"https://playpulse.dev/test/{session_id}"
    return {"session_id": session_id, "join_url": join_url}

@app.get("/v1/sessions/{session_id}/analysis")
async def get_analysis(session_id: str):
    """Return fused analysis: game events + emotions + intent comparison."""
    events = session_events.get(session_id, [])
    emotions = session_emotions.get(session_id, [])
    project_id = sessions[session_id]["project_id"]
    segments = projects[project_id]["segments"]
    
    # Fuse events and emotions by timestamp
    fused = fuse_events_and_emotions(events, emotions)
    
    # Compare against intended emotions per segment
    intent_comparison = compare_intent_vs_reality(fused, segments)
    
    return {
        "session_id": session_id,
        "fused_timeline": fused,
        "intent_comparison": intent_comparison,
        "summary_stats": compute_session_stats(fused)
    }

@app.get("/v1/projects/{project_id}/aggregate")
async def get_aggregate(project_id: str):
    """Cross-tester aggregate analytics."""
    project = projects[project_id]
    all_sessions = [session_events[sid] for sid in project["sessions"]]
    all_emotions = [session_emotions[sid] for sid in project["sessions"]]
    
    # Aggregate across testers
    segment_scores = aggregate_segment_scores(all_sessions, all_emotions, project["segments"])
    pain_points = find_pain_points(all_sessions, all_emotions)
    
    return {
        "project_id": project_id,
        "num_testers": len(project["sessions"]),
        "segment_scores": segment_scores,
        "pain_points": pain_points
    }
```

### Fusion Engine (`fusion.py`)

```python
import bisect
from typing import List, Dict

def fuse_events_and_emotions(events: List[Dict], emotions: List[Dict]) -> List[Dict]:
    """
    Align game events with emotion data by timestamp.
    For each game event, find the closest emotion frame.
    For each emotion frame, find what game state was active.
    Returns a unified timeline.
    """
    emotion_timestamps = [e['timestamp'] for e in emotions]
    
    fused = []
    for event in events:
        t = event['timestamp']
        # Find closest emotion frame
        idx = bisect.bisect_left(emotion_timestamps, t)
        idx = min(idx, len(emotions) - 1)
        
        closest_emotion = emotions[idx] if emotions else {}
        
        fused.append({
            'timestamp': t,
            'event': event,
            'emotion': closest_emotion,
            'contextualized': contextualize(event, closest_emotion)
        })
    
    return fused

def contextualize(event: Dict, emotion: Dict) -> str:
    """Generate a human-readable contextualized insight."""
    emotions = emotion.get('emotions', {})
    frustration = emotions.get('frustration', 0)
    confusion = emotions.get('confusion', 0)
    delight = emotions.get('delight', 0)
    
    event_name = event.get('event_name', '')
    
    if event_name == 'player_death' and frustration > 0.7:
        return f"Player died and showed high frustration ({frustration:.1%})"
    if event_name == 'stuck_detected' and confusion > 0.6:
        return f"Player stuck with high confusion ({confusion:.1%}) — likely unclear design"
    if event_name == 'milestone' and delight > 0.6:
        return f"Milestone reached with positive response ({delight:.1%})"
    
    return ""

def compare_intent_vs_reality(fused: List[Dict], segments: List[Dict]) -> List[Dict]:
    """
    Compare actual emotions against developer's intended emotions per segment.
    """
    results = []
    for segment in segments:
        segment_name = segment['name']
        intended = segment['intended_emotion']
        
        # Find all fused entries within this segment's time range
        # (determine segment boundaries from state_change events)
        segment_emotions = get_emotions_for_segment(fused, segment_name)
        
        if not segment_emotions:
            results.append({
                'segment': segment_name,
                'intended': intended,
                'actual': 'no_data',
                'match': None
            })
            continue
        
        # Average emotions across the segment
        avg_emotions = average_emotions(segment_emotions)
        dominant_actual = max(avg_emotions, key=avg_emotions.get)
        
        # Score intent match
        intent_met = intended.lower() in dominant_actual.lower() or \
                     emotion_similarity(intended, dominant_actual) > 0.6
        
        results.append({
            'segment': segment_name,
            'intended': intended,
            'actual_dominant': dominant_actual,
            'actual_distribution': avg_emotions,
            'intent_met': intent_met,
            'deviation_score': compute_deviation(intended, avg_emotions)
        })
    
    return results
```

---

## 4. Developer Portal / Dashboard (React)

### Pages

**1. Project Setup Page**
- Create new project: name, game title
- Define segments: name + intended emotion for each (drag-and-drop reorder)
- Upload optimal playthrough video (optional — for Gemini analysis)
- Get API key
- Create tester sessions → get join URLs

**2. Live Monitoring Page**
- Real-time per-tester emotion graph (line chart, updating every second)
- Game event markers overlaid on emotion timeline
- Current segment indicator
- Multiple testers visible simultaneously (tabs or grid)

**3. Session Review Page (Post-Test)**
- Full emotional heatmap timeline for one tester
- Game events annotated on timeline with emotion at that moment
- Intent vs reality comparison per segment (green = met, red = missed)
- Gemini-generated natural language insights
- Audio report player (ElevenLabs)

**4. Aggregate Analytics Page**
- Cross-tester comparison: all testers' emotion curves overlaid
- Per-segment scores: avg frustration, confusion, delight across all testers
- Pain point rankings: segments ranked by intent deviation
- VectorAI-powered: "similar moments" panel, tester clustering

### Key Dashboard Components

**Emotion Timeline Chart:**
- X-axis: time (seconds)
- Y-axis: emotion intensity (0-1)
- Lines: frustration (red), confusion (orange), delight (green), surprise (blue), engagement (purple)
- Vertical markers: game events (death = skull icon, milestone = star, etc.)
- Background shading: colored by intended emotion per segment

**Intent vs Reality Card:**
```
┌─────────────────────────────────────────┐
│ Puzzle Room                             │
│ Intended: Curious    Actual: Frustrated │
│ ████████████░░░░░░░  Frustration: 0.78  │
│ ██████████░░░░░░░░░  Confusion:   0.65  │
│ ███░░░░░░░░░░░░░░░░  Curiosity:   0.22  │
│                                         │
│ ⚠️ INTENT MISSED — deviation: 0.72     │
│ Insight: "Avg time stuck: 2:30 vs       │
│ intended 0:30. Gaze suggests players    │
│ don't notice the hidden path."          │
└─────────────────────────────────────────┘
```

### Tech: React with Recharts or Chart.js for graphs. WebSocket connection to backend for live updates.

---

## 5. Snowflake Integration

### Schema

**Bronze (raw events):**
```sql
CREATE TABLE bronze_events (
    id STRING,
    session_id STRING,
    event_source STRING,  -- 'game_sdk' or 'presage' or 'watch'
    event_type STRING,
    event_name STRING,
    timestamp_sec FLOAT,
    payload VARIANT,      -- raw JSON
    received_at TIMESTAMP_NTZ
);
```

**Silver (cleaned + aligned):**
```sql
CREATE TABLE silver_timeline (
    session_id STRING,
    timestamp_sec FLOAT,
    -- Game state
    current_segment STRING,
    game_event STRING,
    game_payload VARIANT,
    -- Emotions (from Presage)
    frustration FLOAT,
    confusion FLOAT,
    delight FLOAT,
    surprise FLOAT,
    boredom FLOAT,
    engagement FLOAT,
    -- Physiology
    heart_rate FLOAT,
    breathing_rate FLOAT,
    -- Gaze
    gaze_x FLOAT,
    gaze_y FLOAT,
    -- Quality
    emotion_confidence FLOAT,
    data_quality_score FLOAT
);
```

**Gold (aggregated):**
```sql
CREATE TABLE gold_segment_scores (
    project_id STRING,
    session_id STRING,
    segment_name STRING,
    intended_emotion STRING,
    -- Averaged metrics for segment
    avg_frustration FLOAT,
    avg_confusion FLOAT,
    avg_delight FLOAT,
    avg_surprise FLOAT,
    avg_engagement FLOAT,
    avg_heart_rate FLOAT,
    -- Comparison
    dominant_emotion STRING,
    intent_met BOOLEAN,
    deviation_score FLOAT,
    time_in_segment_sec FLOAT,
    deaths_in_segment INT,
    stuck_events INT
);
```

### Access Pattern
Use Snowflake REST API (`/api/v2/statements`) to execute SQL from the backend. The student 120-day trial is free.

---

## 6. Actian VectorAI Integration

### What Gets Embedded

For each tester, for each segment, compute an emotional journey embedding:

```python
# Embedding vector for one segment of one tester's playtest
embedding = [
    avg_frustration,    # 0-1
    avg_confusion,      # 0-1
    avg_delight,        # 0-1
    avg_surprise,       # 0-1
    avg_engagement,     # 0-1
    avg_heart_rate_normalized,  # 0-1
    time_in_segment_normalized, # ratio vs expected
    deaths_in_segment,  # count
    intent_deviation,   # 0-1 how far from intended
    stuck_events_count  # count
]
```

### Storage

```python
# Store embedding
vectorai.insert({
    "id": f"{session_id}_{segment_name}",
    "vector": embedding,
    "metadata": {
        "session_id": session_id,
        "project_id": project_id,
        "segment_name": segment_name,
        "tester_name": tester_name,
        "dominant_emotion": dominant_emotion,
        "intent_met": intent_met
    }
})
```

### Queries

```python
# Find all segments similar to this frustrating puzzle experience
results = vectorai.search(
    vector=puzzle_room_embedding,
    top_k=10,
    filter={"project_id": project_id}
)
# Returns: other tester segments with similar emotional profiles

# Find all high-frustration moments
results = vectorai.search(
    vector=[0.9, 0.8, 0.1, 0.1, 0.2, ...],  # high-frustration template
    top_k=20
)
```

### Setup
```bash
docker pull williamimoh/actian-vectorai-db:1.0b
docker run -p 5555:5555 williamimoh/actian-vectorai-db:1.0b
```
Reference: https://github.com/hackmamba-io/actian-vectorAI-db-beta

---

## 7. Gemini Integration

### Optimal Playthrough Analysis

```python
import google.generativeai as genai

def analyze_optimal_playthrough(video_path: str, segments: list) -> dict:
    """Process developer's optimal playthrough to build intended experience map."""
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    video = genai.upload_file(video_path)
    
    prompt = f"""Analyze this game playthrough video. The developer has defined these segments 
    with intended emotions:
    
    {json.dumps(segments, indent=2)}
    
    For each segment, identify:
    1. When it starts and ends (timestamp)
    2. Key events that happen
    3. Expected player behavior and timing
    4. What visual/audio cues guide the player
    
    Return as JSON:
    {{
      "segments": [
        {{
          "name": "tutorial",
          "start_time": 0.0,
          "end_time": 28.5,
          "key_events": ["player picks up key", "player opens door"],
          "expected_duration_sec": 30,
          "design_cues": ["key is glowing yellow", "door has arrow indicator"]
        }}
      ]
    }}"""
    
    response = model.generate_content([video, prompt])
    return json.loads(response.text)
```

### Natural Language Insight Generation

```python
def generate_session_insights(fused_data: list, intent_comparison: list) -> str:
    """Generate developer-facing analysis from fused playtest data."""
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""You are a game design analyst. Based on this playtest data, 
    generate actionable insights for the game developer.
    
    Intent vs Reality comparison:
    {json.dumps(intent_comparison, indent=2)}
    
    Key moments (high frustration, confusion, or delight):
    {json.dumps(get_key_moments(fused_data), indent=2)}
    
    Write a concise analysis covering:
    1. Which segments worked as intended
    2. Which segments missed their emotional target and why
    3. Specific, actionable recommendations
    
    Keep it under 200 words. Be direct."""
    
    response = model.generate_content(prompt)
    return response.text
```

### Cross-Tester Aggregate Insights

```python
def generate_aggregate_insights(all_intent_comparisons: list, pain_points: list) -> str:
    """Generate cross-player pattern analysis."""
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""Analyze these aggregated playtest results from {len(all_intent_comparisons)} testers.
    
    Segment scores across all testers:
    {json.dumps(aggregate_scores, indent=2)}
    
    Recurring pain points:
    {json.dumps(pain_points, indent=2)}
    
    Generate a cross-tester analysis covering:
    1. Universal pain points (segments where most testers struggled)
    2. Segments that consistently work well
    3. Tester variance (where opinions diverge)
    4. Priority recommendations ranked by impact
    
    Keep it under 300 words. Be specific and actionable."""
    
    response = model.generate_content(prompt)
    return response.text
```

---

## 8. ElevenLabs Integration

```python
import requests

def generate_audio_report(text: str, session_id: str) -> str:
    """Generate voice-narrated playtest report."""
    
    response = requests.post(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE_ID",
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.7,
                "similarity_boost": 0.8
            }
        }
    )
    
    audio_path = f"reports/{session_id}_report.mp3"
    with open(audio_path, 'wb') as f:
        f.write(response.content)
    
    return audio_path
```

---

## 9. Environment Variables

```env
# Gemini
GEMINI_API_KEY=your_key_here

# ElevenLabs
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=your_voice_id

# Snowflake
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=playpulse
SNOWFLAKE_SCHEMA=public
SNOWFLAKE_WAREHOUSE=compute_wh

# Actian VectorAI
VECTORAI_HOST=localhost
VECTORAI_PORT=5555

# Vultr (deployment)
VULTR_API_KEY=your_key_here

# Presage
PRESAGE_API_KEY=your_key_here

# Sphinx
SPHINX_API_KEY=your_key_here
```

---

## 10. Deployment (Vultr)

### Backend
```bash
# On Vultr instance
pip install fastapi uvicorn websockets python-dotenv google-generativeai requests
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Docker Compose (if time allows)
```yaml
version: '3'
services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
  
  vectorai:
    image: williamimoh/actian-vectorai-db:1.0b
    ports:
      - "5555:5555"
  
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
```

---

## Build Priority Order

If running low on time, build in this order:

### MVP (Must Demo) — Hours 0-20
1. PlayPulse JS SDK (30 min)
2. Backend WebSocket event ingestion (2 hr)
3. Demo game with 5 segments + SDK integration (6 hr)
4. Presage SDK in tester client page (2 hr)
5. Basic dashboard: live emotion graph + game event markers (4 hr)
6. Fusion engine: align events + emotions by timestamp (2 hr)
7. Intent vs reality comparison logic (2 hr)

### Should Have — Hours 20-28
8. Snowflake pipeline (Bronze → Silver → Gold) (3 hr)
9. VectorAI embeddings + cross-tester similarity search (2 hr)
10. Gemini insight generation (session + aggregate) (2 hr)
11. Cross-tester aggregate dashboard (2 hr)

### Nice to Have — Hours 28-36
12. Gemini optimal playthrough video analysis (2 hr)
13. ElevenLabs audio reports (2 hr)
14. Sphinx notebook setup (2 hr)
15. Polish, video pitch, demo prep (4 hr)

---

## Key Decisions for Implementation

- **Timestamps are the join key.** Everything correlates on `timestamp` (seconds since session start). Game events, Presage emotion frames, and Watch data all use this same clock.
- **Session ID links everything.** Same session_id across game SDK, Presage stream, and Watch stream. This is how the backend fuses data from multiple sources for one tester.
- **Start simple, add layers.** Get game events + Presage emotions flowing to backend and visible on dashboard first. Then add Snowflake, VectorAI, Gemini, ElevenLabs as layers on top.
- **Pre-record backup testers.** If multi-tester live demo fails, have 2-3 pre-recorded sessions ready to show cross-tester analytics.