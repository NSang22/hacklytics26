import { useParams } from 'react-router-dom'

export default function AggregateAnalytics() {
  const { id } = useParams()

  return (
    <div>
      <h1>Aggregate Analytics — Project {id}</h1>

      <p style={{ color: '#888' }}>
        Cross-tester comparison charts, per-segment scores, pain-point rankings,
        and VectorAI similarity panels will be built here.
      </p>

      <div style={{
        border: '1px dashed #444',
        borderRadius: 8,
        padding: 24,
        textAlign: 'center',
        color: '#666',
        marginTop: 24,
      }}>
        <p>📊 Aggregate Recharts panels — coming next</p>
        <p>🔍 VectorAI tester clustering — coming next</p>
        <p>🤖 Gemini aggregate insights — coming next</p>
      </div>
    </div>
  )
}
