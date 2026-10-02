import { Droplets, FlaskConical, LayoutGrid, MapPin, FileText, UserRound } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

const links = [
  ['/dashboard', 'Dashboard', LayoutGrid], ['/investigations', 'Investigations', FlaskConical],
  ['/sites', 'Sites', MapPin], ['/reports', 'Reports', FileText],
]

export default function ApplicationLayout() {
  return <div className="app-shell">
    <header className="app-nav">
      <NavLink className="brand" to="/"><span className="brand-mark"><Droplets size={19}/></span><strong>eDNA Evidence Investigator</strong></NavLink>
      <nav aria-label="Application navigation">{links.map(([to, label, Icon]) => <NavLink key={to} to={to} className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={17}/>{label}</NavLink>)}</nav>
      <div className="profile"><div><strong>Scientific workspace</strong><small>Authentication unavailable</small></div><span className="profile-icon"><UserRound size={17}/></span></div>
    </header>
    <main><Outlet /></main>
  </div>
}
