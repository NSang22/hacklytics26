import { useState, useEffect, useRef } from 'react'

// ─── Fake Data ────────────────────────────────────────────────────────────────

const DFA_STATES = [
  { id: 'goomba',    label: 'First Goomba',     start: 0,  end: 8,  intended: 'Calm',     intendedScore: 0.2, range: [0.0, 0.35] },
  { id: 'blocks',    label: 'Block Discovery',   start: 8,  end: 20, intended: 'Curious',  intendedScore: 0.7, range: [0.55, 0.85] },
  { id: 'pipes',     label: 'First Pipes',       start: 20, end: 35, intended: 'Tense',    intendedScore: 0.6, range: [0.45, 0.75] },
  { id: 'pit',       label: 'First Pit',         start: 35, end: 45, intended: 'Surprised', intendedScore: 0.65, range: [0.5, 0.8] },
  { id: 'midlevel',  label: 'Mid-Level',         start: 45, end: 60, intended: 'Engaged',  intendedScore: 0.7, range: [0.55, 0.85] },
  { id: 'stairs',    label: 'Endgame Stairs',    start: 60, end: 72, intended: 'Satisfied', intendedScore: 0.8, range: [0.65, 1.0] },
]

const STATE_COLORS = {
  goomba:   '#3b82f6',
  blocks:   '#8b5cf6',
  pipes:    '#f59e0b',
  pit:      '#ef4444',
  midlevel: '#f97316',
  stairs:   '#22c55e',
}

// Generate realistic per-second emotion data for 72 seconds
function generateTimeline() {
  const rows = []
  for (let t = 0; t < 72; t++) {
    const state = DFA_STATES.find(s => t >= s.start && t < s.end) || DFA_STATES[5]
    const noise = () => (Math.random() - 0.5) * 0.12

    let frustration, confusion, delight, boredom
    switch (state.id) {
      case 'goomba':
        frustration = 0.12 + noise(); confusion = 0.15 + noise(); delight = 0.35 + noise(); boredom = 0.25 + noise(); break
      case 'blocks':
        frustration = 0.18 + noise(); confusion = 0.28 + noise(); delight = 0.62 + noise(); boredom = 0.1 + noise(); break
      case 'pipes':
        frustration = 0.42 + noise(); confusion = 0.35 + noise(); delight = 0.28 + noise(); boredom = 0.08 + noise(); break
      case 'pit':
        frustration = 0.85 + noise() * 0.5; confusion = 0.55 + noise(); delight = 0.08 + noise(); boredom = 0.05 + noise(); break
      case 'midlevel':
        frustration = 0.58 + noise(); confusion = 0.42 + noise(); delight = 0.38 + noise(); boredom = 0.06 + noise(); break
      case 'stairs':
        frustration = 0.15 + noise(); confusion = 0.1 + noise(); delight = 0.78 + noise(); boredom = 0.12 + noise(); break
      default:
        frustration = 0.3; confusion = 0.3; delight = 0.3; boredom = 0.3
    }

    const hr = state.id === 'pit' ? 102 + Math.random() * 10
             : state.id === 'midlevel' ? 94 + Math.random() * 8
             : state.id === 'goomba' ? 72 + Math.random() * 4
             : 80 + Math.random() * 8

    rows.push({
      t,
      state: state.id,
      frustration: Math.max(0, Math.min(1, frustration)),
      confusion:   Math.max(0, Math.min(1, confusion)),
      delight:     Math.max(0, Math.min(1, delight)),
      boredom:     Math.max(0, Math.min(1, boredom)),
      hr: Math.round(hr),
    })
  }
  return rows
}

const TIMELINE = generateTimeline()

// Compute verdicts per state
function computeVerdicts() {
  return DFA_STATES.map(state => {
    const rows = TIMELINE.filter(r => r.state === state.id)
    const avg = key => rows.reduce((s, r) => s + r[key], 0) / rows.length

    const emotionMap = { Calm: 'delight', Curious: 'delight', Tense: 'frustration', Surprised: 'frustration', Engaged: 'delight', Satisfied: 'delight' }
    const key = emotionMap[state.intended] || 'delight'
    const actual = avg(key)
    const delta = Math.abs(actual - state.intendedScore)

    let verdict, color
    if (actual >= state.range[0] && actual <= state.range[1]) {
      verdict = 'PASS'; color = '#22c55e'
    } else if (delta < 0.25) {
      verdict = 'WARN'; color = '#f59e0b'
    } else {
      verdict = 'FAIL'; color = '#ef4444'
    }

    return { ...state, actual: Math.round(actual * 100) / 100, delta: Math.round(delta * 100) / 100, verdict, color, avgFrustration: avg('frustration'), avgDelight: avg('delight') }
  })
}

