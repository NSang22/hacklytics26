import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

export default function LiveMonitor() {
  const { id } = useParams()
  const [events, setEvents] = useState([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/v1/dashboard-stream/${id}`)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data)
        setEvents(prev => [...prev.slice(-199), data]) // keep last 200
      } catch { /* ignore non-JSON */ }
    }

    return () => ws.close()
  }, [id])

  return (
    <div>
      <h1>Live Monitor — Session {id}</h1>
      <p>Status: {connected ? '🟢 Connected' : '🔴 Disconnected'}</p>

      <h2>Live Event Feed</h2>
      <div style={{
        maxHeight: 500,
        overflowY: 'auto',
        background: '#111',
        color: '#0f0',
        fontFamily: 'monospace',
        fontSize: 13,
        padding: 12,
        borderRadius: 6,
      }}>
        {events.length === 0 && <p style={{ color: '#555' }}>Waiting for events…</p>}
        {events.map((ev, i) => (
          <div key={i} style={{ marginBottom: 4 }}>
            <span style={{ color: '#888' }}>[{(ev.timestamp ?? 0).toFixed(2)}s]</span>{' '}
            <span style={{ color: ev.type === 'emotion' ? '#ff9800' : '#4fc3f7' }}>
              {ev.type === 'emotion' ? 'EMOTION' : ev.event_type || ev.type}
            </span>{' '}
            {ev.event_name || ''}{' '}
            <span style={{ color: '#666' }}>{JSON.stringify(ev.payload || ev.emotions || '')}</span>
          </div>
        ))}
      </div>

      <p style={{ marginTop: 12, color: '#888', fontSize: 12 }}>
        Charts (Recharts) will be layered in here next.
      </p>
    </div>
  )
}
