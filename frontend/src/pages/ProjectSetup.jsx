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

const STATE_BORDER_COLORS = ['#ef4444','#22c55e','#3b82f6','#f59e0b','#ec4899','#6366f1'];

const EMPTY_STATE = {
  name: '', description: '', intended_emotion: 'curious',
  acceptable_range: [0.3, 0.7], expected_duration_sec: 30,
  visual_cues: '', failure_indicators: '', success_indicators: '',
};

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
    <div
      className="min-h-screen text-white"
      style={{
        backgroundImage: "url('/background3.jpg')",
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundAttachment: 'fixed',
      }}
    >
      {/* Overlay */}
      <div className="fixed inset-0 bg-gradient-to-t from-black/60 to-black/95 pointer-events-none" />

      {/* Green ambient glows */}
      <div className="fixed -top-40 -left-40 w-[600px] h-[600px] bg-[#22c55e]/8 blur-[160px] rounded-full pointer-events-none" />
      <div className="fixed -bottom-40 -right-40 w-[500px] h-[500px] bg-[#22c55e]/6 blur-[140px] rounded-full pointer-events-none" />

      {/* Floating header */}
      <div className="relative z-10 max-w-5xl mx-auto px-6 pt-6 pb-2">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-[#22c55e] animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.9)]" />
            <span className="text-xs text-white/70 tracking-widest uppercase font-mono">Project Setup</span>
            <span className="text-white/70 font-mono text-xs select-none">·</span>
            <span className="text-xs text-white/70 font-mono">Configure DFA states & emotional targets</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setStates(MARIO_PRESET); setName('Super Mario Bros 1-1'); setDesc('NES Mario World 1-1 — first level playtest'); }}
              className="px-3 py-1.5 rounded-full text-[10px] font-bold tracking-widest uppercase transition-all hover:scale-[1.03]"
              style={{ background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.25)', color: 'rgba(251,191,36,0.90)' }}
            >
              🍄 Mario Preset
            </button>
            <button
              onClick={addState}
              className="px-3 py-1.5 rounded-full text-[10px] font-bold tracking-widest uppercase transition-all hover:scale-[1.03]"
              style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)', color: 'rgba(255,255,255,0.55)' }}
            >
              + Add State
            </button>
          </div>
        </div>
        <div className="h-px w-full" style={{ background: 'linear-gradient(90deg, rgba(34,197,94,0.30) 0%, rgba(255,255,255,0.05) 60%, transparent 100%)' }} />
      </div>

      <main className="relative z-10 px-6 py-6 max-w-5xl mx-auto space-y-5">

        {/* Game Info */}
        <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
          <h2 className="font-eb-garamond text-2xl font-bold text-white mb-4">Game Info</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-widest font-mono block mb-1.5">Game Name</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="Enter your game title…"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-[#22c55e]/40 transition-colors"
              />
            </div>
            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-widest font-mono block mb-1.5">Description</label>
              <input
                value={desc}
                onChange={e => setDesc(e.target.value)}
                placeholder="What kind of game is this?"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-[#22c55e]/40 transition-colors"
              />
            </div>
          </div>
        </div>

        {/* DFA States */}
        <div className="space-y-3">
          <div className="flex items-baseline gap-3">
            <h2 className="font-eb-garamond text-2xl font-bold text-white">DFA State Editor</h2>
            <span className="text-[11px] text-white/75 font-mono">{states.length} states defined</span>
          </div>

          {states.map((s, i) => (
            <div
              key={i}
              className="rounded-3xl p-5 backdrop-blur-xl shadow-[0_4px_24px_rgba(0,0,0,0.35)] border"
              style={{ background: 'rgba(255,255,255,0.05)', borderColor: STATE_BORDER_COLORS[i % STATE_BORDER_COLORS.length] + '28' }}
            >
              {/* State header row */}
              <div className="flex items-center gap-3 mb-4">
                <div
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-black font-mono text-white shrink-0"
                  style={{ background: STATE_COLORS[i % STATE_COLORS.length] }}
                >
                  {i + 1}
                </div>
                <span className="text-sm font-semibold text-white flex-1">
                  {s.name || `State ${i + 1}`} <span className="ml-1 opacity-70">{EMOTION_ICONS[s.intended_emotion] || '🎮'}</span>
                </span>
                <span className="text-[10px] font-mono text-white/70 px-2 py-1 rounded-lg" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)' }}>{s.expected_duration_sec}s</span>
                <button
                  onClick={() => removeState(i)}
                  className="text-white/20 hover:text-red-400 transition-colors text-xs font-mono px-2 py-1 rounded-lg hover:bg-red-400/10"
                >✕</button>
              </div>

              <div className="grid grid-cols-3 gap-3 mb-3">
                {[
                  { label: 'State Name', field: 'name', placeholder: 'e.g. tutorial', type: 'text', value: s.name },
                  { label: 'Intended Emotion', field: 'intended_emotion', type: 'select', value: s.intended_emotion },
                  { label: 'Duration (sec)', field: 'expected_duration_sec', placeholder: '30', type: 'number', value: s.expected_duration_sec },
                ].map(({ label, field, placeholder, type, value }) => (
                  <div key={field}>
                    <label className="text-[10px] text-white/25 uppercase tracking-widest font-mono block mb-1">{label}</label>
                    {type === 'select' ? (
                      <select
                        value={value}
                        onChange={e => updateState(i, field, e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-[#22c55e]/40 transition-colors"
                        style={{ colorScheme: 'dark' }}
                      >
                        {EMOTIONS.map(em => <option key={em} value={em} style={{ background: '#0d1117' }}>{EMOTION_ICONS[em]} {em}</option>)}
                      </select>
                    ) : (
                      <input
                        type={type}
                        value={value}
                        onChange={e => updateState(i, field, type === 'number' ? +e.target.value : e.target.value)}
                        placeholder={placeholder}
                        className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-white/15 outline-none focus:border-[#22c55e]/40 transition-colors"
                      />
                    )}
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-3 mb-3">
                {[
                  { label: 'Range Min', value: s.acceptable_range[0], onChange: v => updateState(i, 'acceptable_range', [+v, s.acceptable_range[1]]) },
                  { label: 'Range Max', value: s.acceptable_range[1], onChange: v => updateState(i, 'acceptable_range', [s.acceptable_range[0], +v]) },
                ].map(({ label, value, onChange }) => (
                  <div key={label}>
                    <label className="text-[10px] text-white/25 uppercase tracking-widest font-mono block mb-1">{label}</label>
                    <input
                      type="number" step="0.1" min="0" max="1" value={value}
                      onChange={e => onChange(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-[#22c55e]/40 transition-colors"
                    />
                  </div>
                ))}
              </div>

              <div className="mb-3">
                <label className="text-[10px] text-white/25 uppercase tracking-widest font-mono block mb-1">Description</label>
                <input
                  value={s.description}
                  onChange={e => updateState(i, 'description', e.target.value)}
                  placeholder="What happens in this state?"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-white/15 outline-none focus:border-[#22c55e]/40 transition-colors"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'Visual Cues (comma-sep)', field: 'visual_cues', value: s.visual_cues, placeholder: 'Blue bg, open space' },
                  { label: 'Failure Indicators', field: 'failure_indicators', value: s.failure_indicators, placeholder: 'Player stuck, backtracking' },
                  { label: 'Success Indicators', field: 'success_indicators', value: s.success_indicators, placeholder: 'Moves forward confidently' },
                ].map(({ label, field, value, placeholder }) => (
                  <div key={field}>
                    <label className="text-[10px] text-white/25 uppercase tracking-widest font-mono block mb-1">{label}</label>
                    <input
                      value={value}
                      onChange={e => updateState(i, field, e.target.value)}
                      placeholder={placeholder}
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-white/15 outline-none focus:border-[#22c55e]/40 transition-colors"
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Launch */}
        <div
          className="rounded-3xl p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(34,197,94,0.08)] border border-[#22c55e]/20"
          style={{ background: 'rgba(34,197,94,0.07)' }}
        >
          <h2 className="font-eb-garamond text-2xl font-bold text-white mb-4">Launch Project</h2>
          <button
            onClick={submit}
            disabled={loading}
            className="px-8 py-3 rounded-2xl text-sm font-bold tracking-wide transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50"
            style={{
              background: 'rgba(34,197,94,0.20)',
              border: '1px solid rgba(34,197,94,0.40)',
              color: '#86efac',
              boxShadow: loading ? 'none' : '0 0 24px rgba(34,197,94,0.18)',
            }}
          >
            {loading ? '⏳ Creating…' : '🚀 Create Project'}
          </button>

          {result && (
            <div
              className="mt-4 p-4 rounded-2xl text-sm"
              style={{
                background: result.error ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)',
                border: `1px solid ${result.error ? 'rgba(239,68,68,0.20)' : 'rgba(34,197,94,0.20)'}`,
              }}
            >
              {result.error ? (
                <p className="text-red-400">❌ {result.error}</p>
              ) : (
                <>
                  <p className="text-green-400 font-bold mb-2">✅ Project Created!</p>
                  <p className="text-white/50 font-mono text-xs">Project ID: <span className="text-white/80">{result.project_id}</span></p>
                  <p className="text-white/50 font-mono text-xs mt-1">API Key: <span className="text-white/80">{result.api_key}</span></p>
                </>
              )}
            </div>
          )}
        </div>

      </main>
    </div>
  );
}
