import { PiStarFourBold } from "react-icons/pi";
import { useNavigate } from 'react-router-dom'


export default function Hero() {
  const navigate = useNavigate()

  return (
    <div className="relative z-10 w-full flex flex-col items-center pt-28 px-6">

      {/* Title */}
      <div className="text-center mb-16">
        <h1 className="font-eb-garamond text-white text-6xl md:text-9xl font-bold mb-10 tracking-tight leading-none">
          #1 AI Video <br /> Game Analyzer
        </h1>

        <button
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

      {/* Glassy preview card */}
      <div className="max-w-6xl w-full h-[650px] backdrop-blur-[10px] bg-white/30 border border-white/10 rounded-[3.5rem] shadow-[0_0px_40px_20px_rgba(255,255,255,0.3)] relative overflow-hidden">
        {/* Subtle blue inner glow */}
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-blue-500/5 blur-[120px] rounded-full" />
      </div>

    </div>
  )
}
