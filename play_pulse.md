# PlayPulse — Project Overview

**Hacklytics 2026 | Georgia Tech | Entertainment Track | 4 People | 36 Hours**

*"The game industry has been guessing how players feel. PlayPulse measures it."*

---

## The Problem

Game studios spend millions on playtesting every year, and the results are still mostly guesswork. The standard process looks like this: a tester plays the game while someone watches, the session gets recorded, and afterward the tester fills out a survey. Maybe they say "the boss fight was frustrating" or "the puzzle was confusing."

This process is broken in three ways. First, surveys are biased and delayed — by the time a tester writes their feedback, they've already rationalized their experience and forgotten the granular emotional details. Second, manual video review doesn't scale — nobody has time to watch 50 hours of playtest footage frame by frame. Third, and most importantly, existing tools tell developers what players did (where they clicked, where they died, how long they spent per level) but never how players actually felt while doing it.

PlayPulse closes this gap. It measures what players feel in real-time using biological signals, then compares those feelings against what the developer intended them to feel. The output isn't vague — it's a verdict per game segment: did reality match intent? If not, exactly where did it break and why?

---

## The Core Insight: Intent vs Reality

This is the killer feature that separates PlayPulse from everything else.

Before a playtest begins, the developer defines their game's structure as a series of states — think of them as chapters or segments. For each state, they annotate what emotion they intend the player to feel. A tutorial should feel calm. A puzzle should feel curious. A boss fight should feel tense but fair. A surprise event should feel exciting.

After the playtest, PlayPulse measures what the tester actually felt during each state — not from a survey, but from their face, their heart rate, their body. Then it compares actual against intended and produces a simple verdict: PASS (reality matched intent), WARN (close but off), or FAIL (the emotional experience was completely wrong).

This comparison — the intent delta — is the single most valuable piece of information a game designer can have. It tells them not just that something is broken, but specifically which segment is broken, what the player was supposed to feel, what they actually felt instead, and by how much the experience deviated from the design. And when the developer fixes something and runs another round of tests, the delta should improve. That measurable improvement is proof the fix worked.

No existing playtesting tool does this. Existing analytics platforms show you heatmaps of where players died. PlayPulse tells you those players were frustrated when they were supposed to be having fun — and that the problem started two segments earlier when the puzzle failed to teach the mechanic properly.

---

## How It Works — The Full Pipeline

### Step 1: Developer Sets Up the Test

The developer opens the PlayPulse dashboard and creates a new project. They define their game's DFA — Deterministic Finite Automaton. This is a computer science concept that means, in plain terms: the game is modeled as a series of states with transitions between them.

Think of a Mario level. The developer might define these states:

1. **Tutorial Entry** — flat ground, first goomba, learning the controls
2. **Tutorial Pipes** — pipe jumping section, learning jump distance
3. **Brick Platforming** — first real challenge with floating platforms and a chasm
4. **Mid-Level Enemies** — dense section with multiple enemy types
5. **Final Stairs + Flag** — endgame staircase and flag

For each state, the developer fills out a detailed form:

- **State name** — e.g. "tutorial_pipes"
- **Description** — what happens in this section, in plain English
- **Visual cues** — what does this section look like? (e.g. "green pipes, gaps between pipes, flat ground")
- **Failure indicators** — what does it look like when a player is struggling? (e.g. "player falls in gap", "walks backwards", "stands still for 10+ seconds")
- **Success indicators** — what does it look like when it's going well? (e.g. "clears all pipes without dying", "completes in under 20 seconds")
- **Intended emotion** — what should the player feel here? (dropdown: calm, curious, tense, surprised, satisfied, etc.)
- **Acceptable range** — how wide is the acceptable band for that emotion score? (e.g. 0.4 to 0.8)
- **Expected duration** — how long should this section take in an optimal playthrough?

The more detail the developer provides, the better the analysis. This is by design — PlayPulse's quality scales with the quality of the developer's intent annotations.

The developer also uploads a video of themselves playing the game "correctly" — the optimal playthrough. Gemini AI analyzes this video once to build a reference timeline: which states appear when, how long each takes, what the transitions look like visually.

