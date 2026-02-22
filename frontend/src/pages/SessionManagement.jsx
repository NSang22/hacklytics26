import { useState, useEffect } from 'react';

const API = 'http://localhost:8000';

export default function SessionManagement() {
  const [projectId, setProjectId]       = useState('');
  const [sessions, setSessions]         = useState([]);
  const [testerName, setTesterName]     = useState('');
  const [chunkDuration, setChunkDuration] = useState(15);
  const [createResult, setCreateResult] = useState(null);

  const load = async () => {
    if (!projectId) return;
    try {
      const resp = await fetch(`${API}/v1/projects/${projectId}/aggregate`);
      const data = await resp.json();
      setSessions(data.sessions || []);
    } catch { setSessions([]); }
  };

  useEffect(() => { if (projectId) load(); }, [projectId]); // eslint-disable-line

  const create = async () => {
    try {
      const resp = await fetch(`${API}/v1/projects/${projectId}/sessions`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tester_name: testerName || 'tester', chunk_duration_sec: chunkDuration }),
      });
      const data = await resp.json();
      setCreateResult(data);
      load();
    } catch (e) { setCreateResult({ error: e.message }); }
  };

  const health = (score) => {
    if (score == null) return { label: '—', color: 'rgba(255,255,255,0.20)' };
    return score >= 0.7
      ? { label: score.toFixed(2), color: '#22c55e' }
      : score >= 0.5
      ? { label: score.toFixed(2), color: '#f59e0b' }
      : { label: score.toFixed(2), color: '#ef4444' };
  };

  return (
    <div
      className="min-h-screen text-white"
      style={{
        backgroundImage: "url('/background4.jpg')",
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundAttachment: 'fixed',
      }}
    >
      {/* Overlay */}
      <div className="fixed inset-0 bg-gradient-to-t from-black/60 to-black/90 pointer-events-none" />

      {/* Blue ambient glows */}
      <div className="fixed -top-40 -left-40 w-[600px] h-[600px] bg-[#3b82f6]/8 blur-[160px] rounded-full pointer-events-none" />
      <div className="fixed -bottom-40 -right-40 w-[500px] h-[500px] bg-[#3b82f6]/6 blur-[140px] rounded-full pointer-events-none" />

      {/* Floating header */}
      <div className="relative z-10 max-w-5xl mx-auto px-6 pt-6 pb-2">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-[#3b82f6] animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.9)]" />
            <span className="text-xs text-white/70 tracking-widest uppercase font-mono">Session Management</span>
            <span className="text-white/70 font-mono text-xs select-none">·</span>
            <span className="text-xs text-white/70 font-mono">Create and monitor playtest sessions</span>
          </div>
          <button
            onClick={create}
            disabled={!projectId}
            className="px-4 py-1.5 rounded-full text-[10px] font-bold tracking-widest uppercase transition-all hover:scale-[1.03] disabled:opacity-30 disabled:cursor-not-allowed"
            style={{ background: 'rgba(59,130,246,0.14)', border: '1px solid rgba(59,130,246,0.30)', color: 'rgba(147,197,253,0.90)' }}
          >
            🎮 Start Session
          </button>
        </div>
        <div className="h-px w-full" style={{ background: 'linear-gradient(90deg, rgba(59,130,246,0.30) 0%, rgba(255,255,255,0.05) 60%, transparent 100%)' }} />
      </div>

      <main className="relative z-10 px-6 py-6 max-w-5xl mx-auto space-y-5">

        {/* Top row: Project + New Session */}
        <div className="grid grid-cols-2 gap-4">

          {/* Select Project */}
          <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
            <h2 className="font-eb-garamond text-xl font-bold text-white mb-4">Select Project</h2>
            <label className="text-[10px] text-white/70 uppercase tracking-widest font-mono block mb-1.5">Project ID</label>
            <div className="flex gap-2">
              <input
                value={projectId}
                onChange={e => setProjectId(e.target.value)}
                placeholder="Paste Project ID…"
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-[#3b82f6]/40 transition-colors"
              />
              <button
                onClick={load}
                className="px-4 py-2.5 rounded-xl text-xs font-bold tracking-wide transition-all hover:scale-[1.03]"
                style={{ background: 'rgba(59,130,246,0.14)', border: '1px solid rgba(59,130,246,0.28)', color: '#93c5fd' }}
              >
                🔍 Load
              </button>
            </div>
          </div>

          {/* New Session */}
          <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
            <h2 className="font-eb-garamond text-xl font-bold text-white mb-4">New Session</h2>
            <label className="text-[10px] text-white/70 uppercase tracking-widest font-mono block mb-1.5">Tester Name</label>
            <input
              value={testerName}
              onChange={e => setTesterName(e.target.value)}
              placeholder="Tester name"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-[#3b82f6]/40 transition-colors mb-3"
            />
            <div className="flex items-center gap-3">
              <label className="text-[10px] text-white/25 uppercase tracking-widest font-mono whitespace-nowrap">⏱ Chunk</label>
              <input
                type="range" min={5} max={30} step={1} value={chunkDuration}
                onChange={e => setChunkDuration(+e.target.value)}
                className="flex-1 accent-blue-500"
              />
              <span
                className="text-xs font-bold font-mono w-10 text-center"
                style={{ background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.22)', color: '#93c5fd', borderRadius: 8, padding: '2px 0' }}
              >{chunkDuration}s</span>
            </div>
            <p className="text-[10px] text-white/20 font-mono mt-2">Default 15s · use 10s for demo</p>
          </div>
        </div>

        {/* Create result */}
        {createResult && (
          <div
            className="rounded-3xl p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.3)] border"
            style={{
              background: createResult.error ? 'rgba(239,68,68,0.07)' : 'rgba(59,130,246,0.07)',
              borderColor: createResult.error ? 'rgba(239,68,68,0.22)' : 'rgba(59,130,246,0.22)',
            }}
          >
            {createResult.session_id ? (
              <>
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-2 h-2 rounded-full bg-[#3b82f6] shadow-[0_0_6px_rgba(59,130,246,0.8)]" />
                  <span className="text-xs font-bold tracking-widest uppercase text-[#93c5fd]">Session Created</span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-[10px] text-white/25 uppercase tracking-widest font-mono block mb-1">Session ID</label>
                    <code className="block bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white/80 font-mono">{createResult.session_id}</code>
                  </div>
                  <div>
                    <label className="text-[10px] text-white/25 uppercase tracking-widest font-mono block mb-1">Tester Game URL</label>
                    <code className="block bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white/60 font-mono break-all">
                      {`http://localhost:8080/game/index.html?session=${createResult.session_id}&project=${projectId}`}
                    </code>
                  </div>
                </div>
              </>
            ) : (
              <p className="text-red-400 text-sm">❌ {createResult.error}</p>
            )}
          </div>
        )}

        {/* Sessions table */}
        <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
          <div className="flex items-baseline gap-3 mb-4">
            <h2 className="font-eb-garamond text-2xl font-bold text-white">Sessions</h2>
            <span className="text-[11px] text-white/70 font-mono">{sessions.length} found</span>
          </div>

          {sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <span className="text-4xl">🎮</span>
              <p className="text-xs text-white/75 font-mono tracking-widest uppercase">No sessions yet — create one above</p>
            </div>
          ) : (
            <div className="space-y-2">
              {/* Header */}
              <div className="grid grid-cols-5 gap-4 px-3 pb-2 border-b border-white/8">
                {['Session ID','Tester','Health','Chunks','Duration'].map(h => (
                  <span key={h} className="text-[10px] text-white/20 uppercase tracking-widest font-mono">{h}</span>
                ))}
              </div>
              {sessions.map(s => {
                const h = health(s.health_score);
                return (
                  <div key={s.session_id} className="grid grid-cols-5 gap-4 items-center px-3 py-2.5 rounded-xl hover:bg-white/[0.03] transition-colors">
                    <code className="text-xs text-white/50 font-mono truncate">{s.session_id}</code>
                    <span className="text-sm text-white/70">🧑‍🎮 {s.tester_name}</span>
                    <span className="text-sm font-bold font-mono" style={{ color: h.color }}>{h.label}</span>
                    <span
                      className="text-xs font-mono px-2 py-1 rounded-lg w-fit"
                      style={{ background: 'rgba(139,92,246,0.14)', border: '1px solid rgba(139,92,246,0.22)', color: '#c4b5fd' }}
                    >{s.chunks_processed ?? '—'}</span>
                    <span
                      className="text-xs font-mono px-2 py-1 rounded-lg w-fit"
                      style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)', color: 'rgba(255,255,255,0.45)' }}
                    >⏱ {s.duration_sec}s</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </main>
    </div>
  );
}


