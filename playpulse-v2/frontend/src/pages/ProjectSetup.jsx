import { useState } from 'react';

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
  { ...EMPTY_STATE, name: 'first_goomba', intended_emotion: 'surprised', description: 'First enemy encounter — Goomba walking toward player', visual_cues: 'Ground level, single Goomba approaching, brick blocks above', failure_indicators: 'Player takes hit, shrinks, freeze/panic', success_indicators: 'Stomps Goomba, keeps momentum', expected_duration_sec: 8 },
  { ...EMPTY_STATE, name: 'block_discovery', intended_emotion: 'curious', description: 'Discovering ? blocks, power-ups, coin blocks', visual_cues: '? blocks pulsing, player jumps into blocks from below', failure_indicators: 'Player skips blocks, runs past', success_indicators: 'Hits ? blocks, collects mushroom, grows big', expected_duration_sec: 15 },
  { ...EMPTY_STATE, name: 'first_pipes', intended_emotion: 'curious', description: 'Green pipes section — some have piranha plants', visual_cues: 'Green pipes of varying height, piranha plants emerging', failure_indicators: 'Hit by piranha plant, falls into gap between pipes', success_indicators: 'Navigates pipes cleanly, discovers warp pipe', expected_duration_sec: 12 },
  { ...EMPTY_STATE, name: 'first_pit', intended_emotion: 'tense', description: 'First bottomless pit jump — high-stakes platforming', visual_cues: 'Gap in ground, sky visible below, running approach', failure_indicators: 'Falls into pit (death), hesitates at edge', success_indicators: 'Clears pit with confident jump', expected_duration_sec: 5 },
  { ...EMPTY_STATE, name: 'mid_level', intended_emotion: 'excited', description: 'Mid-level gauntlet with stacked enemies and moving platforms', visual_cues: 'Multiple Goombas and Koopas, elevated platforms, coins', failure_indicators: 'Takes multiple hits, backtracks, dies', success_indicators: 'Chain stomps enemies, keeps star power if obtained', expected_duration_sec: 20 },
  { ...EMPTY_STATE, name: 'endgame_stairs', intended_emotion: 'delighted', description: 'Staircase to flagpole — victory sequence', visual_cues: 'Ascending stair blocks, flagpole visible, castle in background', failure_indicators: 'Falls off stairs, lands low on flag', success_indicators: 'Reaches top of flagpole, fireworks', expected_duration_sec: 10 },
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

  const updateState = (i, field, val) => {
    const next = [...states];
    next[i] = { ...next[i], [field]: val };
    setStates(next);
  };
  const addState = () => setStates([...states, { ...EMPTY_STATE }]);
  const removeState = (i) => setStates(states.filter((_, j) => j !== i));

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
    </div>
  );
}
