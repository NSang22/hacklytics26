import { useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, BarChart, Bar, Cell,
} from 'recharts';

const API = 'http://localhost:8000';

const EMOTION_COLORS = {
  frustration: '#ef4444', confusion: '#f59e0b', delight: '#22c55e',
  boredom: '#94a3b8', surprise: '#3b82f6', engagement: '#8b5cf6',
};

const SEVERITY_COLORS = {
  info: '#3b82f6', warning: '#f59e0b', error: '#ef4444', critical: '#dc2626',
};

const SEVERITY_ICONS = {
  info: 'ℹ️', warning: '⚠️', error: '❌', critical: '💀',
};

export default function SessionReview() {
  const [sid, setSid] = useState('');
  const [timeline, setTimeline] = useState([]);
  const [verdicts, setVerdicts] = useState([]);
  const [health, setHealth] = useState(null);
  const [insights, setInsights] = useState('');
  const [chunks, setChunks] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  const load = async () => {
    if (!sid) return;
    setLoading(true);
    try {
      const [tl, vd, hs, ins, ch, ev] = await Promise.all([
        fetch(`${API}/v1/sessions/${sid}/timeline`).then(r => r.json()),
        fetch(`${API}/v1/sessions/${sid}/verdicts`).then(r => r.json()),
        fetch(`${API}/v1/sessions/${sid}/health-score`).then(r => r.json()),
        fetch(`${API}/v1/sessions/${sid}/insights`).then(r => r.json()),
        fetch(`${API}/v1/sessions/${sid}/chunks`).then(r => r.json()).catch(() => ({ chunks: [] })),
        fetch(`${API}/v1/sessions/${sid}/events`).then(r => r.json()).catch(() => ({ events: [] })),
      ]);
      setTimeline(tl.rows || []);
      setVerdicts(vd.verdicts || []);
      setHealth(hs.health_score ?? null);
      setInsights(ins.insights || '');
      setChunks(ch.chunks || []);
      setEvents(ev.events || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  // Derived stats
  const totalDeaths = events.filter(e => (e.label || '').toLowerCase().includes('death')).length;
  const totalEvents = events.length;
  const totalChunks = chunks.length;

  const healthClass = health >= 0.7 ? 'health-good' : health >= 0.5 ? 'health-ok' : 'health-bad';
  const verdictBadge = (v) => {
    const cls = v === 'PASS' ? 'badge-pass' : v === 'WARN' ? 'badge-warn' : v === 'FAIL' ? 'badge-fail' : 'badge-nodata';
    return <span className={`badge ${cls}`}>{v}</span>;
  };
  const verdictClass = (v) => v === 'PASS' ? 'verdict-pass' : v === 'WARN' ? 'verdict-warn' : v === 'FAIL' ? 'verdict-fail' : '';

  const tabs = [
    { key: 'overview', label: '📊 Overview', count: null },
    { key: 'chunks', label: '🧩 Chunks', count: totalChunks },
    { key: 'events', label: '⚡ Events', count: totalEvents },
    { key: 'verdicts', label: '⚖️ Verdicts', count: verdicts.length },
  ];

  return (
    <div>
      <h1 className="page-title">📊 Session Review</h1>
      <p className="page-subtitle"><span className="dot dot-green" /> Deep-dive into a single playtest session</p>

      <div className="card card-green">
        <h2><span className="card-icon">🔍</span><span className="card-label">Load Session</span></h2>
        <div className="row">
          <input value={sid} onChange={e => setSid(e.target.value)} placeholder="Paste Session ID here..." style={{ maxWidth: 340 }} />
          <button className="btn-success" onClick={load} disabled={loading}>{loading ? '⏳ Loading...' : '🚀 Load Session'}</button>
        </div>
      </div>

      {health !== null && (
        <>
          {/* Quick Stats Bar */}
          <div className="stat-bar">
            <div className="stat-bar-item">
              <span className="stat-bar-icon">💓</span>
              <span className="stat-bar-value" style={{ color: health >= 0.7 ? '#22c55e' : health >= 0.5 ? '#f59e0b' : '#ef4444' }}>{health.toFixed(2)}</span>
              <span className="stat-bar-label">Health</span>
            </div>
            <div className="stat-bar-item">
              <span className="stat-bar-icon">🧩</span>
              <span className="stat-bar-value">{totalChunks}</span>
              <span className="stat-bar-label">Chunks</span>
            </div>
            <div className="stat-bar-item">
              <span className="stat-bar-icon">⚡</span>
              <span className="stat-bar-value">{totalEvents}</span>
              <span className="stat-bar-label">Events</span>
            </div>
            <div className="stat-bar-item">
              <span className="stat-bar-icon">💀</span>
              <span className="stat-bar-value" style={{ color: totalDeaths > 0 ? '#ef4444' : '#22c55e' }}>{totalDeaths}</span>
              <span className="stat-bar-label">Deaths</span>
            </div>
            <div className="stat-bar-item">
              <span className="stat-bar-icon">⚖️</span>
              <span className="stat-bar-value">{verdicts.filter(v => v.verdict === 'FAIL').length}</span>
              <span className="stat-bar-label">Fails</span>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="tab-bar">
            {tabs.map(t => (
              <button key={t.key} className={`tab-btn ${activeTab === t.key ? 'tab-active' : ''}`} onClick={() => setActiveTab(t.key)}>
                {t.label}
                {t.count !== null && <span className="tab-count">{t.count}</span>}
              </button>
            ))}
          </div>

          {/* ═══ OVERVIEW TAB ═══ */}
          {activeTab === 'overview' && (
            <>
              <div className="grid-2">
                {/* Emotion Timeline */}
                <div className="card card-blue">
                  <h2><span className="card-icon">🎭</span><span className="card-label">Emotion Timeline</span></h2>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={timeline}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="timestamp_sec" stroke="#94a3b8" tick={{ fontSize: 11 }} label={{ value: 'Time (s)', position: 'insideBottom', offset: -2 }} />
                      <YAxis stroke="#94a3b8" domain={[0, 1]} tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12 }} />
                      <Legend />
                      {Object.entries(EMOTION_COLORS).map(([key, color]) => (
                        <Line key={key} type="monotone" dataKey={key} stroke={color} dot={false} strokeWidth={2} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* HR Timeline */}
                <div className="card card-red">
                  <h2><span className="card-icon">❤️</span><span className="card-label">Heart Rate</span></h2>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={timeline}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="timestamp_sec" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                      <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12 }} />
                      <Legend />
                      <Line type="monotone" dataKey="watch_hr" stroke="#f97316" dot={false} name="Watch HR" strokeWidth={2} />
                      <Line type="monotone" dataKey="presage_hr" stroke="#8b5cf6" dot={false} name="Presage HR" strokeWidth={2} />
                      <ReferenceLine y={80} stroke="#cbd5e1" strokeDasharray="5 5" label="Baseline" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Insights */}
              <div className="card card-purple">
                <h2><span className="card-icon">✨</span><span className="card-label">Gemini Insights</span></h2>
                <div className="insights">{insights}</div>
              </div>
            </>
          )}

          {/* ═══ CHUNKS TAB ═══ */}
          {activeTab === 'chunks' && (
            <div className="card">
              <h2><span className="card-icon">🧩</span><span className="card-label">Chunk-by-Chunk Analysis ({totalChunks} chunks)</span></h2>
              {chunks.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon">📭</div>
                  <p className="text-muted">No chunks processed yet.</p>
                </div>
              ) : (
                <div className="chunk-grid">
                  {chunks.map((c, i) => (
                    <div key={i} className="chunk-card">
                      <div className="chunk-header">
                        <span className="chunk-number">#{c.chunk_index}</span>
                        <span className="text-sm text-muted">{c.chunk_start_sec}s – {c.chunk_start_sec + 15}s</span>
                        <span className="stat-pill stat-pill-green">{c.states_observed?.length || 0} observations</span>
                      </div>
                      {/* States observed */}
                      <div className="chunk-states">
                        {(c.states_observed || []).map((s, j) => (
                          <div key={j} className="chunk-state-row">
                            <span className="badge badge-pass">{s.state}</span>
                            <span className="stat-pill" style={{ marginLeft: 'auto' }}>{(s.confidence * 100).toFixed(0)}%</span>
                            <span className="text-sm text-muted">@ {s.timestamp_in_chunk_sec}s</span>
                          </div>
                        ))}
                      </div>
                      {/* Events in this chunk */}
                      {(c.events || []).length > 0 && (
                        <div className="chunk-events">
                          {c.events.map((e, j) => (
                            <div key={j} className="event-row">
                              <span>{SEVERITY_ICONS[e.severity] || 'ℹ️'}</span>
                              <span className="text-sm" style={{ flex: 1 }}>{e.description}</span>
                              <span className="text-sm text-muted">@ {e.timestamp_sec}s</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {/* Notes */}
                      {c.notes && <p className="text-sm text-muted chunk-notes">📝 {c.notes}</p>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ═══ EVENTS TAB ═══ */}
          {activeTab === 'events' && (
            <>
              {/* Death counter banner */}
              {totalDeaths > 0 && (
                <div className="card card-red" style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 48, marginBottom: 4 }}>💀</div>
                  <div style={{ fontSize: 36, fontWeight: 900, color: '#ef4444' }}>{totalDeaths}</div>
                  <p className="text-sm text-muted">Total Deaths Detected</p>
                </div>
              )}

              <div className="card">
                <h2><span className="card-icon">⚡</span><span className="card-label">Gameplay Events ({totalEvents})</span></h2>
                {events.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon">⚡</div>
                    <p className="text-muted">No events detected during this session.</p>
                  </div>
                ) : (
                  <div className="event-timeline">
                    {events.map((e, i) => (
                      <div key={i} className="event-timeline-item" style={{ borderLeftColor: SEVERITY_COLORS[e.severity] || '#3b82f6' }}>
                        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 20 }}>{SEVERITY_ICONS[e.severity] || 'ℹ️'}</span>
                          <strong>{e.label}</strong>
                          <span className={`badge badge-${e.severity === 'error' || e.severity === 'critical' ? 'fail' : e.severity === 'warning' ? 'warn' : 'pass'}`}>{e.severity}</span>
                          <span className="stat-pill" style={{ marginLeft: 'auto' }}>⏱ {e.timestamp_sec}s</span>
                        </div>
                        <p className="text-sm text-muted" style={{ marginTop: 4, marginLeft: 32 }}>{e.description}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Events by severity chart */}
              {events.length > 0 && (
                <div className="card card-orange">
                  <h2><span className="card-icon">📊</span><span className="card-label">Events by Severity</span></h2>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={
                      Object.entries(events.reduce((acc, e) => { acc[e.severity] = (acc[e.severity] || 0) + 1; return acc; }, {}))
                        .map(([sev, count]) => ({ severity: sev, count }))
                    }>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="severity" stroke="#94a3b8" />
                      <YAxis stroke="#94a3b8" allowDecimals={false} />
                      <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12 }} />
                      <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                        {Object.entries(events.reduce((acc, e) => { acc[e.severity] = (acc[e.severity] || 0) + 1; return acc; }, {}))
                          .map(([sev], i) => (
                            <Cell key={i} fill={SEVERITY_COLORS[sev] || '#3b82f6'} />
                          ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          )}

          {/* ═══ VERDICTS TAB ═══ */}
          {activeTab === 'verdicts' && (
            <div className="card card-orange">
              <h2><span className="card-icon">⚖️</span><span className="card-label">Intent vs Reality — Verdicts</span></h2>
              <div className="grid-3 mt">
                {verdicts.map((v, i) => (
                  <div key={i} className={`verdict-card ${verdictClass(v.verdict)}`}>
                    <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
                      <strong>{v.state_name}</strong>
                      {verdictBadge(v.verdict)}
                    </div>
                    <p className="text-sm text-muted">Intended: <em>{v.intended_emotion}</em></p>
                    <p className="text-sm text-muted">Actual dominant: <em>{v.actual_dominant_emotion}</em></p>
                    <p className="text-sm">Score: {(v.actual_avg_score ?? 0).toFixed(2)}
                      <span className="text-muted"> (range: {(v.acceptable_range || [0,0]).join(' – ')})</span>
                    </p>
                    <p className="text-sm">Duration: {v.actual_duration_sec}s
                      <span className="text-muted"> (expected: {v.expected_duration_sec}s, Δ{v.time_delta_sec > 0 ? '+' : ''}{v.time_delta_sec}s)</span>
                    </p>
                    <p className="text-sm">Deviation: <strong>{(v.deviation_score ?? 0).toFixed(3)}</strong></p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
