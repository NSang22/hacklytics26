import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { PiStarFourBold } from 'react-icons/pi'

const FAQ_DATA = [
  {
    q: 'What input data does CrashOut need?',
    a: 'Three streams: gameplay video (screen capture at 30 FPS, chunked into 10-second segments), webcam footage processed through the Presage SDK for facial affect (frustration, confusion, delight, boredom at 10 Hz), and optionally Apple Watch data for heart rate and HRV at 1 Hz. You also provide your intended emotional arc per game state before the session.',
  },
  {
    q: 'How does it detect game states without instrumenting my game?',
    a: 'CrashOut uses Gemini Vision to watch your gameplay video chunks and extract DFA (Deterministic Finite Automaton) state transitions in real time. You define the states and visual cues up front — like "First Pit: gap in ground, sky visible below" — and Gemini matches frames to those states. No game SDK or code changes required.',
  },
  {
    q: 'What is a "Playtest Health Score"?',
    a: 'It\'s a single 0–1 number summarizing how well the actual player experience matched your design intent. It\'s based on the intent delta — the gap between the emotion you wanted players to feel in each state and what they actually felt. Green (< 0.2 delta) means on-target, yellow (0.2–0.4) is worth watching, and red (> 0.4) flags a broken mechanic.',
  },
  {
    q: 'What are PASS / WARN / FAIL verdicts?',
    a: 'For each DFA state, CrashOut compares the intended emotion and acceptable range you defined against the actual measured affect. If the dominant emotion matches intent and falls within range, it\'s PASS. If it\'s borderline, it\'s WARN. If the actual emotion is far off — like players being frustrated when you intended delight — it\'s FAIL. This turns subjective "does our game feel right?" into objective, researchable data.',
  },
  {
    q: 'What is Sphinx AI?',
    a: 'It\'s a natural-language analytics copilot. Ask questions like "Group by DFA state — show average frustration and heart rate per state as a color-coded heatmap" and Sphinx queries Snowflake and VectorAI behind the scenes, then returns visualizations and data. No SQL knowledge needed.',
  },
  {
    q: 'Can I compare multiple testers?',
    a: 'Yes. The Cross-Tester Aggregate view compares health scores, per-state verdicts, and pain point rankings across every tester in a project. It also shows a health score trend line so you can track whether design changes across playtest iterations are actually improving the experience.',
  },
  {
    q: 'What happens if the Apple Watch isn\'t available?',
    a: 'CrashOut degrades gracefully. The core pipeline — Gemini Vision DFA extraction plus Presage facial affect — works without any wearable. Apple Watch HR/HRV is an additive physiological signal; if it\'s missing, emotion + video data still produce full verdicts and health scores.',
  },
  {
    q: 'How is this different from just watching playtest recordings?',
    a: 'Watching recordings tells you what happened — CrashOut tells you what players felt and whether it matched what you intended. A tester might complete a level fine but be deeply confused the whole time. That gap is invisible on video but immediately visible in the intent delta. Multiply that across 50 testers and you get statistical certainty about design problems.',
  },
]

function FaqItem({ q, a, index }) {
  const [open, setOpen] = useState(false)
  const contentRef = useRef(null)
  const itemRef = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = itemRef.current
    if (!el) return
    const ob = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); ob.disconnect() } },
      { threshold: 0.1 }
    )
    ob.observe(el)
    return () => ob.disconnect()
  }, [])

  return (
    <div
      ref={itemRef}
      className="border-b border-white/8 transition-all duration-700"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(20px)',
        transitionDelay: `${index * 60}ms`,
      }}
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between py-6 text-left group cursor-pointer"
      >
        <span className="text-white font-semibold text-base md:text-lg pr-8 group-hover:text-white transition-colors">
          {q}
        </span>
        <span
          className="text-white text-2xl transition-transform duration-300 shrink-0"
          style={{ transform: open ? 'rotate(45deg)' : 'rotate(0)' }}
        >
          +
        </span>
      </button>
      <div
        className="overflow-hidden transition-all duration-400 ease-in-out"
        style={{ maxHeight: open ? (contentRef.current?.scrollHeight ?? 500) + 'px' : '0px' }}
      >
        <p ref={contentRef} className="text-white text-sm leading-relaxed pb-6 pr-12">
          {a}
        </p>
      </div>
    </div>
  )
}

export default function FAQ() {
  const navigate = useNavigate()

  return (
    <section id="faq" className="relative z-10 w-full max-w-4xl mx-auto px-6 pt-40 pb-32">

      {/* Section heading */}
      <div className="text-center mb-16">
        <p className="text-white text-xs font-bold tracking-[0.3em] uppercase mb-4">Questions</p>
        <h2 className="font-eb-garamond text-white text-5xl md:text-7xl font-bold tracking-tight leading-[1.05]">
          FAQ
        </h2>
      </div>

      {/* FAQ list */}
      <div>
        {FAQ_DATA.map((item, i) => (
          <FaqItem key={i} q={item.q} a={item.a} index={i} />
        ))}
      </div>

      {/* Bottom CTA */}
      <div className="mt-20 text-center">
        <p className="text-white text-sm mb-4">Ready to find out what players really feel?</p>
        <button
          onClick={() => navigate('/dashboard/setup')}
          className="group hover:cursor-pointer relative inline-flex items-center gap-4 overflow-hidden rounded-2xl bg-[#196eff] px-10 py-5 font-semibold transition-all duration-300
                      shadow-[0_12px_30px_rgba(0,0,0,0.35)]
                      hover:scale-[1.04] hover:shadow-[0_18px_45px_rgba(0,0,0,0.45)]
                      active:scale-[0.98]"
        >
          <span className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-b from-white/25 to-transparent opacity-70" />
          <span className="pointer-events-none absolute inset-0 rounded-2xl shadow-[inset_0_-8px_14px_rgba(0,0,0,0.25)]" />
          <span className="pointer-events-none absolute inset-0 rounded-2xl">
            <span className="absolute inset-y-0 -left-1/3 w-full shimmer bg-gradient-to-r from-transparent via-white/55 to-transparent opacity-60" />
          </span>
          <PiStarFourBold className="relative w-7 h-7 text-white transition-transform duration-500 group-hover:rotate-180" />
          <span className="relative text-lg text-white tracking-tight">Start Your First Playtest</span>
        </button>
      </div>
    </section>
  )
}