### Step 2: Tester Plays the Game

The developer creates test sessions and gets URLs. Each tester opens their URL in a browser. The page has:

- The game itself (in our demo, an HTML5 Canvas game)
- Webcam access (for facial emotion capture via Presage)
- Apple Watch connection via Bluetooth (for heart rate and heart rate variability)

When the tester starts playing, three things happen simultaneously:

1. **The webcam records their face** as a continuous video file. This will be analyzed by Presage to extract emotions — frustration, confusion, delight, boredom, surprise, engagement — all scored 0 to 1 at roughly 10 readings per second.

2. **The game screen is recorded in 15-second chunks.** Every 15 seconds, the current chunk is finalized and immediately uploaded to our backend server. The backend sends it straight to Gemini Vision (Google's AI model) for analysis. This means Gemini starts understanding what's happening in the game while the tester is still playing. By the time the game ends, most of the gameplay has already been analyzed.

3. **The Apple Watch streams heart rate and HRV** (heart rate variability) in real-time over Bluetooth, roughly once per second. This physiological data captures stress, arousal, and emotional regulation that facial expressions alone might miss.

### Step 3: Gemini Analyzes the Gameplay (Chunked Batch Processing)

This is one of the most technically interesting parts of the system.

The gameplay video isn't sent to Gemini as one big file after the game ends. Instead, it's split into 15-second chunks that are processed progressively during gameplay.

Why 15 seconds? It's long enough for Gemini to see meaningful player behavior within a single chunk — a death, a respawn, a failed attempt, a moment of confusion. And it's short enough to process quickly — each chunk takes about 3 to 5 seconds for Gemini to analyze.

Each chunk is processed at 2 frames per second, meaning Gemini sees 30 frames per 15-second chunk. That's enough to track player movement, detect deaths, notice backtracking, and identify state transitions.

For each chunk, Gemini is given:

- The 15-second video clip
- The developer's full DFA state definitions (with all those visual cues, failure indicators, and success indicators)
- Context from the previous chunk (what state the player was in, how many deaths so far, what they were doing)

Gemini returns a structured analysis:

- Which DFA state(s) the player was in during this chunk
- Any state transitions (with exact timestamps)
- Events: deaths (and what caused them), moments where the player got stuck, backtracking, long pauses
- Player behavior classification: progressing, stuck, dying, exploring, rushing, confused
- A short summary of what happened

After all chunks are processed, the results are stitched together into a single continuous DFA timeline for the entire gameplay session.

Why we chose this approach over real-time streaming: Gemini's real-time streaming API caps at 1 frame per second and can't be increased. With chunked batch processing, we control the frame rate (2 FPS, or higher if needed), we get temporal context within each chunk, and processing starts during gameplay rather than waiting until the end.

We use two different Gemini models for different tasks: `gemini-2.0-flash` for the chunk analysis (fastest, cheapest — the task is straightforward visual classification), and `gemini-2.5-flash` for the optimal playthrough analysis and natural language insight generation (smarter, runs once or infrequently).

### Step 4: Temporal Fusion — Three Streams Become One Timeline

After the game ends, we have three data streams from different sources at different rates:

- **Presage emotions** at ~10 readings per second (high frequency)
- **Gemini DFA analysis** — states, transitions, and events extracted from 15-second chunks
- **Apple Watch HR/HRV** at ~1 reading per second

These need to be aligned onto a single unified timeline. We resample everything to one row per second of gameplay:

- Presage's 10 readings per second are averaged down to one per second
- Gemini's DFA state is "forward-filled" — if Gemini says the player entered the puzzle room at t=35 seconds, then every row from t=35 onward is labeled "puzzle_room" until the next transition
- Watch readings align directly at 1-to-1 since they're already at ~1 Hz

The result is a clean table: one row per second, containing the DFA state, all six emotion scores, heart rate, HRV, and derived metrics. This fused timeline is the foundation for everything that follows.

### Step 5: Verdicts — Intent vs Reality

For each DFA state, we compute a verdict:

1. Filter all the rows belonging to that state
2. Calculate the average score for the intended emotion across all those rows
3. Check if that average falls within the developer's acceptable range
4. Look at which emotion actually dominated — was it the intended one, or something else entirely?
5. Compute the time the player actually spent in the state vs the expected duration

The verdict is:

- **PASS** — the actual emotional experience matched what the developer intended. The player felt what they were supposed to feel.
- **WARN** — it was close but slightly off. Maybe the intended emotion scored within range but a different emotion was surprisingly high.
- **FAIL** — the emotional experience was wrong. The intended emotion scored below the acceptable range, or a completely different emotion dominated.

Each state also gets a deviation score (0 = perfect match, 1 = complete mismatch) and the time delta (how much longer or shorter the player took compared to the optimal playthrough).

### Step 6: Playtest Health Score

All the per-state verdicts are combined into a single headline number: the Playtest Health Score, ranging from 0 to 1.

- 1.0 means every state matched the developer's intent perfectly
- 0.5 means about half the states hit their targets
- 0.0 means the emotional experience was completely wrong everywhere

This is the number developers track across iterations. Fix the puzzle → run another round of tests → Playtest Health Score improves from 0.72 to 0.89. That's proof the fix worked.

---

## The Data Infrastructure

### Snowflake — Structured Data Warehouse

All the fused timeline data, verdicts, and session metadata are stored in Snowflake using a three-layer "medallion" architecture:

- **Bronze layer:** Raw data exactly as it came from each source (Presage, Gemini chunks, Watch). Append-only, never modified. This is the audit trail.
- **Silver layer:** The cleaned, fused 1-second timeline rows. Quality scores per row. Interpolated gaps where data was missing.
- **Gold layer:** Aggregated analytics — per-state verdict summaries, cross-session comparisons, Playtest Health Scores, time deltas.

When you have 5 or 10 or 50 testers, Snowflake handles the cross-session aggregation that makes the data actually useful. "What's the average frustration in the puzzle room across all testers?" is a SQL query against the Gold layer.

### Actian VectorAI — Emotional Pattern Search

Every 10 seconds of the fused timeline is converted into a numerical vector — a list of numbers representing the emotional profile of that window (average frustration, confusion, delight, heart rate, HRV, which DFA state, etc.). These vectors are stored in VectorAI, a vector database.

This enables semantic similarity search. You can ask: "Find every 10-second window across all testers where frustration was above 0.8 and the player was in the puzzle room." VectorAI returns the top matches with exact timestamps. The developer can go straight to the video footage of those moments.

You can also find patterns: "Find moments across all testers that look similar to this specific frustration spike." VectorAI finds them by comparing the numerical profiles, even if the exact emotion scores are slightly different.

### Sphinx — Natural Language Queries

Sphinx is an AI query agent that sits on top of Snowflake and VectorAI. Instead of writing SQL, the developer types a question in plain English and Sphinx generates the query, runs it, and returns a chart.

We have three killer demo queries:

**Query 1 — The Heatmap ("Where is it broken?")**

> "Group the playtest data by DFA state. Calculate the average frustration score and average heart rate for each state. Plot this as a color-coded heatmap."

This instantly shows which game segments are causing rage. Red cells = problems. Green cells = working as intended.

**Query 2 — The Delta ("Why is it broken?")**

> "Calculate the time difference between the optimal playthrough and the player playthrough for every state. Create a scatter plot showing this time difference on the X-axis and the average confusion score on the Y-axis."

This proves a causal relationship: players who got stuck (large time delta) were also confused (high confusion score). The cluster in the upper right corner is your highest priority fix.

**Query 3 — The Vector Similarity ("Show me the exact moments")**

> "Query VectorAI to find the top 5 most similar 10-second sequences where frustration > 0.8 and the player was in the puzzle room. Output the exact video timestamps."

This gives developers the exact tape to review. Five timestamps, ranked by severity. Go directly to the footage and see exactly what happened.

These three queries form a narrative: WHERE → WHY → SHOW ME. Demo them in this order and judges see a complete analytical workflow.

---

## The Demo Game

We build a simple 2D HTML5 Canvas game specifically designed to produce reliable emotional variation across our 5 DFA states. The game takes 2-3 minutes to play.

**State 1: Tutorial (30 seconds)**
Blue background, open room. Player learns to move with arrow keys, picks up a key, opens a door. Dead simple. This establishes a calm emotional baseline. If anyone shows frustration here, the tutorial design itself is broken.

**State 2: Puzzle Room (45-60 seconds)**
Green/dark background, enclosed space. There's a hidden path — a section of wall that looks solid but can be walked through. It's intentionally non-obvious. Roughly 50% of testers should get stuck for 20-30 seconds, which creates frustration variance in the data. This is the segment we expect to FAIL the intent check for many testers — and that's the point. It makes the cross-tester analytics interesting.

**State 3: Surprise Event (10 seconds)**
The floor drops, enemies appear, the screen flashes red. Completely unexpected. This is designed to trigger a visible heart rate spike and high surprise scores from Presage. Short, sharp, visceral.

**State 4: Gauntlet (45-60 seconds)**
Moving obstacles, timing-based dodging. The player can die and respawn. Death counter visible. This tests skill under pressure. Struggling testers accumulate frustration. Skilled testers show engagement and flow. The emotional response varies dramatically by player, which makes cross-tester comparison interesting.

**State 5: Victory (15 seconds)**
Bright celebration screen. "YOU WIN" text. Death count displayed. This should produce satisfaction and relief. If a tester still shows stress here, the preceding gauntlet was too punishing.

Each state has maximally distinct visual design so that Gemini can reliably detect transitions: different background colors, different visual elements, different UI overlays. This is critical for accurate DFA analysis.

---

## The Dashboard

A React web application with five pages:

**Project Setup** — Create a new project. The DFA State Editor is the centerpiece: a form where developers add, remove, and reorder states, filling in the description, visual cues, failure indicators, success indicators, intended emotion, acceptable range, and expected duration for each. Upload the optimal playthrough video. Launch test sessions.

**Session Review** — The single-tester deep dive. An emotion timeline chart shows all six emotions over time (frustration red, confusion orange, delight green, surprise blue, engagement purple) with the DFA states shown as colored background bands. Verdict cards per state (PASS/WARN/FAIL with scores). The Playtest Health Score displayed prominently. Gemini's natural language insights below.

**Cross-Tester Aggregate** — The big picture. All testers' emotion curves overlaid on the same timeline. Per-state verdict summary ("Tutorial: 5/5 PASS | Puzzle: 2/5 PASS, 3/5 FAIL"). Pain points ranked by failure rate and average frustration. Playtest Health Score comparison across all testers as a bar chart.

**Sphinx Explorer** — The power-user analysis layer. A text input where developers type natural language queries. Pre-loaded example queries (the three killer demos) clickable as buttons. Results render as charts, tables, or text directly in the page.

---

## Technologies and Why Each One Is Used

### Presage SDK — The Emotion Sensor

Presage is the primary source of emotional data. It analyzes the tester's face via webcam and outputs scores for frustration, confusion, delight, boredom, surprise, and engagement, plus camera-derived heart rate and breathing rate. Approximately 10 readings per second.

We're building for both live and batch modes. Live mode processes webcam frames in real-time during gameplay (preferred, still being tested). Batch mode records the webcam as a video file and sends it to Presage's API after the session for processing. The rest of the pipeline is identical regardless of which mode is used — it just consumes timestamped emotion data.

### Gemini Vision API — The Game Understanding Engine

Gemini is how PlayPulse understands what's happening in the game without any SDK or code integration. It watches the gameplay video (in 15-second chunks) and identifies DFA state transitions, player behavior, deaths, stuck moments, and backtracking.

This is what makes PlayPulse work with any game. We don't need access to the game's source code, we don't need developers to install an SDK, we don't need telemetry hooks. We just point Gemini at the screen recording. The developer's DFA state descriptions (visual cues, failure indicators, success indicators) serve as the prompt that tells Gemini what to look for.

Novel use: Gemini acts as the formal transition function of a Deterministic Finite Automaton. This is a computer science concept, not just marketing — the game's states and transitions form a formal DFA, and Gemini is the function that determines which state the system is in based on the observed visual input.

### Vultr — The Compute Infrastructure

Vultr hosts the entire processing pipeline: the FastAPI backend server, the WebSocket endpoint for Apple Watch data, the chunk processing queue, and the embedding generation for VectorAI. Not just hosting — the compute is structurally necessary for temporal resampling (aligning three data streams at different rates), chunk processing orchestration, and embedding generation.

### Snowflake — The Data Warehouse

Multi-session structured telemetry storage with real analytical workloads. The medallion architecture (Bronze/Silver/Gold) is genuinely justified because multiple testers generate structured time-series data that needs cross-session aggregation. When a developer asks "what's the average frustration across all testers in state X," that's a Snowflake query.

### Actian VectorAI — The Pattern Finder

Stores high-dimensional emotional profile embeddings for 10-second gameplay windows. Enables cross-session semantic search: "find all moments across all testers that look like this frustration spike." This is a genuinely novel use of a vector database — most vector DB applications store text embeddings for search. We store psychophysiological gameplay embeddings.

### Sphinx — The Natural Language Query Layer

Developer types a question in plain English, Sphinx generates the SQL or vector query, runs it, returns a chart. Three killer demo queries (heatmap, delta scatter plot, vector similarity search) show the full power. Judges expect Sphinx to be used for finance or business data. We're using it for rage heatmaps and frustration clustering. Novel application.

### Apple Watch — The Physiological Ground Truth

Heart rate and heart rate variability via Bluetooth Low Energy, streamed in real-time during gameplay. HRV is a validated physiological marker of stress and emotional regulation. The Watch provides data that facial expression analysis alone might miss — a player who maintains a neutral face but has an elevated HR is experiencing arousal that Presage wouldn't catch.

---

## Prizes We're Targeting

| Prize | Why We Win It |
|---|---|
| **Entertainment Track 1st** | This is literally a game playtesting tool. Exact match for the track description. |
| **Overall 1st-3rd** | Hits all 5 rubric criteria hard. DFA formalism = creativity. Full pipeline = technical depth. Judge-plays-and-sees-their-emotions = demo engagement. Research-level approach = soundness. |
| **Best Use of Vultr** | CPU + GPU compute both legitimately necessary. Not just hosting — the compute is the pipeline. |
| **Best Use of Presage SDK** | Presage is our primary sensor, not a tacked-on feature. Their challenge description literally says "gaming and entertainment." |
| **Best Use of Gemini API** | Novel application as a DFA transition function. Not chatbot, not summarization — formal state machine visual classification + behavioral analysis from video chunks. Plus NL insight generation. |
| **Best Use of Snowflake** | Medallion architecture with real multi-session aggregation workloads. Not a forced integration. |
| **Best Use of Actian VectorAI** | Cross-session emotional trajectory search. "Find all frustration moments in Room A." Novel vector DB use case. |
| **Best Use of Sphinx** | Natural language queries over psychophysiological game telemetry. They expect finance data. We give them rage heatmaps. $400 cash prize. |
| **Best Use of ElevenLabs** | (If time) Voice-narrated playtest reports. Developer listens while reviewing footage. |

Maximum target: 9 prize categories. Minimum viable: 5 (Entertainment + Overall + Presage + Gemini + Vultr).

---

## Team Roles and 36-Hour Schedule

### Person 1 — Game Developer + Recording Infrastructure

**Primary deliverable:** The demo game and the tester-side recording system.

Build the 2D HTML5 Canvas game with 5 visually distinct states and real gameplay mechanics. Build the chunked screen recorder that splits gameplay into 15-second video chunks and uploads them to the backend during gameplay. Build the webcam recorder for Presage. Integrate Apple Watch BLE. Pre-record 3-5 real playtest sessions with genuine data before the demo.

| Hours | What You're Doing |
|---|---|
| 0-6 | Demo game: 5 states, distinct visuals, basic mechanics |
| 6-10 | Chunked screen recorder + webcam recorder |
| 10-14 | Tester session page: game + recording + upload flow |
| 14-18 | Apple Watch BLE integration |
| 18-24 | Polish game: tune difficulty for emotional variance, maximize visual distinctness |
| 24-30 | Pre-record 3-5 real sessions |
| 30-36 | Bug fixes and demo prep |

### Person 2 — Backend Engineer + Data Pipeline

**Primary deliverable:** The server, fusion engine, verdict system, and data stores.

Build the FastAPI backend with all endpoints. Build the chunk processing pipeline that receives 15-second gameplay chunks and sends them to Gemini immediately. Build the temporal fusion engine that aligns three data streams onto a 1-second timeline. Build the verdict computation and Playtest Health Score. Wire up Snowflake and VectorAI.

| Hours | What You're Doing |
|---|---|
| 0-4 | FastAPI skeleton with all endpoints including chunk upload |
| 4-8 | Presage integration (try live, batch fallback) |
| 8-12 | Chunk processing pipeline: receive → Gemini → store → stitch |
| 12-16 | Temporal fusion engine + verdict computation + health score |
| 16-20 | Snowflake: Bronze/Silver/Gold tables |
| 20-24 | VectorAI: embedding generation + similarity search |
| 24-28 | Cross-tester aggregation, process pre-recorded sessions |
| 28-36 | End-to-end testing, reliability |

### Person 3 — AI Intelligence Specialist

**Primary deliverable:** Gemini prompt engineering, insight generation, and Sphinx.

Engineer the Gemini prompts for chunk analysis — this is the most important prompt engineering work in the project. The quality of state detection and behavioral analysis depends entirely on how well these prompts work. Test against the demo game at 2 FPS. Build the optimal playthrough analysis. Build the natural language insight generator. Set up Sphinx and validate the three killer demo queries with real data.

| Hours | What You're Doing |
|---|---|
| 0-6 | Gemini chunk analysis: prompt engineering, test at 2 FPS, verify accuracy |
| 6-12 | Gemini insights: per-session and cross-tester text generation |
| 12-18 | Sphinx setup: connect to Snowflake, test the three demo queries |
| 18-24 | Sphinx polish: get charts rendering, save exact query text |
| 24-28 | ElevenLabs audio reports (if time) |
| 28-36 | Demo preparation, judge Q&A answers, video pitch |

### Person 4 — Frontend Dashboard Developer

**Primary deliverable:** The React dashboard that developers use.

Build all five pages of the developer portal. The DFA State Editor is the highest priority — it needs to be polished because it's the first thing judges see in the demo. The Session Review page with the emotion timeline overlaid on DFA states is the second priority — this is where verdicts are displayed. The cross-tester aggregate view and Sphinx explorer come after.

| Hours | What You're Doing |
|---|---|
| 0-6 | React scaffold, router, 5 page skeletons |
| 6-12 | Project Setup: DFA State Editor, intent form, upload, session creation |
| 12-18 | Session Review: emotion timeline, DFA state overlay, verdict cards, health score |
| 18-24 | Cross-Tester Aggregate: overlaid curves, pain points, verdict summary |
| 24-28 | Sphinx Explorer: query input, chart rendering |
| 28-32 | UI polish |
| 32-36 | Record 2-minute video pitch, demo rehearsal |

---

## The 2-Minute Demo Script

**0:00-0:10 — The Problem**
"Game studios spend millions on playtesting. They see what players do — but never how they feel. Post-session surveys are biased. Manual video review doesn't scale."

**0:10-0:35 — Our Solution**
"PlayPulse instruments the human, not the game. Zero code integration required."
Show the developer portal: DFA states defined with detailed descriptions, intents set per state.
"The developer models their game as a state machine and annotates each segment with what emotion they want the player to feel."
Show a tester playing the demo game.
"Presage captures facial emotion. Apple Watch captures heart rate. Gemini Vision analyzes 15-second gameplay chunks during gameplay itself. By the time the game ends, the analysis is already done."

**0:35-1:05 — The Killer Feature**
"PlayPulse fuses all three data streams and produces a verdict per game state."
Show the session review page: emotion timeline with DFA overlay, verdict cards.
"The puzzle room was supposed to feel curious. It felt frustrated. FAIL. The surprise event was supposed to feel exciting. It did. PASS."
Show the Playtest Health Score: 0.72.

**1:05-1:30 — Cross-Tester Intelligence**
"Run ten playtests. PlayPulse aggregates automatically."
Show the cross-tester overlay, pain points ranked.
"Seven out of ten testers got frustrated at the same puzzle. Snowflake stores the structured telemetry. VectorAI finds the exact worst moments across all sessions."
Flash a Sphinx query → show the heatmap result.
"Developers query their data in plain English through Sphinx."

**1:30-1:50 — The Measurable Delta**
"Fix the puzzle. Run another round. Playtest Health Score improves from 0.72 to 0.89. PlayPulse gives you a measurable signal that your design fix actually worked."

**1:50-2:00 — Close**
"No SDK. No code changes. Works with any game. The industry has been guessing how players feel. PlayPulse measures it."

---

## What to Do Before Coding Starts

- [ ] Vultr: sign up, claim free cloud credits
- [ ] Presage SDK: get API key, test with a sample video, confirm output format
- [ ] Gemini API: get key, test vision endpoint with a gameplay screenshot, verify JSON output mode works
- [ ] Snowflake: sign up for 120-day student trial
- [ ] Actian VectorAI: pull Docker image, run locally, test insert + query
- [ ] Sphinx: get access, test with sample tabular data
- [ ] ElevenLabs: get API key (if using)
- [ ] Apple Watch: confirm BLE streaming works (reuse from previous project)
- [ ] Create project repo with folder structure
- [ ] Sketch dashboard wireframes on paper
- [ ] Finalize demo game state designs — lock in 5 distinct visual themes
- [ ] Create .env.example with all required API keys documented

---

## Risk Mitigation

**Presage doesn't work live?** We have batch mode as fallback. Record the face video, send it to Presage after the session. The rest of the pipeline doesn't change.

**Gemini misidentifies game states?** Our demo game has maximally distinct visual states (different colors, different layouts, different UI elements). Rich state definitions with visual cues and failure indicators guide Gemini. We validate against the game's own state tracking and report accuracy to judges.

**Processing takes too long?** Most chunks process during gameplay, not after. By the time the game ends, only the final chunk is pending. Worst case: ~5-10 seconds of wait time.

**Multi-tester live demo fails?** We pre-record 3-5 real sessions before the event. Live demo: one judge plays for real. Cross-tester analytics come from pre-recorded sessions with genuine data.

**Running out of time?** Cut in this order: (1) ElevenLabs, (2) Sphinx explorer, (3) VectorAI search, (4) cross-tester aggregate. Core MVP: demo game + Gemini DFA chunks + Presage emotions + temporal fusion + verdicts + single-session dashboard. This alone is a complete, demo-able product.

---

## Why This Wins

**Creativity** — The DFA formalism for game state modeling, Gemini as a formal automaton transition function, intent annotation before testing, and the verdict system are all genuinely novel. No existing tool compares actual emotions against intended design.

**Technical Depth** — Full multimodal pipeline: facial affect + HR/HRV + AI vision, temporal fusion across three different sample rates, chunked progressive processing, vector embeddings for cross-session search, data warehouse with medallion architecture, natural language query agent.

**Impact** — Direct commercial value for every game studio. Transforms subjective playtesting into measurable, data-driven design. The Playtest Health Score is a metric the industry doesn't have.

**Demo Quality** — A judge sits down and plays a game. Their emotions are captured. They see a verdict: this segment worked, this one didn't. That's visceral, interactive, and unforgettable.

**Soundness** — Presage provides clinically-validated facial affect metrics. HR/HRV are established psychophysiology markers. Gemini's state detection is validated against known game state. The fusion engine handles different sample rates with explicit temporal alignment. We acknowledge limitations (facial expression isn't perfect, Gemini can miss fast events) instead of handwaving them.

**Judge-killer sentence:** *"The game industry has been guessing how players feel. PlayPulse measures it."*

---

*Hacklytics 2026 | Georgia Tech | Entertainment Track | 36 Hours*