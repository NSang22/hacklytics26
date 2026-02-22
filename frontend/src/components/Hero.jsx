import { PiStarFourBold } from "react-icons/pi";
import { MdOutlineToggleOff } from "react-icons/md";
import { MdToggleOn } from "react-icons/md";
import { IoIosWifi } from "react-icons/io";
import { useNavigate } from 'react-router-dom'
import { useEffect, useRef } from 'react'
import { gsap } from 'gsap'


export default function Hero() {
  const navigate = useNavigate()

  const titleRef   = useRef(null)
  const btnRef     = useRef(null)
  const windowRef  = useRef(null)
  const macWinRef  = useRef(null)
  const dockRef    = useRef(null)

  useEffect(() => {
    const tl = gsap.timeline({ defaults: { ease: 'power2.out', duration: 0.7 } })

    // title slides down from above
    gsap.set(titleRef.current,  { opacity: 0, y: -50 })
    // button fades in place
    gsap.set(btnRef.current,    { opacity: 0 })
    // outer window slides up from below
    gsap.set(windowRef.current, { opacity: 0, y: 60 })
    // inner mac window slides in from left
    gsap.set(macWinRef.current, { opacity: 0, x: -40 })
    // dock slides up from below
    gsap.set(dockRef.current,   { opacity: 0, y: 30 })

    tl.to(titleRef.current,  { opacity: 1, y: 0 })
      .to(btnRef.current,    { opacity: 1 }, '-=0.4')
      .to(windowRef.current, { opacity: 1, y: 0 }, '-=0.3')
      .to(macWinRef.current, { opacity: 1, x: 0 }, '-=0.4')
      .to(dockRef.current,   { opacity: 1, y: 0 }, '-=0.3')
  }, [])

  return (
    <div className="relative z-10 w-full flex flex-col items-center pt-28 px-6">

      {/* Title */}
      <div ref={titleRef} className="text-center mb-16">
        <h1 className="font-eb-garamond text-white text-6xl md:text-9xl font-bold mb-10 tracking-tight leading-none">
          #1 AI Video <br /> Game Analyzer
        </h1>

        <button
        ref={btnRef}
        onClick={() => navigate('/dashboard')}
        className="group hover:cursor-pointer relative inline-flex items-center gap-4 overflow-hidden rounded-2xl bg-[#196eff] px-10 py-5 font-semibold transition-all duration-300
                    shadow-[0_12px_30px_rgba(0,0,0,0.35)]
                    hover:scale-[1.04] hover:shadow-[0_18px_45px_rgba(0,0,0,0.45)]
                    active:scale-[0.98]"
        >
        {/* 3D lighting (behind shimmer) */}
        <span className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-b from-white/25 to-transparent opacity-70" />
        <span className="pointer-events-none absolute inset-0 rounded-2xl shadow-[inset_0_-8px_14px_rgba(0,0,0,0.25)]" />

        {/* shimmer ON TOP so it stays visible */}
        <span className="pointer-events-none absolute inset-0 rounded-2xl">
            <span className="absolute inset-y-0 -left-1/3 w-full shimmer bg-gradient-to-r from-transparent via-white/55 to-transparent opacity-60" />
        </span>

        <PiStarFourBold className="relative w-7 h-7 text-white transition-transform duration-500 group-hover:rotate-180" />
        <span className="relative text-lg text-white tracking-tight">Start Analyzing</span>
        </button>
      </div>

      <div
        ref={windowRef}
        className="max-w-6xl w-full h-[750px] rounded-[14px] shadow-[0_0px_40px_20px_rgba(255,255,255,0.3)] relative overflow-hidden"
        style={{ backgroundImage: "url('/background.png')", backgroundSize: 'cover', backgroundPosition: 'center' }}
      >
        {/* Top Bar */}
        <div className="absolute opacity-50 top-0 left-0 w-full h-9 bg-black/80 backdrop-blur-md flex items-center justify-between pl-4 pr-1">
          {/* Logo — far left */}
          <img src="/logo.png" alt="PlayPulse" className="h-6 w-auto object-contain" />

          {/* Right-side icons */}
          <div className="flex items-center gap-3">
            <IoIosWifi className="text-white w-6 h-6 opacity-90" />

            {/* Stacked toggles */}
            <div className="relative w-9 h-5 flex-shrink-0">
              <MdOutlineToggleOff className="absolute top-[-4px] left-0 w-4 h-5 text-white/90" />
              <MdToggleOn        className="absolute top-[4px] left-0 w-4 h-5.5 text-white/90" />
            </div>
          </div>
        </div>
        {/* Subtle blue inner glow */}
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-blue-500/5 blur-[120px] rounded-full" />

        {/* Inner macOS-style dark window */}
        <div ref={macWinRef} className="absolute top-[47%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80%] h-[72%] rounded-[20px] bg-[#1e1e1e]/90 backdrop-blur-sm shadow-[0_20px_60px_rgba(0,0,0,0.6)] border border-white/10 overflow-hidden">
          {/* Title bar */}
          <div className="w-full h-9 bg-[#2a2a2a] flex items-center px-4 gap-2 border-b border-white/5">
            {/* Traffic lights */}
            <span className="w-3 h-3 rounded-full bg-[#ff5f57] shadow-[0_0_4px_rgba(255,95,87,0.6)]" />
            <span className="w-3 h-3 rounded-full bg-[#febc2e] shadow-[0_0_4px_rgba(254,188,46,0.6)]" />
            <span className="w-3 h-3 rounded-full bg-[#28c840] shadow-[0_0_4px_rgba(40,200,64,0.6)]" />
          </div>
          {/* Window body — video + overlay */}
          <div className="relative w-full h-full bg-[#1a1a1a] overflow-hidden flex items-center justify-center">
            {/* Video */}
            <video
              src="/tmp.mp4"
              autoPlay
              loop
              muted
              playsInline
              className="absolute inset-3 w-[calc(100%-1.5rem)] h-[calc(83%-1.5rem)] object-cover opacity-80 rounded-xl"
            />

            {/* Dark vignette */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-black/20 pointer-events-none" />

            {/* Bottom overlay: analyzing bar */}
            <div className="absolute bottom-12 left-4 right-4 px-4 py-2.5 rounded-xl bg-black/50 backdrop-blur-sm border border-white/10 flex items-center justify-between gap-4">
              {/* Pulsing label */}
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#196eff] animate-pulse shadow-[0_0_6px_rgba(25,110,255,0.8)]" />
                <span className="text-xs text-white/70 font-medium tracking-[0.2em] uppercase">Analyzing</span>
              </div>

              {/* Fake waveform bars */}
              <div className="flex items-end gap-[3px] h-6">
                {[4,7,5,9,6,8,4,10,6,5,8,7,4,9,6].map((h, i) => (
                  <div
                    key={i}
                    className="w-[3px] rounded-full bg-[#196eff]"
                    style={{ height: `${h * 2}px` }}
                  />
                ))}
              </div>

              {/* Metrics */}
              <div className="flex items-center gap-3 text-[10px] font-mono text-white/40">
                <span>FPS <span className="text-white/70">60</span></span>
                <span>ENG <span className="text-[#28c840]/80">94%</span></span>
                <span>CONF <span className="text-[#febc2e]/80">0.87</span></span>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Dock */}
        <div ref={dockRef} className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-2 rounded-2xl bg-white/10 backdrop-blur-md border border-white/30 shadow-[0_0px_20px_rgba(0,0,0,0.2)]">
          {[
            { src: '/apps.png',     alt: 'Apps'     },
            { src: '/safari.png',   alt: 'Safari'   },
            { src: '/settings.png', alt: 'Settings' },
            { src: '/music.png',    alt: 'Music'    },
            { src: '/steam.png',    alt: 'Steam'    },
          ].map(({ src, alt }) => (
            <div key={alt} className="w-11 h-11 rounded-xl overflow-hidden flex-shrink-0">
              <img src={src} alt={alt} className="w-full h-full object-cover" />
            </div>
            
            
          ))}
          {/* Our logo — black bg */}
          <div className="w-11 h-11 rounded-xl bg-black flex items-center justify-center flex-shrink-0 overflow-hidden">
            <img src="/logo.png" alt="PlayPulse" className="w-20 h-20 object-contain" />
          </div>
        </div>

          

      </div>

    </div>
  )
}
