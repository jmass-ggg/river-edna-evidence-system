import { Navigate, Route, Routes } from 'react-router-dom'
import ApplicationLayout from './components/ApplicationLayout'
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import Investigations from './pages/Investigations'
import InvestigationWorkspace from './pages/InvestigationWorkspace'
import Sites from './pages/Sites'
import Reports from './pages/Reports'

export default function App() {
  return <Routes>
    <Route path="/" element={<Home />} />
    <Route element={<ApplicationLayout />}>
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/investigations" element={<Investigations />} />
      <Route path="/investigations/new" element={<Investigations formOpen />} />
      <Route path="/investigations/:caseId" element={<InvestigationWorkspace />} />
      <Route path="/sites" element={<Sites />} />
      <Route path="/reports" element={<Reports />} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}
