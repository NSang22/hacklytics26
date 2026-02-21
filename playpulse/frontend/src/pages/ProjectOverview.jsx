import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function ProjectOverview() {
  const { id } = useParams()
  const [project, setProject] = useState(null)
  const [sessionName, setSessionName] = useState('')

  useEffect(() => {
    fetch(`${API}/v1/projects/${id}`).then(r => r.json()).then(setProject)
  }, [id])

  const createSession = async () => {
    const res = await fetch(`${API}/v1/projects/${id}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: id, tester_name: sessionName || 'Anonymous' }),
    })
    const data = await res.json()
    // Refresh project to see new session
    const updated = await fetch(`${API}/v1/projects/${id}`).then(r => r.json())
    setProject(updated)
    setSessionName('')
    alert(`Session created!\nID: ${data.session_id}\nGame URL: ${data.join_url}`)
  }

  if (!project) return <p>Loading…</p>

  return (
    <div>
      <h1>{project.name}</h1>
      <p><strong>Project ID:</strong> {project.id}</p>
      <p><strong>API Key:</strong> <code>{project.api_key}</code></p>

      <h2>Segments</h2>
      <ul>
        {project.segments.map((s, i) => (
          <li key={i}>{s.order}. {s.name} — <em>{s.intended_emotion}</em></li>
        ))}
      </ul>

      <h2>Sessions</h2>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          placeholder="Tester name"
          value={sessionName}
          onChange={e => setSessionName(e.target.value)}
        />
        <button onClick={createSession}>+ New Session</button>
      </div>

      {project.sessions.length === 0 ? (
        <p>No sessions yet.</p>
      ) : (
        <ul>
          {project.sessions.map(sid => (
            <li key={sid}>
              {sid} —{' '}
              <Link to={`/sessions/${sid}/live`}>Live</Link>{' | '}
              <Link to={`/sessions/${sid}/review`}>Review</Link>
            </li>
          ))}
        </ul>
      )}

      <h2>Aggregate</h2>
      <Link to={`/projects/${id}/aggregate`}>View Cross-Tester Analytics →</Link>
    </div>
  )
}
