import { useState, useEffect } from 'react';

const API = 'http://localhost:8000';

export default function SessionManagement() {
  const [projectId, setProjectId] = useState('');
  const [sessions, setSessions] = useState([]);
  const [testerName, setTesterName] = useState('');
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

  const healthBadge = (score) => {
    if (score == null) return <span className="badge badge-nodata">—</span>;
    const cls = score >= 0.7 ? 'badge-pass' : score >= 0.5 ? 'badge-warn' : 'badge-fail';
    return <span className={`badge ${cls}`}>{score.toFixed(2)}</span>;
  };

  return (
    <div className="pp-wrap">
      <div className="content">
        <h1 className="page-title">🕹️ Session Management</h1>
        <p className="page-subtitle"><span className="dot" /> Create and monitor playtest sessions</p>

        <div className="grid-2">
          <div className="card">
            <h2><span className="card-icon">📂</span><span className="card-label">Select Project</span></h2>
            <div className="row">
              <input value={projectId} onChange={e => setProjectId(e.target.value)} placeholder="Paste Project ID…" style={{ maxWidth: 300 }} />
              <button onClick={load}>🔍 Load</button>
            </div>
          </div>

          <div className="card">
            <h2><span className="card-icon">➕</span><span className="card-label">New Session</span></h2>
            <div className="row" style={{ flexWrap: 'wrap', gap: 10 }}>
              <input value={testerName} onChange={e => setTesterName(e.target.value)} placeholder="Tester name" style={{ maxWidth: 200 }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                <label style={{ margin: 0, fontSize: 13, whiteSpace: 'nowrap' }}>⏱ Chunk Duration</label>
                <input type="range" min={5} max={30} step={1} value={chunkDuration} onChange={e => setChunkDuration(+e.target.value)} style={{ width: 100 }} />
                <span className="stat-pill" style={{ width: 42, textAlign: 'center', flexShrink: 0 }}>{chunkDuration}s</span>
              </div>
              <button className="btn-success" onClick={create}>🎮 Start Session</button>
            </div>
            <p className="text-sm text-muted" style={{ marginTop: 6 }}>Default 15s per chunk. Use 10s for demo.</p>
          </div>
        </div>

        {createResult && (
          <div className="card card-glow" style={{ borderColor: createResult.error ? 'rgba(239,68,68,.3)' : 'rgba(16,185,129,.3)' }}>
            {createResult.session_id ? (
              <>
                <h2><span className="card-icon">✅</span><span className="card-label">Session Created</span></h2>
                <div className="grid-2">
                  <div>
                    <label>Session ID</label>
                    <code style={{ fontSize: 14, display: 'block', padding: '8px 12px' }}>{createResult.session_id}</code>
                  </div>
                  <div>
                    <label>Tester Game URL</label>
                    <code style={{ fontSize: 11, display: 'block', padding: '8px 12px', wordBreak: 'break-all' }}>
                      {`http://localhost:8080/game/index.html?session=${createResult.session_id}&project=${projectId}`}
                    </code>
                  </div>
                </div>
              </>
            ) : (
              <p style={{ color: '#ef4444' }}>❌ {createResult.error}</p>
            )}
          </div>
        )}

        <div className="card">
          <h2><span className="card-icon">📋</span><span className="card-label">Sessions ({sessions.length})</span></h2>
          {sessions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <p style={{ fontSize: 40, marginBottom: 8 }}>🎮</p>
              <p className="text-muted">No sessions yet. Create one to get started!</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Tester</th>
                  <th>Health Score</th>
                  <th>Chunks</th>
                  <th>Duration</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => (
                  <tr key={s.session_id}>
                    <td><code>{s.session_id}</code></td>
                    <td style={{ fontWeight: 600 }}>🧑‍🎮 {s.tester_name}</td>
                    <td>{healthBadge(s.health_score)}</td>
                    <td><span className="stat-pill stat-pill-purple">{s.chunks_processed ?? '—'}</span></td>
                    <td><span className="stat-pill">⏱ {s.duration_sec}s</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
