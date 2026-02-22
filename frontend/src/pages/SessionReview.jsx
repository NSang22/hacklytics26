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
  // Session state
  const [sid, setSid] = useState('');
  const [timeline, setTimeline] = useState([]);
  const [verdicts, setVerdicts] = useState([]);
  const [health, setHealth] = useState(null);
  const [insights, setInsights] = useState('');
  const [chunks, setChunks] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  // Aggregate (Compare) state
  const [projectId, setProjectId] = useState('');
  const [agg, setAgg] = useState(null);
  const [allVerdicts, setAllVerdicts] = useState(null);
  const [aggInsights, setAggInsights] = useState('');
  const [healthTrend, setHealthTrend] = useState([]);
  const [aggLoading, setAggLoading] = useState(false);

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

  const loadAgg = async () => {
    if (!projectId) return;
    setAggLoading(true);
    try {
      const [ag, vd, ins, ht] = await Promise.all([
        fetch(`${API}/v1/projects/${projectId}/aggregate`).then(r => r.json()),
        fetch(`${API}/v1/projects/${projectId}/aggregate/verdicts`).then(r => r.json()),
        fetch(`${API}/v1/projects/${projectId}/aggregate/insights`).then(r => r.json()),
        fetch(`${API}/v1/projects/${projectId}/health-trend`).then(r => r.json()).catch(() => ({ trend: [] })),
      ]);
      setAgg(ag);
      setAllVerdicts(vd);
      setAggInsights(ins.insights || '');
      setHealthTrend(ht.trend || []);
    } catch (e) { console.error(e); }
    setAggLoading(false);
  };

  const stateSummary = () => {
    if (!allVerdicts?.by_session) return [];
    const map = {};
    for (const [, vds] of Object.entries(allVerdicts.by_session)) {
      for (const v of vds) {
        if (!map[v.state_name]) map[v.state_name] = { state: v.state_name, pass: 0, warn: 0, fail: 0, total: 0, frustrations: [] };
        const m = map[v.state_name];
        m.total++;
        if (v.verdict === 'PASS') m.pass++;
        else if (v.verdict === 'WARN') m.warn++;
        else if (v.verdict === 'FAIL') m.fail++;
        m.frustrations.push(v.actual_distribution?.frustration ?? 0);
      }
    }
    return Object.values(map).map(m => ({
      ...m,
      avg_frustration: +(m.frustrations.reduce((a, b) => a + b, 0) / (m.frustrations.length || 1)).toFixed(3),
    }));
  };

  const totalDeaths = events.filter(e => (e.label || '').toLowerCase().includes('death')).length;
  const totalEvents = events.length;
  const totalChunks = chunks.length;
  const aggSummary = stateSummary();
  const healthBars = (agg?.sessions || []).map(s => ({
    name: s.tester_name || s.session_id.slice(0, 6),
    health_score: +(s.health_score ?? 0).toFixed(2),
  }));

  const tabs = [
    { key: 'overview', label: '📊 Overview',  count: null },
    { key: 'chunks',   label: '🧩 Chunks',    count: totalChunks },
    { key: 'events',   label: '⚡ Events',        count: totalEvents },
    { key: 'verdicts', label: '⚖️ Verdicts', count: verdicts.length },
    { key: 'compare',  label: '🏆 Compare',   count: null },
  ];

  return (
    <div
      className="min-h-screen text-white"
      style={{
        backgroundImage: "url('/background5.jpg')",
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundAttachment: 'fixed',
      }}
    >
      {/* Overlay */}
      <div className="fixed inset-0 bg-gradient-to-t from-black/60 to-black/90 pointer-events-none" />

      {/* Amber ambient glows */}
      <div className="fixed -top-40 -left-40 w-[600px] h-[600px] bg-[#f59e0b]/8 blur-[160px] rounded-full pointer-events-none" />
      <div className="fixed -bottom-40 -right-40 w-[500px] h-[500px] bg-[#f59e0b]/6 blur-[140px] rounded-full pointer-events-none" />

      {/* Floating header */}
      <div className="relative z-10 max-w-5xl mx-auto px-6 pt-6 pb-2">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-2 h-2 rounded-full bg-[#f59e0b] animate-pulse shadow-[0_0_8px_rgba(245,158,11,0.9)]" />
          <span className="text-xs text-white/70 tracking-widest uppercase font-mono">Session Review</span>
          <span className="text-white/70 font-mono text-xs select-none">·</span>
          <span className="text-xs text-white/70 font-mono">Deep-dive into a single playtest session</span>
        </div>
        <div className="h-px w-full" style={{ background: 'linear-gradient(90deg, rgba(245,158,11,0.35) 0%, rgba(255,255,255,0.05) 60%, transparent 100%)' }} />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 pb-12 space-y-5">

        {/* Session Load Card */}
        <div className="rounded-3xl border border-white/10 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.35)]" style={{ background: 'rgba(255,255,255,0.05)' }}>
          <div className="flex items-center gap-3 mb-1">
            <div className="w-1.5 h-1.5 rounded-full bg-[#f59e0b] shadow-[0_0_6px_rgba(245,158,11,0.8)]" />
            <span className="text-xs font-bold tracking-widest uppercase text-[#fcd34d]">Load Session</span>
          </div>
          <p className="text-[11px] text-white/70 mb-4 font-mono">Paste a session ID to load its data</p>
          <div className="flex items-center gap-3">
            <input
              value={sid}
              onChange={e => setSid(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && load()}
              placeholder="Paste Session ID…"
              className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-[#f59e0b]/40 transition-colors"
            />
            <button
              onClick={load}
              disabled={loading}
              className="px-6 py-2.5 rounded-full text-xs font-bold tracking-widest uppercase transition-all hover:scale-[1.03] disabled:opacity-50"
              style={{ background: 'rgba(245,158,11,0.14)', border: '1px solid rgba(245,158,11,0.30)', color: '#fcd34d' }}
            >
              {loading ? '⏳ Loading…' : '🚀 Load'}
            </button>
          </div>
        </div>

        {health !== null && (
          <>
            {/* Stat strip */}
            <div className="grid grid-cols-5 gap-3">
              {[
                { icon: '💓', value: health.toFixed(2), label: 'Health', color: health >= 0.7 ? '#22c55e' : health >= 0.5 ? '#f59e0b' : '#ef4444' },
                { icon: '🧩', value: totalChunks,  label: 'Chunks',  color: '#fcd34d' },
                { icon: '⚡',    value: totalEvents,  label: 'Events',  color: '#fcd34d' },
                { icon: '💀', value: totalDeaths, label: 'Deaths',  color: totalDeaths > 0 ? '#ef4444' : '#22c55e' },
                { icon: '⚖️', value: verdicts.filter(v => v.verdict === 'FAIL').length, label: 'Fails', color: '#ef4444' },
              ].map(s => (
                <div key={s.label} className="rounded-2xl p-4 text-center backdrop-blur-xl border border-white/10" style={{ background: 'rgba(255,255,255,0.05)' }}>
                  <div className="text-xl mb-1">{s.icon}</div>
                  <div className="text-lg font-bold font-mono" style={{ color: s.color }}>{s.value}</div>
                  <div className="text-[10px] text-white/30 uppercase tracking-widest font-mono mt-0.5">{s.label}</div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Tab pills */}
        <div className="flex items-center gap-2">
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className="px-5 py-2 text-xs tracking-wider font-semibold transition-all duration-200 rounded-full"
              style={{
                color: activeTab === t.key ? 'white' : 'rgba(255,255,255,0.30)',
                background: activeTab === t.key ? 'rgba(245,158,11,0.18)' : 'rgba(255,255,255,0.04)',
                border: activeTab === t.key ? '1px solid rgba(245,158,11,0.40)' : '1px solid rgba(255,255,255,0.07)',
                boxShadow: activeTab === t.key ? '0 0 18px rgba(245,158,11,0.15)' : 'none',
              }}
            >
              {t.label}{t.count !== null && <span className="ml-1.5 text-[10px] opacity-60">({t.count})</span>}
            </button>
          ))}
        </div>

        {/* Overview */}
        {activeTab === 'overview' && (
          health === null ? (
            <div className="flex flex-col items-center py-20 gap-3">
              <span className="text-5xl opacity-20">📊</span>
              <p className="text-xs text-white/20 font-mono tracking-widest uppercase">Load a session to see overview</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
                  <h2 className="font-eb-garamond text-xl font-bold text-white mb-4">Emotion Timeline</h2>
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={timeline}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="timestamp_sec" stroke="rgba(255,255,255,0.2)" tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)' }} />
                      <YAxis stroke="rgba(255,255,255,0.2)" domain={[0,1]} tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)' }} />
                      <Tooltip contentStyle={{ background: 'rgba(10,10,15,0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, color: '#fff' }} />
                      <Legend wrapperStyle={{ fontSize: 11, color: 'rgba(255,255,255,0.4)' }} />
                      {Object.entries(EMOTION_COLORS).map(([key, color]) => (
                        <Line key={key} type="monotone" dataKey={key} stroke={color} dot={false} strokeWidth={2} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
                  <h2 className="font-eb-garamond text-xl font-bold text-white mb-4">Heart Rate</h2>
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={timeline}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="timestamp_sec" stroke="rgba(255,255,255,0.2)" tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)' }} />
                      <YAxis stroke="rgba(255,255,255,0.2)" tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)' }} />
                      <Tooltip contentStyle={{ background: 'rgba(10,10,15,0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, color: '#fff' }} />
                      <Legend wrapperStyle={{ fontSize: 11, color: 'rgba(255,255,255,0.4)' }} />
                      <Line type="monotone" dataKey="watch_hr" stroke="#f97316" dot={false} name="Watch HR" strokeWidth={2} />
                      <Line type="monotone" dataKey="presage_hr" stroke="#8b5cf6" dot={false} name="Presage HR" strokeWidth={2} />
                      <ReferenceLine y={80} stroke="rgba(255,255,255,0.15)" strokeDasharray="5 5" label={{ value: 'Baseline', fill: 'rgba(255,255,255,0.25)', fontSize: 10 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="rounded-3xl border border-[#f59e0b]/20 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(245,158,11,0.08)]" style={{ background: 'rgba(245,158,11,0.07)' }}>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-2 h-2 rounded-full bg-[#f59e0b] shadow-[0_0_6px_rgba(245,158,11,0.8)]" />
                  <span className="text-xs font-bold tracking-widest uppercase text-[#fcd34d]">Gemini Insights</span>
                </div>
                <p className="text-sm text-white/60 leading-relaxed">{insights || 'No insights loaded yet.'}</p>
              </div>
            </div>
          )
        )}

        {/* Chunks */}
        {activeTab === 'chunks' && (
          health === null ? (
            <div className="flex flex-col items-center py-20 gap-3">
              <span className="text-5xl opacity-20">🧩</span>
              <p className="text-xs text-white/20 font-mono tracking-widest uppercase">Load a session to see chunks</p>
            </div>
          ) : (
            <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <div className="flex items-baseline gap-3 mb-4">
                <h2 className="font-eb-garamond text-2xl font-bold text-white">Chunk-by-Chunk Analysis</h2>
                <span className="text-[11px] text-white/25 font-mono">{totalChunks} chunks</span>
              </div>
              {chunks.length === 0 ? (
                <div className="flex flex-col items-center py-12 gap-3">
                  <span className="text-4xl opacity-30">📭</span>
                  <p className="text-xs text-white/25 font-mono tracking-widest uppercase">No chunks processed yet</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {chunks.map((c, i) => (
                    <div key={i} className="rounded-2xl p-4 border border-white/8" style={{ background: 'rgba(255,255,255,0.04)' }}>
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-[10px] font-black font-mono px-2 py-1 rounded-lg" style={{ background: 'rgba(245,158,11,0.15)', color: '#fcd34d', border: '1px solid rgba(245,158,11,0.25)' }}>#{c.chunk_index}</span>
                        <span className="text-xs text-white/30 font-mono">{c.chunk_start_sec}s – {c.chunk_start_sec + 15}s</span>
                        <span className="ml-auto text-[10px] text-white/25 font-mono">{c.states_observed?.length || 0} obs</span>
                      </div>
                      {(c.states_observed || []).map((s, j) => (
                        <div key={j} className="flex items-center gap-2 py-1">
                          <span className="text-[10px] px-2 py-0.5 rounded-md font-mono" style={{ background: 'rgba(34,197,94,0.15)', color: '#86efac', border: '1px solid rgba(34,197,94,0.2)' }}>{s.state}</span>
                          <span className="text-[10px] text-white/30 font-mono ml-auto">{(s.confidence * 100).toFixed(0)}%</span>
                          <span className="text-[10px] text-white/20 font-mono">@ {s.timestamp_in_chunk_sec}s</span>
                        </div>
                      ))}
                      {(c.events || []).map((e, j) => (
                        <div key={j} className="flex items-center gap-2 py-1 border-t border-white/5 mt-1">
                          <span>{SEVERITY_ICONS[e.severity] || 'ℹ️'}</span>
                          <span className="text-xs text-white/50 flex-1">{e.description}</span>
                          <span className="text-[10px] text-white/20 font-mono">@ {e.timestamp_sec}s</span>
                        </div>
                      ))}
                      {c.notes && <p className="text-[10px] text-white/25 mt-2 font-mono">📝 {c.notes}</p>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        )}

        {/* Events */}
        {activeTab === 'events' && (
          health === null ? (
            <div className="flex flex-col items-center py-20 gap-3">
              <span className="text-5xl opacity-20">⚡</span>
              <p className="text-xs text-white/20 font-mono tracking-widest uppercase">Load a session to see events</p>
            </div>
          ) : (
            <div className="space-y-4">
              {totalDeaths > 0 && (
                <div className="rounded-3xl border border-red-500/20 p-6 text-center backdrop-blur-xl" style={{ background: 'rgba(239,68,68,0.07)' }}>
                  <div className="text-5xl mb-2">💀</div>
                  <div className="text-4xl font-black font-mono text-red-400">{totalDeaths}</div>
                  <p className="text-xs text-white/30 mt-1 uppercase tracking-widest font-mono">Total Deaths Detected</p>
                </div>
              )}

              <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
                <div className="flex items-baseline gap-3 mb-4">
                  <h2 className="font-eb-garamond text-2xl font-bold text-white">Gameplay Events</h2>
                  <span className="text-[11px] text-white/25 font-mono">{totalEvents} total</span>
                </div>
                {events.length === 0 ? (
                  <div className="flex flex-col items-center py-12 gap-3">
                    <span className="text-4xl opacity-30">⚡</span>
                    <p className="text-xs text-white/25 font-mono tracking-widest uppercase">No events detected</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {events.map((e, i) => (
                      <div key={i} className="flex items-start gap-3 py-2.5 px-3 rounded-xl hover:bg-white/[0.03] transition-colors" style={{ borderLeft: `2px solid ${SEVERITY_COLORS[e.severity] || '#f59e0b'}40` }}>
                        <span className="text-lg shrink-0">{SEVERITY_ICONS[e.severity] || 'ℹ️'}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className="text-sm font-semibold text-white/80">{e.label}</span>
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-md" style={{ background: `${SEVERITY_COLORS[e.severity]}20`, color: SEVERITY_COLORS[e.severity] || '#f59e0b', border: `1px solid ${SEVERITY_COLORS[e.severity]}30` }}>{e.severity}</span>
                          </div>
                          <p className="text-xs text-white/35">{e.description}</p>
                        </div>
                        <span className="text-[10px] text-white/20 font-mono shrink-0">⏱ {e.timestamp_sec}s</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {events.length > 0 && (
                <div className="rounded-3xl border border-[#f59e0b]/20 p-6 backdrop-blur-xl" style={{ background: 'rgba(245,158,11,0.06)' }}>
                  <h2 className="font-eb-garamond text-xl font-bold text-white mb-4">Events by Severity</h2>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={Object.entries(events.reduce((acc, e) => { acc[e.severity] = (acc[e.severity] || 0) + 1; return acc; }, {})).map(([sev, count]) => ({ severity: sev, count }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="severity" stroke="rgba(255,255,255,0.2)" tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)' }} />
                      <YAxis stroke="rgba(255,255,255,0.2)" allowDecimals={false} tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)' }} />
                      <Tooltip contentStyle={{ background: 'rgba(10,10,15,0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, color: '#fff' }} />
                      <Bar dataKey="count" radius={[8,8,0,0]}>
                        {Object.entries(events.reduce((acc, e) => { acc[e.severity] = (acc[e.severity] || 0) + 1; return acc; }, {})).map(([sev], i) => (
                          <Cell key={i} fill={SEVERITY_COLORS[sev] || '#f59e0b'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )
        )}

        {/* Verdicts */}
        {activeTab === 'verdicts' && (
          health === null ? (
            <div className="flex flex-col items-center py-20 gap-3">
              <span className="text-5xl opacity-20">⚖️</span>
              <p className="text-xs text-white/20 font-mono tracking-widest uppercase">Load a session to see verdicts</p>
            </div>
          ) : (
            <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <h2 className="font-eb-garamond text-2xl font-bold text-white mb-4">Intent vs Reality — Verdicts</h2>
              <div className="grid grid-cols-3 gap-3">
                {verdicts.map((v, i) => {
                  const vc = v.verdict === 'PASS' ? '#22c55e' : v.verdict === 'WARN' ? '#f59e0b' : '#ef4444';
                  return (
                    <div key={i} className="rounded-2xl p-4 border" style={{ background: `${vc}0d`, borderColor: `${vc}30` }}>
                      <div className="flex items-start justify-between mb-2">
                        <span className="text-sm font-semibold text-white/80">{v.state_name}</span>
                        <span className="text-[10px] font-black font-mono px-2 py-1 rounded-lg" style={{ background: `${vc}20`, color: vc }}>{v.verdict}</span>
                      </div>
                      <div className="space-y-0.5 text-[11px] text-white/40 font-mono">
                        <p>Intended: <span className="text-white/60">{v.intended_emotion}</span></p>
                        <p>Actual: <span className="text-white/60">{v.actual_dominant_emotion}</span></p>
                        <p>Score: <span className="text-white/60">{(v.actual_avg_score ?? 0).toFixed(2)}</span> <span className="text-white/20">(range: {(v.acceptable_range || [0,0]).join('–')})</span></p>
                        <p>Duration: <span className="text-white/60">{v.actual_duration_sec}s</span> <span className="text-white/20">(exp: {v.expected_duration_sec}s, Δ{v.time_delta_sec > 0 ? '+' : ''}{v.time_delta_sec}s)</span></p>
                        <p>Deviation: <span style={{ color: vc }}>{(v.deviation_score ?? 0).toFixed(3)}</span></p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )
        )}

        {/* Compare */}
        {activeTab === 'compare' && (
          <div className="space-y-5">
            <div className="rounded-3xl border border-white/10 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.35)]" style={{ background: 'rgba(255,255,255,0.05)' }}>
              <div className="flex items-center gap-3 mb-1">
                <div className="w-1.5 h-1.5 rounded-full bg-[#f59e0b] shadow-[0_0_6px_rgba(245,158,11,0.8)]" />
                <span className="text-xs font-bold tracking-widest uppercase text-[#fcd34d]">Load Project</span>
              </div>
              <p className="text-[11px] text-white/70 mb-4 font-mono">Paste a project ID to compare results across all testers</p>
              <div className="flex items-center gap-3">
                <input
                  value={projectId}
                  onChange={e => setProjectId(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && loadAgg()}
                  placeholder="Paste Project ID…"
                  className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-[#f59e0b]/40 transition-colors"
                />
                <button
                  onClick={loadAgg}
                  disabled={aggLoading}
                  className="px-6 py-2.5 rounded-full text-xs font-bold tracking-widest uppercase transition-all hover:scale-[1.03] disabled:opacity-50"
                  style={{ background: 'rgba(245,158,11,0.14)', border: '1px solid rgba(245,158,11,0.30)', color: '#fcd34d' }}
                >
                  {aggLoading ? '⏳ Loading…' : '🚀 Load'}
                </button>
              </div>
            </div>

            {!agg && (
              <div className="flex flex-col items-center py-16 gap-3">
                <span className="text-5xl opacity-20">🏆</span>
                <p className="text-xs text-white/20 font-mono tracking-widest uppercase">Load a project to compare testers</p>
              </div>
            )}

            {agg && (
              <>
                {healthTrend.length > 1 && (
                  <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
                    <h2 className="font-eb-garamond text-xl font-bold text-white mb-1">Health Score Trend</h2>
                    <p className="text-[11px] text-white/25 font-mono mb-4">Health scores across successive sessions</p>
                    <ResponsiveContainer width="100%" height={240}>
                      <LineChart data={healthTrend.map((t, i) => ({ ...t, index: i + 1, label: t.tester_name || `Session ${i + 1}` }))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                        <XAxis dataKey="label" stroke="rgba(255,255,255,0.2)" tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)' }} />
                        <YAxis domain={[0, 1]} stroke="rgba(255,255,255,0.2)" tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)' }} />
                        <Tooltip contentStyle={{ background: 'rgba(10,10,15,0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, color: '#fff' }} />
                        <Line type="monotone" dataKey="health_score" stroke="#14b8a6" strokeWidth={3} dot={{ fill: '#14b8a6', r: 5 }} name="Health Score" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}

                <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
                  <h2 className="font-eb-garamond text-xl font-bold text-white mb-4">Tester Health Score Comparison</h2>
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={healthBars}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="name" stroke="rgba(255,255,255,0.2)" tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)' }} />
                      <YAxis domain={[0, 1]} stroke="rgba(255,255,255,0.2)" tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)' }} />
                      <Tooltip contentStyle={{ background: 'rgba(10,10,15,0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, color: '#fff' }} />
                      <Bar dataKey="health_score" fill="#3b82f6" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {aggSummary.length > 0 && (
                  <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
                    <h2 className="font-eb-garamond text-xl font-bold text-white mb-4">Per-State Verdict Summary</h2>
                    <div className="space-y-2">
                      {aggSummary.map(s => (
                        <div key={s.state} className="flex items-center gap-4 px-4 py-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                          <span className="text-sm font-semibold text-white/70 flex-1">{s.state}</span>
                          <span className="text-[10px] font-black font-mono px-2 py-1 rounded-lg" style={{ background: 'rgba(34,197,94,0.15)', color: '#86efac', border: '1px solid rgba(34,197,94,0.25)' }}>PASS {s.pass}</span>
                          <span className="text-[10px] font-black font-mono px-2 py-1 rounded-lg" style={{ background: 'rgba(245,158,11,0.15)', color: '#fcd34d', border: '1px solid rgba(245,158,11,0.25)' }}>WARN {s.warn}</span>
                          <span className="text-[10px] font-black font-mono px-2 py-1 rounded-lg" style={{ background: 'rgba(239,68,68,0.15)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.25)' }}>FAIL {s.fail}</span>
                          <span className="text-[10px] text-white/30 font-mono w-28 text-right">Frustration {s.avg_frustration}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="rounded-3xl border border-red-500/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(239,68,68,0.05)' }}>
                  <h2 className="font-eb-garamond text-xl font-bold text-white mb-4">Pain Point Rankings</h2>
                  <div className="space-y-2">
                    {[...aggSummary].sort((a, b) => b.fail - a.fail || b.avg_frustration - a.avg_frustration).map((s, i) => {
                      const rankColors = ['#ef4444', '#f97316', '#f59e0b'];
                      const rc = rankColors[i] || '#94a3b8';
                      return (
                        <div key={s.state} className="flex items-center gap-3 px-4 py-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                          <span className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-black shrink-0" style={{ background: `${rc}25`, color: rc, border: `1px solid ${rc}40` }}>{i + 1}</span>
                          <span className="text-sm font-semibold text-white/70 flex-1">{s.state}</span>
                          <span className="text-[10px] font-mono px-2 py-1 rounded-md" style={{ background: 'rgba(239,68,68,0.15)', color: '#fca5a5' }}>Fail {s.total > 0 ? Math.round(s.fail / s.total * 100) : 0}%</span>
                          <span className="text-[10px] font-mono px-2 py-1 rounded-md" style={{ background: 'rgba(245,158,11,0.15)', color: '#fcd34d' }}>Frustration {s.avg_frustration}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {aggInsights && (
                  <div className="rounded-3xl border border-[#f59e0b]/20 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(245,158,11,0.08)]" style={{ background: 'rgba(245,158,11,0.07)' }}>
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-2 h-2 rounded-full bg-[#f59e0b] shadow-[0_0_6px_rgba(245,158,11,0.8)]" />
                      <span className="text-xs font-bold tracking-widest uppercase text-[#fcd34d]">Cross-Tester Insights</span>
                    </div>
                    <p className="text-sm text-white/60 leading-relaxed">{aggInsights}</p>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
