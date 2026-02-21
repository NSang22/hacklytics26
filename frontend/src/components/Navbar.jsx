export default function Navbar() {
  return (
    <nav className="absolute max-w-7xl mx-auto left-0 right-0 top-0 w-full z-50 px-12 py-10 flex justify-start items-center bg-transparent">
      <div className="flex items-center gap-3">
        <img src="/logo.png" alt="Logo" className="w-10 h-10" />
        <span className="text-white font-bold text-xl tracking-tight">
          CrashOut
        </span>
      </div>

      <div className="hidden ml-10 md:flex space-x-12 text-white text-xs font-bold tracking-[0.2em] uppercase">
        <a href="#" className="hover:text-white transition-colors">Pricing</a>
        <a href="#" className="hover:text-white transition-colors">Desktop</a>
        <a href="#" className="hover:text-white transition-colors">Contact</a>
      </div>
    </nav>
  )
}
