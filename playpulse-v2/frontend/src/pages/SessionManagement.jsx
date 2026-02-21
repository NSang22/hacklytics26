import { useState, useEffect, useRef, useCallback } from 'react';

const API = 'http://localhost:8000';

export default function SessionManagement() {
  const [projectId, setProjectId] = useState('');
  const [sessions, setSessions] = useState([]);
  const [testerName, setTesterName] = useState('');
  const [chunkDuration, setChunkDuration] = useState(15);
  const [createResult, setCreateResult] = useState(null);

  // Live data collection monitor
  const [monitorSessionId, setMonitorSessionId] = useState('');
  const [collectionStatus, setCollectionStatus] = useState(null);
  const pollRef = useRef(null);

  const load = async () => {
    if (!projectId) return;
    try {
      const resp = await fetch(`${API}/v1/projects/${projectId}/aggregate`);
      const data = await resp.json();
      setSessions(data.sessions || []);
    } catch { setSessions([]); }
  };

  useEffect(() => { if (projectId) load(); }, [projectId]);

  const create = async () => {
    try {
      const resp = await fetch(`${API}/v1/projects/${projectId}/sessions`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tester_name: testerName || 'tester', chunk_duration_sec: chunkDuration }),
      });
      const data = await resp.json();
      setCreateResult(data);
      if (data.session_id) {
        setMonitorSessionId(data.session_id);
      }
      load();
    } catch (e) { setCreateResult({ error: e.message }); }
  };

  // Poll collection status for the monitored session
  const pollStatus = useCallback(async () => {
    if (!monitorSessionId) return;
    try {
      const resp = await fetch(`${API}/v1/sessions/${monitorSessionId}/collection-status`);
      if (resp.ok) {
        setCollectionStatus(await resp.json());
      }
    } catch { /* ignore */ }
  }, [monitorSessionId]);

  useEffect(() => {
    if (monitorSessionId) {
      pollStatus();
      pollRef.current = setInterval(pollStatus, 3000);
      return () => clearInterval(pollRef.current);
    } else {
      setCollectionStatus(null);
    }
  }, [monitorSessionId, pollStatus]);

  const healthBadge = (score) => {
    if (score == null) return <span className="badge badge-nodata">—</span>;
    const cls = score >= 0.7 ? 'badge-pass' : score >= 0.5 ? 'badge-warn' : 'badge-fail';
    return <span className={`badge ${cls}`}>{score.toFixed(2)}</span>;
  };

  const statusColor = (st) => {
    if (st === 'complete') return '#22c55e';
    if (st === 'recording') return '#ef4444';
    if (st === 'processing') return '#f59e0b';
    return '#94a3b8';
  };

  return (
    <div>
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
              <p className="text-sm text-muted" style={{ marginTop: 8 }}>
                💡 <strong>Desktop Client:</strong> Paste this Session ID into the AURA Desktop Agent to start screen + webcam + watch capture.
              </p>
            </>
          ) : (
            <p style={{ color: 'var(--neon-red)' }}>❌ {createResult.error}</p>
          )}
        </div>
      )}

      {/* ── Live Data Collection Monitor ──────────────── */}
      <div className="card" style={{ borderLeft: '3px solid #3b82f6' }}>
        <h2><span className="card-icon">📡</span><span className="card-label">Live Collection Monitor</span></h2>
        <div className="row" style={{ gap: 10, marginBottom: 12 }}>
          <input
            value={monitorSessionId}
            onChange={e => setMonitorSessionId(e.target.value)}
            placeholder="Session ID to monitor…"
            style={{ maxWidth: 300 }}
          />
          <button onClick={pollStatus}>🔄 Refresh</button>
        </div>

        {collectionStatus ? (
          <div>
            <div className="row" style={{ gap: 16, marginBottom: 12, flexWrap: 'wrap' }}>
              <div style={{ textAlign: 'center', minWidth: 90 }}>
                <div style={{ fontSize: 28, fontWeight: 800, color: statusColor(collectionStatus.status) }}>
                  {collectionStatus.status?.toUpperCase()}
                </div>
                <div className="text-sm text-muted">Status</div>
              </div>
              <div style={{ textAlign: 'center', minWidth: 70 }}>
                <div style={{ fontSize: 28, fontWeight: 800 }}>{collectionStatus.chunks_uploaded}</div>
                <div className="text-sm text-muted">🖥️ Chunks</div>
              </div>
              <div style={{ textAlign: 'center', minWidth: 70 }}>
                <div style={{ fontSize: 28, fontWeight: 800 }}>{collectionStatus.chunks_processed}</div>
                <div className="text-sm text-muted">⚙️ Processed</div>
              </div>
              <div style={{ textAlign: 'center', minWidth: 70 }}>
                <div style={{ fontSize: 28, fontWeight: 800 }}>{collectionStatus.emotion_frames}</div>
                <div className="text-sm text-muted">📷 Emotions</div>
              </div>
              <div style={{ textAlign: 'center', minWidth: 70 }}>
                <div style={{ fontSize: 28, fontWeight: 800 }}>{collectionStatus.watch_readings}</div>
                <div className="text-sm text-muted">⌚ Watch</div>
              </div>
              <div style={{ textAlign: 'center', minWidth: 70 }}>
                <div style={{ fontSize: 28, fontWeight: 800 }}>{collectionStatus.has_face_video ? '✅' : '—'}</div>
                <div className="text-sm text-muted">🎬 Face Video</div>
              </div>
            </div>
            {/* Stream health indicators */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <span className={`badge ${collectionStatus.chunks_uploaded > 0 ? 'badge-pass' : 'badge-nodata'}`}>
                Screen {collectionStatus.chunks_uploaded > 0 ? '● Live' : '○ Waiting'}
              </span>
              <span className={`badge ${collectionStatus.emotion_frames > 0 ? 'badge-pass' : 'badge-nodata'}`}>
                Presage {collectionStatus.emotion_frames > 0 ? '● Live' : '○ Waiting'}
              </span>
              <span className={`badge ${collectionStatus.watch_readings > 0 ? 'badge-pass' : 'badge-nodata'}`}>
                Watch {collectionStatus.watch_readings > 0 ? '● Live' : '○ Waiting'}
              </span>
            </div>
          </div>
        ) : (
          <p className="text-muted" style={{ textAlign: 'center', padding: 16 }}>
            Enter a session ID to monitor data collection in real time
          </p>
        )}
      </div>

      {/* ── Session List ─────────────────────────────── */}
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
                <th>Monitor</th>
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
                  <td>
                    <button
                      className="btn-sm"
                      onClick={() => setMonitorSessionId(s.session_id)}
                      style={{ fontSize: 11, padding: '2px 8px' }}
                    >
                      📡
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
