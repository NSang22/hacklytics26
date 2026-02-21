import { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, LineChart, Line,
} from 'recharts';

const API = 'http://localhost:8000';

export default function CrossTesterAggregate() {
  const [projectId, setProjectId] = useState('');
  const [agg, setAgg] = useState(null);
  const [allVerdicts, setAllVerdicts] = useState(null);
  const [insights, setInsights] = useState('');
  const [healthTrend, setHealthTrend] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [ag, vd, ins, ht] = await Promise.all([
        fetch(`${API}/v1/projects/${projectId}/aggregate`).then(r => r.json()),
        fetch(`${API}/v1/projects/${projectId}/aggregate/verdicts`).then(r => r.json()),
        fetch(`${API}/v1/projects/${projectId}/aggregate/insights`).then(r => r.json()),
        fetch(`${API}/v1/projects/${projectId}/health-trend`).then(r => r.json()).catch(() => ({ trend: [] })),
      ]);
      setAgg(ag);
      setAllVerdicts(vd);
      setInsights(ins.insights || '');
      setHealthTrend(ht.trend || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  // Build per-state summary from all verdicts
  const stateSummary = () => {
    if (!allVerdicts?.by_session) return [];
    const map = {};
    for (const [sid, vds] of Object.entries(allVerdicts.by_session)) {
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

  const summary = stateSummary();

  // Health score bar data
  const healthBars = (agg?.sessions || []).map(s => ({
    name: s.tester_name || s.session_id.slice(0, 6),
    health_score: +(s.health_score ?? 0).toFixed(2),
  }));

  return (
    <div>
      <h1 className="page-title">🏆 Cross-Tester Aggregate</h1>
      <p className="page-subtitle"><span className="dot dot-blue" /> Compare results across all testers in a project</p>

      <div className="card card-blue">
        <h2><span className="card-icon">📦</span><span className="card-label">Load Project</span></h2>
        <div className="row">
          <input value={projectId} onChange={e => setProjectId(e.target.value)} placeholder="Paste Project ID here..." style={{ maxWidth: 340 }} />
          <button onClick={load} disabled={loading}>{loading ? '⏳ Loading...' : '🚀 Load'}</button>
        </div>
      </div>

      {agg && (
        <>
          {/* Health Trend Over Time */}
          {healthTrend.length > 1 && (
            <div className="card card-teal">
              <h2><span className="card-icon">📈</span><span className="card-label">Health Score Trend</span></h2>
              <p className="text-sm text-muted mb">Tracks how playtest health scores evolve across successive sessions</p>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={healthTrend.map((t, i) => ({ ...t, index: i + 1, label: t.tester_name || `Session ${i + 1}` }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="label" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 1]} stroke="#94a3b8" tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12 }} />
                  <Line type="monotone" dataKey="health_score" stroke="#14b8a6" strokeWidth={3} dot={{ fill: '#14b8a6', r: 5 }} name="Health Score" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Health Score Comparison */}
          <div className="card card-green">
            <h2><span className="card-icon">📊</span><span className="card-label">Playtest Health Score Comparison</span></h2>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={healthBars}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis domain={[0, 1]} stroke="#94a3b8" />
                <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12 }} />
                <Bar dataKey="health_score" fill="#3b82f6" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Per-State Verdict Summary */}
          <div className="card card-orange">
            <h2><span className="card-icon">⚖️</span><span className="card-label">Per-State Verdict Summary</span></h2>
            {summary.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">📭</div>
                <p className="text-muted">No verdict data available yet.</p>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>State</th>
                    <th>PASS</th><th>WARN</th><th>FAIL</th>
                    <th>Avg Frustration</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.map(s => (
                    <tr key={s.state}>
                      <td><strong>{s.state}</strong></td>
                      <td><span className="badge badge-pass">{s.pass}</span></td>
                      <td><span className="badge badge-warn">{s.warn}</span></td>
                      <td><span className="badge badge-fail">{s.fail}</span></td>
                      <td><span className="stat-pill">{s.avg_frustration}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Pain Point Rankings */}
          <div className="card card-red">
            <h2><span className="card-icon">🔥</span><span className="card-label">Pain Point Rankings</span></h2>
            {summary.sort((a, b) => b.fail - a.fail || b.avg_frustration - a.avg_frustration).map((s, i) => (
              <div key={s.state} className="pain-row">
                <span className={`pain-rank ${i < 3 ? `rank-${i + 1}` : ''}`} style={i >= 3 ? { background: '#94a3b8' } : undefined}>{i + 1}</span>
                <span style={{ flex: 1, fontWeight: 700 }}>{s.state}</span>
                <span className="stat-pill stat-pill-red">Fail: {s.total > 0 ? Math.round(s.fail / s.total * 100) : 0}%</span>
                <span className="stat-pill stat-pill-orange">Frustration: {s.avg_frustration}</span>
              </div>
            ))}
          </div>

          {/* Insights */}
          <div className="card card-purple">
            <h2><span className="card-icon">✨</span><span className="card-label">Cross-Tester Insights</span></h2>
            <div className="insights">{insights}</div>
          </div>
        </>
      )}
    </div>
  );
}
