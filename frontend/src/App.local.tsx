import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useState } from 'react'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Artifacts from './pages/Artifacts'
import ArtifactDetail from './pages/ArtifactDetail'
import Workflows from './pages/Workflows'
import WorkflowDetail from './pages/WorkflowDetail'
import Certificates from './pages/Certificates'
import CertificateDetail from './pages/CertificateDetail'
import Compliance from './pages/Compliance'
import SystemHealth from './pages/SystemHealth'
import Logs from './pages/Logs'

// Mock user for local development
const mockUser = {
  signInDetails: {
    loginId: 'local-dev@example.com'
  }
}

function App() {
  const [user] = useState(mockUser)

  const handleSignOut = () => {
    console.log('Sign out (local dev mode)')
  }

  return (
    <Router>
      <Layout user={user} signOut={handleSignOut}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/artifacts" element={<Artifacts />} />
          <Route path="/artifacts/:id" element={<ArtifactDetail />} />
          <Route path="/workflows" element={<Workflows />} />
          <Route path="/workflows/:id" element={<WorkflowDetail />} />
          <Route path="/certificates" element={<Certificates />} />
          <Route path="/certificates/:id" element={<CertificateDetail />} />
          <Route path="/compliance" element={<Compliance />} />
          <Route path="/system" element={<SystemHealth />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
