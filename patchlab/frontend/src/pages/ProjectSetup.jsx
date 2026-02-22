import { useState, useRef } from 'react';

const API = 'http://localhost:8000';

const EMOTIONS = ['frustrated','confused','delighted','bored','surprised','tense','calm','excited','curious'];

const EMOTION_ICONS = {
  frustrated: '😤', confused: '🤔', delighted: '😄', bored: '😴',
  surprised: '😲', tense: '😰', calm: '😌', excited: '🤩', curious: '🧐',
};

const STATE_COLORS = [
  'linear-gradient(135deg, #ef4444, #f97316)',
  'linear-gradient(135deg, #22c55e, #14b8a6)',
  'linear-gradient(135deg, #3b82f6, #38bdf8)',
  'linear-gradient(135deg, #f59e0b, #eab308)',
  'linear-gradient(135deg, #ec4899, #d946ef)',
  'linear-gradient(135deg, #6366f1, #8b5cf6)',
];

const EMPTY_STATE = {
  name: '', description: '', intended_emotion: 'curious',
  acceptable_range: [0.3, 0.7], expected_duration_sec: 30,
  visual_cues: '', failure_indicators: '', success_indicators: '',
};

// ── Mario 1-1 DFA preset (primary demo) ────────────────────
const MARIO_PRESET = [
  { ...EMPTY_STATE, name: 'overworld_start', intended_emotion: 'excited', description: 'Opening run — flat ground, first Goomba, ? blocks. Fast-paced introduction.', visual_cues: 'Green grass, blue sky, Goomba, ? blocks, brick blocks', failure_indicators: 'Repeated deaths to first Goomba, frozen in place for >3s', success_indicators: 'Stomps Goomba, hits ? block, keeps momentum', expected_duration_sec: 8 },
  { ...EMPTY_STATE, name: 'block_discovery', intended_emotion: 'curious', description: 'Player discovers ? blocks give power-ups, coins from bricks', visual_cues: '? blocks pulsing, mushroom emerging, coin particles', failure_indicators: 'Runs past all ? blocks without hitting any', success_indicators: 'Hits ? blocks, grabs mushroom, grows big', expected_duration_sec: 5 },
  { ...EMPTY_STATE, name: 'platforming', intended_emotion: 'tense', description: 'Pipes, pits, and enemies — core platforming challenge. Deaths send player back to start; single deaths are normal, excessive deaths signal a problem.', visual_cues: 'Green pipes, gaps in ground, Koopas, piranha plants, elevated platforms', failure_indicators: 'Dies 3+ times in same section, stuck for >10s, backtracks repeatedly', success_indicators: 'Navigates pipes and pits with momentum, clears gaps confidently', expected_duration_sec: 15 },
  { ...EMPTY_STATE, name: 'mid_gauntlet', intended_emotion: 'excited', description: 'Dense enemy section — Goombas, Koopas, elevated platforms. Deaths respawn to start; only repeated death loops are concerning.', visual_cues: 'Multiple enemies, stacked platforms, coins above, moving Koopa shells', failure_indicators: 'Dies 3+ times consecutively, gives up or stops moving', success_indicators: 'Chain stomps enemies, maintains flow, collects coins', expected_duration_sec: 12 },
  { ...EMPTY_STATE, name: 'flagpole', intended_emotion: 'delighted', description: 'Staircase approach and flagpole grab — victory moment', visual_cues: 'Ascending stair blocks, flagpole, castle in background, fireworks', failure_indicators: 'Falls off stairs repeatedly, very low flag grab', success_indicators: 'Reaches top of flagpole, smooth staircase ascent', expected_duration_sec: 6 },
];

