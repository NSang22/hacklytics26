import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function SessionReview() {
  const { id } = useParams()
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API}/v1/sessions/${id}/analysis`)
      .then(r => r.json())
      .then(data => { setAnalysis(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [id])

  if (loading) return <p>Loading analysis…</p>
  if (!analysis) return <p>No analysis data available.</p>

  return (
    <div>
      <h1>Session Review — {id}</h1>

      <h2>Summary Stats</h2>
      <ul>
        {Object.entries(analysis.summary_stats || {}).map(([k, v]) => (
          <li key={k}><strong>{k}:</strong> {v}</li>
        ))}
      </ul>

      <h2>Intent vs Reality</h2>
      <table>
        <thead>
          <tr>
            <th>Segment</th>
            <th>Intended</th>
            <th>Actual Dominant</th>
            <th>Intent Met?</th>
            <th>Deviation</th>
          </tr>
        </thead>
        <tbody>
          {(analysis.intent_comparison || []).map((row, i) => (
            <tr key={i}>
              <td>{row.segment}</td>
              <td>{row.intended}</td>
              <td>{row.actual_dominant ?? '—'}</td>
              <td>{row.intent_met == null ? '—' : row.intent_met ? '✅' : '❌'}</td>
              <td>{row.deviation_score ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Fused Timeline ({(analysis.fused_timeline || []).length} entries)</h2>
      <div style={{
        maxHeight: 400,
        overflowY: 'auto',
        background: '#111',
        color: '#ccc',
        fontFamily: 'monospace',
        fontSize: 12,
        padding: 12,
        borderRadius: 6,
      }}>
        {(analysis.fused_timeline || []).map((entry, i) => (
          <div key={i} style={{ marginBottom: 4 }}>
            <span style={{ color: '#888' }}>[{entry.timestamp.toFixed(2)}s]</span>{' '}
            {entry.event?.event_type} — {entry.event?.event_name}{' '}
            {entry.contextualized && <em style={{ color: '#ff9800' }}>({entry.contextualized})</em>}
          </div>
        ))}
      </div>

      <p style={{ marginTop: 12, color: '#888', fontSize: 12 }}>
        Emotion heatmap, Gemini insights, and ElevenLabs audio player will be added here.
      </p>
    </div>
  )
}
