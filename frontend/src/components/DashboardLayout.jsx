import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import '../playpulse.css';

const NAV_ITEMS = [
  { to: '/dashboard',   label: 'Demo',       icon: '🎮', end: true },
  { to: '/dashboard/setup',     label: 'Setup',      icon: '🛠️' },
  { to: '/dashboard/sessions',  label: 'Sessions',   icon: '🕹️' },
  { to: '/dashboard/review',    label: 'Review',     icon: '📊' },
  { to: '/dashboard/aggregate', label: 'Aggregate',  icon: '🏆' },
  { to: '/dashboard/sphinx',    label: 'Sphinx',     icon: '🔮' },
];

export default function DashboardLayout() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen" style={{ background: '#080a0f' }}>
      {/* Top navigation bar */}
      <nav
        className="sticky top-0 z-50 border-b border-white/5 backdrop-blur-md"
        style={{ background: 'rgba(8,10,15,0.9)' }}
      >
        <div className="flex items-center h-14 px-5 gap-4 max-w-[1400px] mx-auto">
          {/* Home / Logo */}
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 hover:opacity-70 transition-opacity mr-2"
          >
            <img src="/logo.png" alt="" className="w-5 h-5" />
            <span className="text-white font-bold text-sm tracking-wide">PatchLab</span>
          </button>

          <div className="h-5 w-px bg-white/10" />

          {/* Nav links */}
          <div className="flex items-center gap-1">
            {NAV_ITEMS.map(({ to, label, icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide transition-all flex items-center gap-1.5 ${
                    isActive
                      ? 'bg-white/10 text-white'
                      : 'text-white/40 hover:text-white/70 hover:bg-white/5'
                  }`
                }
              >
                <span>{icon}</span>
                <span>{label}</span>
              </NavLink>
            ))}
          </div>

          {/* Right side status */}
          <div className="ml-auto flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              <span className="text-[10px] text-white/30 tracking-widest uppercase">API Ready</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Page content */}
      <Outlet />
    </div>
  );
}