export default function ProjectSetup() {
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [states, setStates] = useState([
    { ...EMPTY_STATE, name: 'tutorial', intended_emotion: 'calm', description: 'Opening level, easy navigation', visual_cues: 'Blue background, open space', expected_duration_sec: 30 },
    { ...EMPTY_STATE, name: 'puzzle_room', intended_emotion: 'curious', description: 'Hidden path puzzle', visual_cues: 'Green/dark, walls', expected_duration_sec: 45 },
    { ...EMPTY_STATE, name: 'surprise_event', intended_emotion: 'surprised', description: 'Sudden enemy appearance', visual_cues: 'Red flash, enemies', expected_duration_sec: 10 },
    { ...EMPTY_STATE, name: 'gauntlet', intended_emotion: 'tense', description: 'Moving obstacle dodge', visual_cues: 'Dark, moving spikes', expected_duration_sec: 50 },
    { ...EMPTY_STATE, name: 'victory', intended_emotion: 'delighted', description: 'Win screen', visual_cues: 'Bright, particles', expected_duration_sec: 15 },
  ]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [optimalFile, setOptimalFile] = useState(null);
  const [optimalStatus, setOptimalStatus] = useState(null);
  const [optimalUploading, setOptimalUploading] = useState(false);
  const [transitions, setTransitions] = useState([]);
  const fileInputRef = useRef(null);

  const updateState = (i, field, val) => {
    const next = [...states];
    next[i] = { ...next[i], [field]: val };
    setStates(next);
  };
  const addState = () => setStates([...states, { ...EMPTY_STATE }]);
  const removeState = (i) => setStates(states.filter((_, j) => j !== i));

  // Transition helpers
  const addTransition = () => setTransitions([...transitions, { from_state: '', to_state: '', trigger: '' }]);
  const updateTransition = (i, field, val) => {
    const next = [...transitions];
    next[i] = { ...next[i], [field]: val };
    setTransitions(next);
  };
  const removeTransition = (i) => setTransitions(transitions.filter((_, j) => j !== i));
  const autoGenTransitions = () => {
    // Generate linear transitions from state order
    const auto = [];
    for (let i = 0; i < states.length - 1; i++) {
      if (states[i].name && states[i + 1].name) {
        auto.push({ from_state: states[i].name, to_state: states[i + 1].name, trigger: 'progression' });
      }
    }
    setTransitions(auto);
  };

  const submit = async () => {
    setLoading(true);
    try {
      const body = {
        name: name || 'Demo Game',
        description: desc,
        dfa_states: states.map(s => ({
          ...s,
          visual_cues: s.visual_cues.split(',').map(x => x.trim()).filter(Boolean),
          failure_indicators: s.failure_indicators.split(',').map(x => x.trim()).filter(Boolean),
          success_indicators: s.success_indicators.split(',').map(x => x.trim()).filter(Boolean),
        })),
        transitions: transitions.filter(t => t.from_state && t.to_state),
      };
      const resp = await fetch(`${API}/v1/projects`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setResult(await resp.json());
    } catch (e) { setResult({ error: e.message }); }
    setLoading(false);
  };

  return (
    <div>
      <h1 className="page-title">🎮 Project Setup</h1>
      <p className="page-subtitle"><span className="dot" /> Configure your game's DFA states and emotional targets</p>

      <div className="card">
        <h2><span className="card-icon">🎯</span><span className="card-label">Game Info</span></h2>
        <div className="grid-2">
          <div>
            <label>Game Name</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Enter your game title…" />
          </div>
          <div>
            <label>Description</label>
            <input value={desc} onChange={e => setDesc(e.target.value)} placeholder="What kind of game is this?" />
          </div>
        </div>
      </div>

      <div className="card">
        <h2><span className="card-icon">🧩</span><span className="card-label">DFA State Editor</span></h2>
        <p className="text-muted mb">
          Define each game state with its intended emotion and visual cues for Gemini detection.
          States represent distinct phases in your game flow.
        </p>

        {states.map((s, i) => (
          <div key={i} className="state-card">
            <div className="state-header">
              <div className="state-number" style={{ background: STATE_COLORS[i % STATE_COLORS.length] }}>{i + 1}</div>
              <strong style={{ flex: 1, fontSize: 15 }}>
                {s.name || `State ${i + 1}`}
                <span style={{ marginLeft: 8 }}>{EMOTION_ICONS[s.intended_emotion] || '🎮'}</span>
              </strong>
              <span className="stat-pill">{s.expected_duration_sec}s</span>
              <button className="btn-sm btn-danger" onClick={() => removeState(i)}>✕</button>
            </div>
            <div className="grid-3">
              <div>
                <label>State Name</label>
                <input value={s.name} onChange={e => updateState(i, 'name', e.target.value)} placeholder="e.g. tutorial" />
              </div>
              <div>
                <label>Intended Emotion</label>
                <select value={s.intended_emotion} onChange={e => updateState(i, 'intended_emotion', e.target.value)}>
                  {EMOTIONS.map(em => <option key={em} value={em}>{EMOTION_ICONS[em]} {em}</option>)}
                </select>
              </div>
              <div>
                <label>Expected Duration (sec)</label>
                <input type="number" value={s.expected_duration_sec} onChange={e => updateState(i, 'expected_duration_sec', +e.target.value)} />
              </div>
            </div>
            <div className="grid-2">
              <div>
                <label>Acceptable Range (min)</label>
                <input type="number" step="0.1" min="0" max="1" value={s.acceptable_range[0]}
                  onChange={e => updateState(i, 'acceptable_range', [+e.target.value, s.acceptable_range[1]])} />
              </div>
              <div>
                <label>Acceptable Range (max)</label>
                <input type="number" step="0.1" min="0" max="1" value={s.acceptable_range[1]}
                  onChange={e => updateState(i, 'acceptable_range', [s.acceptable_range[0], +e.target.value])} />
              </div>
            </div>
            <label>Description</label>
            <input value={s.description} onChange={e => updateState(i, 'description', e.target.value)} placeholder="What happens in this state?" />
            <div className="grid-3">
              <div>
                <label>Visual Cues (comma-sep)</label>
                <input value={s.visual_cues} onChange={e => updateState(i, 'visual_cues', e.target.value)} placeholder="Blue bg, open space" />
              </div>
              <div>
                <label>Failure Indicators</label>
                <input value={s.failure_indicators} onChange={e => updateState(i, 'failure_indicators', e.target.value)} placeholder="Player stuck, backtracking" />
              </div>
              <div>
                <label>Success Indicators</label>
                <input value={s.success_indicators} onChange={e => updateState(i, 'success_indicators', e.target.value)} placeholder="Moves forward confidently" />
              </div>
            </div>
          </div>
        ))}

        <button className="btn-ghost" onClick={addState} style={{ marginRight: 8 }}>+ Add State</button>
        <button className="btn-ghost" onClick={() => { setStates(MARIO_PRESET); setName('Super Mario Bros 1-1'); setDesc('NES Mario World 1-1 — first level playtest'); }} style={{ background: 'linear-gradient(135deg, #ef4444, #f59e0b)', color: '#fff', border: 'none' }}>
          🍄 Load Mario 1-1 Preset
        </button>
      </div>

      {/* ── DFA Transitions ──────────────────────────────── */}
      <div className="card">
        <h2><span className="card-icon">🔗</span><span className="card-label">DFA Transitions</span></h2>
        <p className="text-muted mb">
          Define valid transitions between states. These help Gemini understand game flow.
        </p>
        {transitions.map((t, i) => (
          <div key={i} className="row" style={{ gap: 8, marginBottom: 8, alignItems: 'center' }}>
            <select value={t.from_state} onChange={e => updateTransition(i, 'from_state', e.target.value)} style={{ width: 160 }}>
              <option value="">From…</option>
              {states.filter(s => s.name).map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
            </select>
            <span style={{ fontSize: 18, opacity: 0.5 }}>→</span>
            <select value={t.to_state} onChange={e => updateTransition(i, 'to_state', e.target.value)} style={{ width: 160 }}>
              <option value="">To…</option>
              {states.filter(s => s.name).map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
            </select>
            <input value={t.trigger} onChange={e => updateTransition(i, 'trigger', e.target.value)} placeholder="Trigger (e.g. progression)" style={{ width: 180 }} />
            <button className="btn-sm btn-danger" onClick={() => removeTransition(i)}>✕</button>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-ghost" onClick={addTransition}>+ Add Transition</button>
          <button className="btn-ghost" onClick={autoGenTransitions} style={{ background: 'rgba(99,102,241,.15)', borderColor: 'rgba(99,102,241,.3)' }}>
            ⚡ Auto-Generate Linear
          </button>
        </div>
      </div>

      {/* ── Launch ───────────────────────────────────────── */}
      <div className="card card-glow">
        <h2><span className="card-icon">🚀</span><span className="card-label">Launch</span></h2>
        <button onClick={submit} disabled={loading} style={{ fontSize: 16, padding: '12px 32px' }}>
          {loading ? '⏳ Creating…' : '🚀 Create Project'}
        </button>
        {result && (
          <div style={{ marginTop: 16, padding: 16, borderRadius: 12, background: result.error ? 'rgba(239,68,68,.08)' : 'rgba(16,185,129,.08)', border: `1px solid ${result.error ? 'rgba(239,68,68,.2)' : 'rgba(16,185,129,.2)'}` }}>
            {result.error ? (
              <p style={{ color: 'var(--neon-red)' }}>❌ {result.error}</p>
            ) : (
              <>
                <p style={{ color: 'var(--neon-green)', fontWeight: 700, marginBottom: 8 }}>✅ Project Created!</p>
                <p className="text-sm">Project ID: <code>{result.project_id}</code></p>
                <p className="text-sm">API Key: <code>{result.api_key}</code></p>
              </>
            )}
          </div>
        )}
      </div>

      {/* ── Optimal Playthrough Upload ───────────────────── */}
      {result && result.project_id && (
        <div className="card" style={{ borderLeft: '3px solid var(--blue)' }}>
          <h2><span className="card-icon">🎬</span><span className="card-label">Optimal Playthrough Video</span></h2>
          <p className="text-muted mb">
            Upload a video of the intended/developer playthrough. PatchLab uses this as a reference 
            to compare tester sessions against the "golden path". Gemini will analyze it to extract 
            expected timing and emotional signatures per DFA state.
          </p>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              onChange={e => setOptimalFile(e.target.files[0] || null)}
              style={{ display: 'none' }}
            />
            <button
              className="btn-ghost"
              onClick={() => fileInputRef.current?.click()}
              style={{ background: 'rgba(59,130,246,.1)', border: '1px dashed rgba(59,130,246,.4)', padding: '12px 24px' }}
            >
              🎬 {optimalFile ? optimalFile.name : 'Choose Video File…'}
            </button>
            {optimalFile && (
              <span className="stat-pill" style={{ fontSize: 12 }}>
                {(optimalFile.size / 1048576).toFixed(1)} MB
              </span>
            )}
            <button
              disabled={!optimalFile || optimalUploading}
              onClick={async () => {
                setOptimalUploading(true);
                setOptimalStatus(null);
                try {
                  const fd = new FormData();
                  fd.append('file', optimalFile);
                  const resp = await fetch(`${API}/v1/projects/${result.project_id}/optimal-playthrough`, {
                    method: 'POST',
                    body: fd,
                  });
                  const data = await resp.json();
                  setOptimalStatus({ ok: true, data });
                } catch (e) {
                  setOptimalStatus({ ok: false, error: e.message });
                }
                setOptimalUploading(false);
              }}
              style={{ fontSize: 14, padding: '10px 24px' }}
            >
              {optimalUploading ? '⏳ Analyzing…' : '📤 Upload & Analyze'}
            </button>
          </div>
          {optimalStatus && (
            <div style={{ marginTop: 12, padding: 12, borderRadius: 8, background: optimalStatus.ok ? 'rgba(16,185,129,.08)' : 'rgba(239,68,68,.08)', border: `1px solid ${optimalStatus.ok ? 'rgba(16,185,129,.2)' : 'rgba(239,68,68,.2)'}` }}>
              {optimalStatus.ok ? (
                <>
                  <p style={{ color: 'var(--neon-green)', fontWeight: 700 }}>✅ Optimal playthrough processed!</p>
                  <p className="text-sm text-muted">Gemini extracted reference emotional signatures for each DFA state.</p>
                  {optimalStatus.data?.reference && (
                    <details style={{ marginTop: 8 }}>
                      <summary style={{ cursor: 'pointer', fontSize: 13, opacity: 0.7 }}>View extracted reference data</summary>
                      <pre style={{ fontSize: 11, marginTop: 8, padding: 8, background: 'rgba(0,0,0,.1)', borderRadius: 6, overflow: 'auto', maxHeight: 200 }}>
                        {JSON.stringify(optimalStatus.data.reference, null, 2)}
                      </pre>
                    </details>
                  )}
                </>
              ) : (
                <p style={{ color: 'var(--neon-red)' }}>❌ {optimalStatus.error}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
