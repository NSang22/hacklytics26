import { useState } from 'react';

const API = 'http://localhost:8000';

const EXAMPLE_QUERIES = [
  'Group by DFA state. Show average frustration and heart rate per state as a color-coded heatmap.',
  'Scatter plot: time delta between optimal and actual playthrough on X-axis, average confusion score on Y-axis.',
  'Find top 5 moments in puzzle_room where frustration exceeded 0.8 from VectorAI. Return session ID, tester name, and exact timestamps.',
];

export default function SphinxExplorer() {
  const [projectId, setProjectId] = useState('');
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const submit = async (q) => {
    const question = q || query;
    if (!projectId || !question) return;
    setLoading(true);
    setQuery(question);
    try {
      const resp = await fetch(`${API}/v1/projects/${projectId}/sphinx-query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
      setResult(await resp.json());
    } catch (e) { setResult({ error: e.message }); }
    setLoading(false);
  };

  return (
    <div className="pp-wrap">
      <div className="content">
        <h1 className="page-title">🔮 Sphinx Explorer</h1>
        <p className="page-subtitle"><span className="dot dot-purple" /> Ask questions about your playtest data in plain English</p>

        <div className="card card-purple">
          <h2><span className="card-icon">💬</span><span className="card-label">Natural Language Query</span></h2>
          <div className="row mb">
            <input value={projectId} onChange={e => setProjectId(e.target.value)} placeholder="Project ID" style={{ maxWidth: 240 }} />
          </div>
          <div className="row">
            <input
              value={query} onChange={e => setQuery(e.target.value)}
              placeholder="e.g. Show frustration heatmap by DFA state"
              style={{ flex: 1 }}
              onKeyDown={e => e.key === 'Enter' && submit()}
            />
            <button onClick={() => submit()} disabled={loading}>{loading ? '⏳ Querying...' : '🔮 Ask Sphinx'}</button>
          </div>
        </div>

        <div className="card card-teal">
          <h2><span className="card-icon">💡</span><span className="card-label">Example Queries</span></h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {EXAMPLE_QUERIES.map((q, i) => (
              <button key={i} className="query-chip" onClick={() => submit(q)}>{q}</button>
            ))}
          </div>
        </div>

        {result && (
          <div className="card card-glow">
            <h2><span className="card-icon">🎯</span><span className="card-label">Result</span></h2>
            {result.error ? (
              <p style={{ color: '#ef4444', fontWeight: 700 }}>❌ {result.error}</p>
            ) : (
              <>
                <div className="insights" style={{ marginBottom: 14 }}>{result.answer}</div>
                <div className="row text-sm">
                  <span className="stat-pill stat-pill-green">Confidence: {((result.confidence ?? 0) * 100).toFixed(0)}%</span>
                  {result.sources?.length > 0 && <span className="stat-pill stat-pill-purple">Sources: {result.sources.join(', ')}</span>}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
