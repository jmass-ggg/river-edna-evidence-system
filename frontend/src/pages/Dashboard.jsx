import { Activity, ClipboardCheck, FlaskConical, Plus, TestTube2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { DataState, PageHeader, Panel, StatusBadge } from '../components/UI'
import useRemoteData from '../hooks/useRemoteData'
import { loadCaseIndex } from '../services/api'

const metrics = [[Activity,'Active Investigations'],[FlaskConical,'Pending Scientific Decisions'],[TestTube2,'Follow-up Sampling'],[ClipboardCheck,'Reviews Required']]

export default function Dashboard() {
  const {status,data,error}=useRemoteData(loadCaseIndex,[]); const records=data?.cases||[]
  const active=records.filter(r=>r.status==='ACTIVE').length
  const pending=records.filter(r=>!r.scientificDecision).length
  const followUps=records.reduce((total,record)=>total+record.followUpCount,0)
  const review=records.filter(r=>r.status==='UNDER_REVIEW').length
  const values=[active,pending,followUps,review]
  return <div className="page-container">
    <PageHeader title="Dashboard" description="Monitor freshwater investigations and follow-up decisions." action={<Link className="button primary" to="/investigations/new"><Plus size={16}/> New investigation</Link>}/>
    <div className="metrics">{metrics.map(([Icon,label],i) => <div className="metric" key={label}><div><Icon size={18}/><strong>{label}</strong></div><b>{status==='READY'?values[i]:'—'}</b><small>{['Persisted ACTIVE cases','Cases without a persisted decision','Registered follow-up samples','Persisted UNDER_REVIEW cases'][i]}</small></div>)}</div>
    <div className="dashboard-grid">
      <Panel title="Investigations Requiring Attention">{status==='LOADING'?<DataState status="LOADING" title="Loading investigations" message="Requesting persisted cases."/>:status==='ERROR'?<DataState status="ERROR" title="Could not load investigations" message={error?.message}/>:review?<div className="action-list">{records.filter(r=>r.status==='UNDER_REVIEW').map(r=><Link className="button" key={r.id} to={`/investigations/${r.id}`}>{r.metadata?.name||r.target_taxon}</Link>)}</div>:<DataState title="No cases are under review" message="Review status is based on the persisted UNDER_REVIEW workflow state." action={<Link className="button primary" to="/investigations/new">Create investigation</Link>}/>}</Panel>
      <Panel title="Quick Actions"><div className="action-list"><Link className="button primary" to="/investigations/new">New Investigation</Link><Link className="button" to="/investigations">Open Investigations</Link><Link className="button" to="/sites">View Monitoring Sites</Link><Link className="button" to="/reports">Review Reports</Link></div></Panel>
    </div>
    <Panel title="Recent Investigations" className="recent"><div className="table-scroll"><table><thead><tr>{['Investigation','Target Species','Detection Site','Workflow Status','Scientific Decision','Last Updated'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{records.slice(0,8).map(r=><tr key={r.id}><td><Link to={`/investigations/${r.id}`}>{r.metadata?.name||`Investigation ${r.id.slice(0,8)}`}</Link></td><td><i>{r.target_taxon}</i></td><td>{r.detectionSiteLabel}</td><td>{r.status}</td><td><StatusBadge value={r.scientificDecision?.status||'NOT_EVALUATED'}/></td><td>{new Date(r.updated_at).toLocaleDateString()}</td></tr>)}</tbody></table></div>{status!=='LOADING'&&!records.length&&<DataState title="No investigation records are available yet." message="Create an investigation or load the Wigger demonstration."/>}</Panel>
  </div>
}
