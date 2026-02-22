export default function Navbar() {
  return (
    <nav className="absolute max-w-7xl mx-auto left-0 right-0 top-0 w-full z-50 px-12 py-10 flex justify-start items-center bg-transparent">
      <div className="flex items-center gap-3">
        <img src="/logo.png" alt="Logo" className="w-18 h-auto" />
        <span className="text-white font-eb-garamond font-bold text-3xl tracking-tight">
          PatchLab
        </span>
      </div>

      <div className="hidden ml-10 md:flex space-x-12 text-white text-xs font-bold tracking-[0.2em] uppercase">
        <span className="flex items-center gap-2 cursor-default opacity-60 select-none">
          Desktop
          <span
            className="text-[8px] font-black tracking-widest px-1.5 py-0.5 rounded-full"
            style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24', border: '1px solid rgba(251,191,36,0.30)' }}
          >
            SOON
          </span>
        </span>
        <a href="#contact" className="hover:text-white transition-colors">Contact</a>
        <a href="#faq" className="hover:text-white transition-colors">FAQ</a>
      </div>
    </nav>
  )
}
