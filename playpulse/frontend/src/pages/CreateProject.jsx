import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function CreateProject() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [segments, setSegments] = useState([
    { name: 'tutorial', intended_emotion: 'calm', order: 1 },
    { name: 'puzzle', intended_emotion: 'curious', order: 2 },
    { name: 'surprise', intended_emotion: 'surprise', order: 3 },
    { name: 'gauntlet', intended_emotion: 'tense', order: 4 },
    { name: 'victory', intended_emotion: 'satisfied', order: 5 },
  ])
  const [result, setResult] = useState(null)

  const handleCreate = async () => {
    const res = await fetch(`${API}/v1/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, segments }),
    })
    const data = await res.json()
    setResult(data)
  }

  return (
    <div>
      <h1>Create New Project</h1>

      <label>
        Project Name:
        <input value={name} onChange={e => setName(e.target.value)} placeholder="My Game" />
      </label>

      <h3>Segments</h3>
      <table>
        <thead>
          <tr><th>#</th><th>Name</th><th>Intended Emotion</th></tr>
        </thead>
        <tbody>
          {segments.map((s, i) => (
            <tr key={i}>
              <td>{s.order}</td>
              <td>{s.name}</td>
              <td>{s.intended_emotion}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <button onClick={handleCreate} disabled={!name}>Create Project</button>

      {result && (
        <div className="result-card">
          <p><strong>Project ID:</strong> {result.project_id}</p>
          <p><strong>API Key:</strong> <code>{result.api_key}</code></p>
          <button onClick={() => navigate(`/projects/${result.project_id}`)}>
            Go to Project →
          </button>
        </div>
      )}
    </div>
  )
}
