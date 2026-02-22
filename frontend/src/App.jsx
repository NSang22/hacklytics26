import { useEffect, useRef } from 'react'
import Navbar from './components/Navbar'
import Hero from './components/Hero'
import WhatIsIt from './components/WhatIsIt'
import FAQ from './components/FAQ'

const TOTAL_FRAMES = 207
// Tweak this — 0.4 means full animation plays in first 40% of scroll
// Lower = faster (more video-like), Higher = slower (more deliberate)
const SCROLL_RANGE = 1.0

const frameSrc = (i) =>
  `/frames/ezgif-frame-${String(i).padStart(3, '0')}.jpg`

function drawCover(ctx, img, canvas) {
  const w = img.naturalWidth
  const h = img.naturalHeight
  if (!w || !h) return
  const scale = Math.max(canvas.width / w, canvas.height / h)
  const x = (canvas.width - w * scale) / 2
  const y = (canvas.height - h * scale) / 2
  ctx.drawImage(img, x, y, w * scale, h * scale)
}

function App() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d', { alpha: false })

    let lastIdx = 0

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
      const img = images[lastIdx]
      if (img?.complete && img.naturalWidth) drawCover(ctx, img, canvas)
    }

    // Simple Image preload — fast, no fetch overhead
    const images = []
    for (let i = 1; i <= TOTAL_FRAMES; i++) {
      const img = new Image()
      img.src = frameSrc(i)
      img.onload = () => {
        if (i === 1) resize()
      }
      images.push(img)
    }

    const state = { target: 0, current: 0 }

    let rafId
    const animate = () => {
      // 0.3 = snappy but not jarring. Lower = smoother but laggy.
      state.current += (state.target - state.current) * 0.5

      const idx = Math.min(TOTAL_FRAMES - 1, Math.max(0, Math.round(state.current)))

      if (idx !== lastIdx) {
        lastIdx = idx
        const img = images[idx]
        if (img?.complete && img.naturalWidth) drawCover(ctx, img, canvas)
      }

      rafId = requestAnimationFrame(animate)
    }
    rafId = requestAnimationFrame(animate)

    const handleScroll = () => {
      const scrollTop = window.scrollY
      const docHeight = document.documentElement.scrollHeight - window.innerHeight
      // Animation completes within SCROLL_RANGE of total scroll
      const progress = Math.min(1, scrollTop / (docHeight * SCROLL_RANGE))
      state.target = progress * (TOTAL_FRAMES - 1)
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    window.addEventListener('resize', resize)

    return () => {
      cancelAnimationFrame(rafId)
      window.removeEventListener('scroll', handleScroll)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <div className="relative w-full" style={{ height: '180vh' }}>

      {/* Background canvas — no img tag swapping, no flicker */}
      <canvas
        ref={canvasRef}
        className="fixed top-0 left-0 w-full h-screen -z-20"
      />

      {/* Dark overlay */}
      <div className="fixed top-0 left-0 w-full h-screen bg-black/65 -z-10" />

      {/* Navbar */}
      <Navbar />

      {/* Hero */}
      <Hero />

      {/* What Is It */}
      <WhatIsIt />

      {/* FAQ */}
      <FAQ />

    </div>
  )
}

export default App