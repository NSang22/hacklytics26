import { Routes, Route, Link, Navigate } from 'react-router-dom'
import CreateProject from './pages/CreateProject'
import ProjectOverview from './pages/ProjectOverview'
import LiveMonitor from './pages/LiveMonitor'
import SessionReview from './pages/SessionReview'
import AggregateAnalytics from './pages/AggregateAnalytics'
import './App.css'

function App() {
  return (
    <div className="app-shell">
      <nav className="top-nav">
        <Link to="/projects/new" className="nav-brand">⚡ PlayPulse</Link>
        <Link to="/projects/new">New Project</Link>
      </nav>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/projects/new" replace />} />
          <Route path="/projects/new" element={<CreateProject />} />
          <Route path="/projects/:id" element={<ProjectOverview />} />
          <Route path="/projects/:id/aggregate" element={<AggregateAnalytics />} />
          <Route path="/sessions/:id/live" element={<LiveMonitor />} />
          <Route path="/sessions/:id/review" element={<SessionReview />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
