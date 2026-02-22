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
    <div
      className="min-h-screen text-white"
      style={{
        backgroundImage: "url('/background6.jpg')",
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundAttachment: 'fixed',
      }}
    >
      {/* Overlay */}
      <div className="fixed inset-0 bg-gradient-to-t from-black/60 to-black/90 pointer-events-none" />

      {/* Red-orange ambient glows */}
      <div className="fixed -top-40 -left-40 w-[600px] h-[600px] bg-[#f97316]/8 blur-[160px] rounded-full pointer-events-none" />
      <div className="fixed -bottom-40 -right-40 w-[500px] h-[500px] bg-[#ef4444]/6 blur-[140px] rounded-full pointer-events-none" />

      {/* Floating header */}
      <div className="relative z-10 max-w-4xl mx-auto px-6 pt-6 pb-2">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-2 h-2 rounded-full bg-[#f97316] animate-pulse shadow-[0_0_8px_rgba(249,115,22,0.9)]" />
          <span className="text-xs text-white/70 tracking-widest uppercase font-mono">Sphinx Explorer</span>
          <span className="text-white/70 font-mono text-xs select-none">·</span>
          <span className="text-xs text-white/70 font-mono">Ask your playtest data anything</span>
        </div>
        <div className="h-px w-full" style={{ background: 'linear-gradient(90deg, rgba(249,115,22,0.40) 0%, rgba(255,255,255,0.05) 60%, transparent 100%)' }} />
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-6 pb-12 space-y-5">

        {/* Query Card */}
        <div className="rounded-3xl border border-white/10 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.35)]" style={{ background: 'rgba(255,255,255,0.05)' }}>
          <div className="flex items-center gap-3 mb-1">
            <div className="w-1.5 h-1.5 rounded-full bg-[#f97316] shadow-[0_0_6px_rgba(249,115,22,0.8)]" />
            <span className="text-xs font-bold tracking-widest uppercase text-[#fdba74]">Natural Language Query</span>
          </div>
          <p className="text-[11px] text-white/70 mb-5 font-mono">Ask questions about your playtest data in plain English</p>

          <div className="space-y-3">
            <input
              value={projectId}
              onChange={e => setProjectId(e.target.value)}
              placeholder="Project ID…"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-[#f97316]/40 transition-colors"
            />
            <div className="flex items-center gap-3">
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && submit()}
                placeholder="e.g. Show frustration heatmap by DFA state…"
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-[#f97316]/40 transition-colors"
              />
              <button
                onClick={() => submit()}
                disabled={loading}
                className="px-6 py-2.5 rounded-full text-xs font-bold tracking-widest uppercase transition-all hover:scale-[1.03] disabled:opacity-50 shrink-0"
                style={{ background: 'rgba(249,115,22,0.16)', border: '1px solid rgba(249,115,22,0.35)', color: '#fdba74' }}
              >
                {loading ? '⏳ Querying…' : '🔮 Ask Sphinx'}
              </button>
            </div>
          </div>
        </div>

        {/* Example Queries */}
        <div className="rounded-3xl border border-white/10 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.35)]" style={{ background: 'rgba(255,255,255,0.05)' }}>
          <div className="flex items-center gap-3 mb-4">
            <div className="w-1.5 h-1.5 rounded-full bg-[#f97316] shadow-[0_0_6px_rgba(249,115,22,0.8)]" />
            <span className="text-xs font-bold tracking-widest uppercase text-[#fdba74]">Example Queries</span>
          </div>
          <div className="flex flex-col gap-2">
            {EXAMPLE_QUERIES.map((q, i) => (
              <button
                key={i}
                onClick={() => submit(q)}
                className="text-left px-4 py-3 rounded-2xl text-xs text-white/50 hover:text-white/80 transition-all hover:scale-[1.01]"
                style={{ background: 'rgba(249,115,22,0.06)', border: '1px solid rgba(249,115,22,0.15)' }}
              >
                <span className="text-[#fdba74]/60 font-mono mr-2">{String(i + 1).padStart(2, '0')}.</span>
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Result */}
        {result && (
          <div
            className="rounded-3xl border p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(249,115,22,0.10)]"
            style={{
              background: result.error ? 'rgba(239,68,68,0.07)' : 'rgba(249,115,22,0.07)',
              borderColor: result.error ? 'rgba(239,68,68,0.25)' : 'rgba(249,115,22,0.25)',
            }}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-2 h-2 rounded-full bg-[#f97316] shadow-[0_0_6px_rgba(249,115,22,0.8)]" />
              <span className="text-xs font-bold tracking-widest uppercase text-[#fdba74]">
                {result.error ? 'Error' : 'Sphinx Answer'}
              </span>
            </div>
            {result.error ? (
              <p className="text-sm text-red-400 font-mono">❌ {result.error}</p>
            ) : (
              <>
                <p className="text-sm text-white/70 leading-relaxed mb-5">{result.answer}</p>
                <div className="flex items-center gap-3">
                  <span
                    className="text-[10px] font-black font-mono px-3 py-1.5 rounded-full"
                    style={{ background: 'rgba(34,197,94,0.15)', color: '#86efac', border: '1px solid rgba(34,197,94,0.25)' }}
                  >
                    Confidence {((result.confidence ?? 0) * 100).toFixed(0)}%
                  </span>
                  {result.sources?.length > 0 && (
                    <span
                      className="text-[10px] font-mono px-3 py-1.5 rounded-full"
                      style={{ background: 'rgba(249,115,22,0.15)', color: '#fdba74', border: '1px solid rgba(249,115,22,0.25)' }}
                    >
                      Sources: {result.sources.join(', ')}
                    </span>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {!result && (
          <div className="flex flex-col items-center py-16 gap-3">
            <span className="text-6xl opacity-15">🔮</span>
            <p className="text-xs text-white/15 font-mono tracking-widest uppercase">Enter a project ID and ask Sphinx anything</p>
          </div>
        )}

      </div>
    </div>
  );
}
