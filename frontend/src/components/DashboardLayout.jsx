import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import '../playpulse.css';

const NAV_ITEMS = [
  { to: '/dashboard',          label: 'Demo',     end: true },
  { to: '/dashboard/setup',    label: 'Setup'             },
  { to: '/dashboard/sessions', label: 'Sessions'          },
  { to: '/dashboard/review',   label: 'Review'            },
  { to: '/dashboard/sphinx',   label: 'Sphinx'            },
];

const ROUTE_ACCENT = {
  '/dashboard':          { rgb: '236,72,153',  text: '#f9a8d4', mid: 'rgba(20,8,16,0.65)' },
  '/dashboard/setup':    { rgb: '34,197,94',   text: '#86efac', mid: 'rgba(5,18,10,0.65)' },
  '/dashboard/sessions': { rgb: '59,130,246',  text: '#93c5fd', mid: 'rgba(5,10,24,0.65)' },
  '/dashboard/review':   { rgb: '245,158,11',  text: '#fcd34d', mid: 'rgba(18,12,3,0.65)' },
  '/dashboard/sphinx':   { rgb: '249,115,22',  text: '#fdba74', mid: 'rgba(20,8,3,0.65)'  },
};
const DEFAULT_ACCENT = { rgb: '255,255,255', text: 'rgba(255,255,255,0.65)', mid: 'rgba(8,8,12,0.65)' };

export default function DashboardLayout() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const accent = ROUTE_ACCENT[pathname] ?? DEFAULT_ACCENT;

  return (
    <div className="min-h-screen" style={{ background: '#050608' }}>
      {/* Top navigation bar */}
      <nav
        className="sticky top-0 z-50 backdrop-blur-xl"
        style={{
          background: `linear-gradient(135deg, rgba(5,6,8,0.78) 0%, ${accent.mid} 50%, rgba(5,6,8,0.78) 100%)`,
          boxShadow: `0 1px 0 0 rgba(${accent.rgb},0.18), inset 0 1px 0 0 rgba(255,255,255,0.04), 0 8px 40px 0 rgba(0,0,0,0.55)`,
        }}
      >
        <div className="flex items-center h-14 px-6 gap-4 max-w-5xl mx-auto">
          {/* Home / Logo */}
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 hover:opacity-70 transition-opacity mr-2"
          >
            <img src="/logo.png" alt="" className="w-10 h-auto" />
            <span className="text-white font-bold text-sm tracking-wide font-eb-garamond">PatchLab</span>
          </button>

          <div className="h-5 w-px bg-white/10" />

          {/* Nav links */}
          <div className="flex items-center gap-1">
            {NAV_ITEMS.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide transition-all duration-200 ${
                    isActive ? '' : 'text-white/30 hover:text-white/60 hover:bg-white/[0.04] border border-transparent'
                  }`
                }
                style={({ isActive }) => isActive ? {
                  background: `rgba(${accent.rgb},0.10)`,
                  color: accent.text,
                  border: `1px solid rgba(${accent.rgb},0.20)`,
                  boxShadow: `0 0 14px 0 rgba(${accent.rgb},0.18)`,
                } : {}}
              >
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