const VERDICTS = computeVerdicts()
const HEALTH_SCORE = Math.round((VERDICTS.filter(v => v.verdict === 'PASS').length / VERDICTS.length) * 100)

// Cross-tester data (5 testers)
const TESTERS = ['Tester A', 'Tester B', 'Tester C', 'Tester D', 'Tester E']
const TESTER_COLORS = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7']
const CROSS_TESTER = TESTERS.map((name, ti) => {
  const offset = (Math.random() - 0.5) * 0.15
  return {
    name,
    color: TESTER_COLORS[ti],
    data: TIMELINE.map(r => ({ t: r.t, frustration: Math.max(0, Math.min(1, r.frustration + offset + (Math.random() - 0.5) * 0.08)) }))
  }
})

// ─── Sub-components ───────────────────────────────────────────────────────────

function EmotionTimeline({ timeline }) {
  const canvasRef = useRef(null)
  const [hover, setHover] = useState(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width
    const H = canvas.height
    const PAD = { top: 16, bottom: 24, left: 8, right: 8 }
    const plotW = W - PAD.left - PAD.right
    const plotH = H - PAD.top - PAD.bottom
    const maxT = timeline[timeline.length - 1].t + 1

    ctx.clearRect(0, 0, W, H)

    // DFA state background bands
    DFA_STATES.forEach(state => {
      const x1 = PAD.left + (state.start / maxT) * plotW
      const x2 = PAD.left + (state.end / maxT) * plotW
      ctx.fillStyle = STATE_COLORS[state.id] + '18'
      ctx.fillRect(x1, PAD.top, x2 - x1, plotH)
      // State label
      ctx.fillStyle = STATE_COLORS[state.id] + 'cc'
      ctx.font = '9px monospace'
      ctx.fillText(state.label, x1 + 4, PAD.top + 11)
    })

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.05)'
    ctx.lineWidth = 1
    for (let y = 0; y <= 4; y++) {
      const yy = PAD.top + (y / 4) * plotH
      ctx.beginPath(); ctx.moveTo(PAD.left, yy); ctx.lineTo(PAD.left + plotW, yy); ctx.stroke()
    }

    // Emotion lines
    const lines = [
      { key: 'frustration', color: '#ef4444', label: 'Frustration' },
      { key: 'confusion',   color: '#f97316', label: 'Confusion' },
      { key: 'delight',     color: '#22c55e', label: 'Delight' },
      { key: 'boredom',     color: '#6366f1', label: 'Boredom' },
    ]

    lines.forEach(({ key, color }) => {
      ctx.beginPath()
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.shadowColor = color
      ctx.shadowBlur = 4
      timeline.forEach((row, i) => {
        const x = PAD.left + (row.t / maxT) * plotW
        const y = PAD.top + (1 - row[key]) * plotH
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      })
      ctx.stroke()
      ctx.shadowBlur = 0
    })

    // Hover line
    if (hover !== null) {
      const x = PAD.left + (hover / maxT) * plotW
      ctx.strokeStyle = 'rgba(255,255,255,0.3)'
      ctx.lineWidth = 1
      ctx.setLineDash([4, 4])
      ctx.beginPath(); ctx.moveTo(x, PAD.top); ctx.lineTo(x, PAD.top + plotH); ctx.stroke()
      ctx.setLineDash([])
    }
  }, [timeline, hover])

  const handleMouseMove = (e) => {
    const rect = canvasRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const pct = x / rect.width
    const t = Math.round(pct * 72)
    setHover(Math.max(0, Math.min(71, t)))
  }

  const hoverRow = hover !== null ? timeline[Math.min(hover, timeline.length - 1)] : null

  return (
    <div className="relative">
      <canvas
        ref={canvasRef}
        width={900}
        height={180}
        className="w-full h-auto cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHover(null)}
        style={{ background: 'transparent' }}
      />
      {hoverRow && (
        <div className="absolute top-2 right-2 bg-black/80 border border-white/10 rounded-lg px-3 py-2 text-xs font-mono pointer-events-none">
          <div className="text-white/50 mb-1">t = {hoverRow.t}s · {DFA_STATES.find(s => s.id === hoverRow.state)?.label}</div>
          <div className="text-red-400">Frustration {hoverRow.frustration.toFixed(2)}</div>
          <div className="text-orange-400">Confusion {hoverRow.confusion.toFixed(2)}</div>
          <div className="text-green-400">Delight {hoverRow.delight.toFixed(2)}</div>
          <div className="text-indigo-400">Boredom {hoverRow.boredom.toFixed(2)}</div>
          <div className="text-white/60 mt-1">HR {hoverRow.hr} bpm</div>
        </div>
      )}
      {/* Legend */}
      <div className="flex gap-4 mt-2 px-2">
        {[['#ef4444','Frustration'],['#f97316','Confusion'],['#22c55e','Delight'],['#6366f1','Boredom']].map(([c,l]) => (
          <div key={l} className="flex items-center gap-1.5">
            <div className="w-3 h-0.5 rounded" style={{ background: c }} />
            <span className="text-[10px] text-white/40 font-mono">{l}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function CrossTesterChart({ data }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width, H = canvas.height
    const PAD = { top: 12, bottom: 20, left: 8, right: 8 }
    const plotW = W - PAD.left - PAD.right
    const plotH = H - PAD.top - PAD.bottom
    const maxT = 72

    ctx.clearRect(0, 0, W, H)

    // State bands
    DFA_STATES.forEach(state => {
      const x1 = PAD.left + (state.start / maxT) * plotW
      const x2 = PAD.left + (state.end / maxT) * plotW
      ctx.fillStyle = STATE_COLORS[state.id] + '12'
      ctx.fillRect(x1, PAD.top, x2 - x1, plotH)
    })

    // Each tester's frustration line
    data.forEach(({ data: pts, color }) => {
      ctx.beginPath()
      ctx.strokeStyle = color + 'cc'
      ctx.lineWidth = 1.5
      pts.forEach((p, i) => {
        const x = PAD.left + (p.t / maxT) * plotW
        const y = PAD.top + (1 - p.frustration) * plotH
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      })
      ctx.stroke()
    })
  }, [data])

  return (
    <div>
      <canvas ref={canvasRef} width={900} height={140} className="w-full h-auto" style={{ background: 'transparent' }} />
      <div className="flex gap-4 mt-2 px-2">
        {data.map(({ name, color }) => (
          <div key={name} className="flex items-center gap-1.5">
            <div className="w-3 h-0.5 rounded" style={{ background: color }} />
            <span className="text-[10px] text-white/40 font-mono">{name}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function HealthRing({ score }) {
  const r = 54, cx = 70, cy = 70
  const circ = 2 * Math.PI * r
  const filled = (score / 100) * circ

  const color = score >= 70 ? '#22c55e' : score >= 45 ? '#f59e0b' : '#ef4444'

  return (
    <div className="flex flex-col items-center justify-center">
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10" />
        <circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circ}`}
          strokeDashoffset={circ / 4}
          style={{ filter: `drop-shadow(0 0 8px ${color})`, transition: 'stroke-dasharray 1s ease' }}
        />
        <text x={cx} y={cy - 6} textAnchor="middle" fill="white" fontSize="26" fontWeight="bold" fontFamily="monospace">{score}</text>
        <text x={cx} y={cy + 14} textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize="10" fontFamily="monospace">/ 100</text>
      </svg>
      <p className="text-xs text-white/40 font-mono mt-1 tracking-widest uppercase">Health Score</p>
    </div>
  )
}

function VerdictCard({ verdict }) {
  const bg = 'rgba(255,255,255,0.06)'

  return (
    <div
      className="rounded-3xl p-5 border border-white/15 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)] transition-all hover:scale-[1.02]"
      style={{ background: bg, borderColor: verdict.color + '35' }}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-0.5">{verdict.label}</div>
          <div className="text-sm text-white/70">Intended: <span className="text-white font-medium">{verdict.intended}</span></div>
        </div>
        <div
          className="text-xs font-black font-mono px-2 py-1 rounded-lg tracking-widest"
          style={{ background: verdict.color + '25', color: verdict.color }}
        >
          {verdict.verdict}
        </div>
      </div>

      {/* Score bar */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-[10px] font-mono text-white/30">
          <span>Actual</span>
          <span>{verdict.actual}</span>
        </div>
        <div className="h-1.5 rounded-full bg-white/5 relative overflow-hidden">
          {/* Intended range band */}
          <div
            className="absolute h-full rounded-full opacity-20"
            style={{ left: `${verdict.range[0] * 100}%`, width: `${(verdict.range[1] - verdict.range[0]) * 100}%`, background: verdict.color }}
          />
          {/* Actual score marker */}
          <div
            className="absolute h-full w-0.5 rounded-full"
            style={{ left: `${verdict.actual * 100}%`, background: verdict.color, boxShadow: `0 0 6px ${verdict.color}` }}
          />
        </div>
        <div className="flex justify-between text-[10px] font-mono text-white/20">
          <span>Range {verdict.range[0]}–{verdict.range[1]}</span>
          <span>Δ {verdict.delta}</span>
        </div>
      </div>
    </div>
  )
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('session')
  const [mounted, setMounted] = useState(false)

  useEffect(() => { setTimeout(() => setMounted(true), 100) }, [])

  const painPoints = [...VERDICTS].sort((a, b) => b.delta - a.delta)

  return (
    <div
      className="min-h-screen text-white"
      style={{
        backgroundImage: "url('/background2.jpg')",
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundAttachment: 'fixed',
      }}
    >
      {/* Dark overlay */}
      <div className="fixed inset-0 bg-gradient-to-t from-black/60 to-black/95 pointer-events-none" />

      {/* Pink ambient glows */}
      <div className="fixed -top-40 -left-40 w-[600px] h-[600px] bg-[#ec4899]/10 blur-[160px] rounded-full pointer-events-none" />
      <div className="fixed -bottom-40 -right-40 w-[500px] h-[500px] bg-[#ec4899]/8 blur-[140px] rounded-full pointer-events-none" />

      {/* Unified session header — no fill, floats on the page background */}
      <div className="relative z-10 max-w-5xl mx-auto px-6 pt-6 pb-2">
        {/* Status row */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-[#ec4899] animate-pulse shadow-[0_0_8px_rgba(236,72,153,0.9)]" />
              <span className="text-xs text-white/70 tracking-widest uppercase font-mono">Demo Session</span>
            </div>
            <span className="text-white/70 font-mono text-xs select-none">·</span>
            <span className="text-xs text-white/70 font-mono">SMB1-1 · Judge Demo · ID: aura_8f2d</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-white/70 font-mono">72s recorded</span>
            <div
              className="px-3 py-1 rounded-full text-[10px] font-bold tracking-widest uppercase"
              style={{ background: 'rgba(236,72,153,0.10)', border: '1px solid rgba(236,72,153,0.25)', color: 'rgba(236,72,153,0.90)' }}
            >
              Processing Complete
            </div>
          </div>
        </div>

        {/* Tab pills — inline, no background strip */}
        <div className="flex items-center gap-2">
          {[['session', 'Session Review'], ['cross', 'Cross-Tester'], ['sphinx', 'Sphinx AI']].map(([id, label]) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className="px-5 py-2 text-xs tracking-wider font-semibold transition-all duration-200 rounded-full"
              style={{
                color: activeTab === id ? 'white' : 'rgba(255,255,255,0.30)',
                background: activeTab === id ? 'rgba(236,72,153,0.18)' : 'rgba(255,255,255,0.04)',
                border: activeTab === id ? '1px solid rgba(236,72,153,0.40)' : '1px solid rgba(255,255,255,0.07)',
                boxShadow: activeTab === id ? '0 0 18px rgba(236,72,153,0.20)' : 'none',
              }}
            >
              {label}
            </button>
          ))}

          {/* Subtle divider + stat inline */}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[10px] text-white/70 font-mono tracking-widest uppercase">Health</span>
            <span
              className="text-xs font-bold font-mono"
              style={{ color: HEALTH_SCORE >= 70 ? '#22c55e' : HEALTH_SCORE >= 45 ? '#f59e0b' : '#ef4444' }}
            >
              {HEALTH_SCORE}
            </span>
            <span className="text-[10px] text-white/70 font-mono">/ 100</span>
          </div>
        </div>

        {/* Thin accent line below tabs */}
        <div className="mt-4 h-px w-full" style={{ background: 'linear-gradient(90deg, rgba(236,72,153,0.30) 0%, rgba(255,255,255,0.05) 60%, transparent 100%)' }} />
      </div>

      <main className="relative z-10 px-6 py-6 max-w-5xl mx-auto space-y-6">

        {/* ── SESSION REVIEW ── */}
        {activeTab === 'session' && (
          <div className={`space-y-5 transition-opacity duration-500 ${mounted ? 'opacity-100' : 'opacity-0'}`}>

            {/* Top row: Health score + quick stats */}
            <div className="grid grid-cols-[auto_1fr] gap-5">
              <div className="rounded-3xl border border-white/15 p-6 flex flex-col items-center justify-center backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.5)]" style={{ background: 'rgba(255,255,255,0.06)', minWidth: 200 }}>
                <HealthRing score={HEALTH_SCORE} />
                <div className="mt-4 text-center space-y-1">
                  <div className="text-[10px] text-white/30 uppercase tracking-widest">Breakdown</div>
                  <div className="flex gap-3 justify-center text-xs">
                    <span className="text-green-400">{VERDICTS.filter(v=>v.verdict==='PASS').length} PASS</span>
                    <span className="text-yellow-400">{VERDICTS.filter(v=>v.verdict==='WARN').length} WARN</span>
                    <span className="text-red-400">{VERDICTS.filter(v=>v.verdict==='FAIL').length} FAIL</span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                {[
                  { label: 'Peak Frustration', value: '0.91', sub: 'at t=38s · First Pit', color: '#ef4444' },
                  { label: 'Avg Heart Rate', value: '87 bpm', sub: 'Peak 108 at pit death', color: '#f97316' },
                  { label: 'Worst Segment', value: 'First Pit', sub: 'Δ 0.52 from intent', color: '#ef4444' },
                ].map(s => (
                  <div key={s.label} className="rounded-3xl border border-white/15 p-5 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
                    <div className="text-[10px] text-white/30 uppercase tracking-widest mb-2">{s.label}</div>
                    <div className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</div>
                    <div className="text-[10px] text-white/30 mt-1">{s.sub}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Emotion timeline */}
            <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="font-eb-garamond text-2xl font-bold text-white">Emotion Timeline</h2>
                  <p className="text-[10px] text-white/30 mt-0.5">All 4 Presage streams · DFA states as bands · hover for details</p>
                </div>
              </div>
              <EmotionTimeline timeline={TIMELINE} />
            </div>

            {/* Verdict cards */}
            <div>
              <h2 className="font-eb-garamond text-2xl font-bold text-white mb-4">Per-State Verdicts — Intent vs. Reality</h2>
              <div className="grid grid-cols-3 gap-3">
                {VERDICTS.map(v => <VerdictCard key={v.id} verdict={v} />)}
              </div>
            </div>

            {/* Gemini insight */}
            <div className="rounded-3xl border border-[#ec4899]/25 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(236,72,153,0.1)]" style={{ background: 'rgba(236,72,153,0.07)' }}>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-5 h-5 rounded-md bg-pink-500/20 flex items-center justify-center">
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="#ec4899"><circle cx="5" cy="5" r="4"/></svg>
                </div>
                <span className="text-xs font-bold tracking-widest uppercase text-[#ec4899]">Gemini Insight</span>
              </div>
              <p className="text-sm text-white/60 leading-relaxed">
                The tester died twice at the <span className="text-white">First Pit</span> (t=38s, t=41s), producing frustration spikes of <span className="text-red-400">0.89</span> and <span className="text-red-400">0.91</span> respectively — significantly above the intended "tense but fair" range of 0.50–0.80. 
                Gemini detected no block-breaking behavior in the Block Discovery state, suggesting the tester missed the core mechanic before reaching the pit. 
                The <span className="text-white">Endgame Stairs</span> segment was the only state to produce a clean delight response (avg 0.81), consistent with design intent.
              </p>
              <div className="mt-3 pt-3 border-t border-white/5 text-[10px] text-white/20 font-mono">
                Analyzed via gemini-2.5-flash · 7 chunks · 2fps · State detection accuracy 94%
              </div>
            </div>
          </div>
        )}

        {/* ── CROSS-TESTER ── */}
        {activeTab === 'cross' && (
          <div className="space-y-5">

            <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <h2 className="font-eb-garamond text-2xl font-bold text-white mb-1">Frustration Overlay — All Testers</h2>
              <p className="text-[10px] text-white/30 mb-4">5 sessions · convergence at First Pit indicates systematic design failure</p>
              <CrossTesterChart data={CROSS_TESTER} />
            </div>

            {/* Pain points table */}
            <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <h2 className="font-eb-garamond text-2xl font-bold text-white mb-4">Pain Point Rankings</h2>
              <div className="space-y-2">
                {painPoints.map((v, i) => (
                  <div key={v.id} className="flex items-center gap-4 py-2.5 px-3 rounded-xl hover:bg-white/3 transition-colors">
                    <span className="text-white/20 text-xs w-4">{i + 1}</span>
                    <div className="flex-1">
                      <div className="text-sm text-white/80">{v.label}</div>
                      <div className="text-[10px] text-white/30 mt-0.5">Intended: {v.intended} · Actual avg frustration: {v.avgFrustration.toFixed(2)}</div>
                    </div>
                    <div className="w-32 h-1.5 rounded-full bg-white/5 overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${v.delta * 100}%`, background: v.color, boxShadow: `0 0 6px ${v.color}` }} />
                    </div>
                    <div className="text-xs font-bold w-10 text-right" style={{ color: v.color }}>Δ {v.delta}</div>
                    <div className="text-xs font-black px-2 py-1 rounded-lg w-14 text-center" style={{ background: v.color + '20', color: v.color }}>{v.verdict}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Per-state verdict breakdown table */}
            <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <h2 className="font-eb-garamond text-2xl font-bold text-white mb-4">Cross-Session Verdict Summary</h2>
              <div className="grid grid-cols-3 gap-3">
                {VERDICTS.map(v => (
                  <div key={v.id} className="flex items-center justify-between py-2 px-3 rounded-xl border border-white/5">
                    <span className="text-xs text-white/60">{v.label}</span>
                    <div className="flex gap-1.5 text-[10px] font-bold">
                      <span className="text-green-400">{v.verdict === 'PASS' ? '5/5' : v.verdict === 'WARN' ? '2/5' : '0/5'} P</span>
                      <span className="text-red-400">{v.verdict === 'FAIL' ? '5/5' : v.verdict === 'WARN' ? '3/5' : '0/5'} F</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── SPHINX ── */}
        {activeTab === 'sphinx' && (
          <div className="space-y-5">
            <div className="rounded-3xl border border-purple-400/20 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(168,85,247,0.08)]" style={{ background: 'rgba(168,85,247,0.07)' }}>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-1.5 h-1.5 rounded-full bg-purple-400 shadow-[0_0_6px_rgba(168,85,247,0.8)]" />
                <span className="text-xs font-bold tracking-widest uppercase text-purple-300">Sphinx AI</span>
                <span className="text-[10px] text-white/20 ml-1">Natural language · Snowflake + VectorAI</span>
              </div>

              <div className="relative">
                <input
                  type="text"
                  placeholder="Ask anything about your playtest data..."
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-white/20 outline-none focus:border-purple-500/50 pr-24"
                />
                <button className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1.5 rounded-lg text-xs font-bold text-white" style={{ background: 'rgba(168,85,247,0.4)' }}>
                  Run →
                </button>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {[
                  'Show average frustration per DFA state as a heatmap',
                  'Scatter: time delta vs confusion score per state',
                  'Find top 5 moments where frustration > 0.8 in First Pit',
                ].map(q => (
                  <button key={q} className="text-[10px] px-3 py-1.5 rounded-lg border border-white/10 text-white/40 hover:text-white hover:border-white/20 transition-all">
                    {q}
                  </button>
                ))}
              </div>
            </div>

            {/* Example output */}
            <div className="rounded-3xl border border-white/15 p-6 backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.4)]" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <div className="text-[10px] text-white/20 font-mono mb-3 uppercase tracking-widest">Example Output — Frustration Heatmap by State</div>
              <div className="grid grid-cols-6 gap-2">
                {VERDICTS.map(v => {
                  const intensity = v.avgFrustration
                  const bg = `rgba(239,68,68,${intensity * 0.8})`
                  return (
                    <div key={v.id} className="rounded-xl p-3 text-center" style={{ background: bg, border: '1px solid rgba(239,68,68,0.2)' }}>
                      <div className="text-[10px] text-white/70 leading-tight mb-1">{v.label}</div>
                      <div className="text-lg font-bold text-white">{v.avgFrustration.toFixed(2)}</div>
                    </div>
                  )
                })}
              </div>
              <div className="mt-3 text-[10px] text-white/20 font-mono">Generated by Sphinx · Query: "GROUP BY dfa_state, AVG(frustration)" · 0.12s</div>
            </div>
          </div>
        )}

      </main>
    </div>
  )
}