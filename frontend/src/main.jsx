import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import App from './App.jsx'
import DashboardLayout from './components/DashboardLayout.jsx'
import Dashboard from './components/Dashboard.jsx'
import ProjectSetup from './pages/ProjectSetup.jsx'
import SessionManagement from './pages/SessionManagement.jsx'
import SessionReview from './pages/SessionReview.jsx'
import SphinxExplorer from './pages/SphinxExplorer.jsx'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="setup" element={<ProjectSetup />} />
          <Route path="sessions" element={<SessionManagement />} />
          <Route path="review" element={<SessionReview />} />
          <Route path="sphinx" element={<SphinxExplorer />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
