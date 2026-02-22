import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import ProjectSetup from './pages/ProjectSetup';
import SessionManagement from './pages/SessionManagement';
import SessionReview from './pages/SessionReview';
import CrossTesterAggregate from './pages/CrossTesterAggregate';
import SphinxExplorer from './pages/SphinxExplorer';
import './App.css';

const NAV = [
  { to: '/', label: 'Setup', icon: '🎮' },
  { to: '/sessions', label: 'Sessions', icon: '🕹️' },
  { to: '/review', label: 'Review', icon: '📊' },
  { to: '/aggregate', label: 'Aggregate', icon: '🏆' },
  { to: '/sphinx', label: 'Sphinx', icon: '🔮' },
];

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <header className="topbar">
          <span className="logo">
            <span className="logo-icon">🎯</span>
            PatchLab
          </span>
          <nav>
            {NAV.map(n => (
              <NavLink key={n.to} to={n.to} end={n.to === '/'} className={({isActive}) => isActive ? 'active' : ''}>
                <span className="nav-icon">{n.icon}</span>{n.label}
              </NavLink>
            ))}
          </nav>
        </header>
        <main className="content">
          <Routes>
            <Route path="/" element={<ProjectSetup />} />
            <Route path="/sessions" element={<SessionManagement />} />
            <Route path="/review" element={<SessionReview />} />
            <Route path="/aggregate" element={<CrossTesterAggregate />} />
            <Route path="/sphinx" element={<SphinxExplorer />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
