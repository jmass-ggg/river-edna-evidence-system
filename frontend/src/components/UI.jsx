import { AlertCircle, Inbox, LoaderCircle } from 'lucide-react'

export function PageHeader({ title, description, action }) {
  return <div className="page-header"><div><h1>{title}</h1><p>{description}</p></div>{action}</div>
}

export function StatusBadge({ value = 'NOT_EVALUATED' }) {
  const key = String(value).toUpperCase()
  return <span className={`badge badge-${key.toLowerCase()}`}>{key.replaceAll('_', ' ')}</span>
}

export function SourceHypothesisStatus({zone, assessment}) {
  return <>
    <p>Network validation: <StatusBadge value={zone.validation_status}/></p>
    <p>Validated river topology establishes a mapped relationship, not a biological source or an independently verified source hypothesis.</p>
    <p>Hypothesis state: {assessment?.hypothesis_status?<StatusBadge value={assessment.hypothesis_status}/>:'Not evaluated'}</p>
    <p>{assessment?.hypothesis_reason||'No hypothesis-state result is available from the scientific engine.'}</p>
    {assessment?<>
      <p>Evidence compatibility counts: supports {assessment.summary.supports}; contradicts {assessment.summary.contradicts}; neutral {assessment.summary.neutral}; unknown {assessment.summary.unknown}</p>
      {assessment.assessments.map((item,index)=><div key={`${item.evidence_id}:${index}`}>
        <p>Evidence compatibility: <StatusBadge value={item.compatibility}/></p>
        <p>Scientific rule: {item.rule_id||'No validated scientific rule applies to this evidence type.'}</p>
        <p>Assessment reason: {item.reason}</p>
      </div>)}
    </>:<p>Evidence compatibility: Not assessed. Recorded observations are required before assessment.</p>}
  </>
}

export function NetworkDistance({candidate}) {
  const distance=candidate.network_distance_km
  return <>
    <span>{Number.isFinite(distance)?`${distance.toFixed(3)} km`:(candidate.network_distance_reason||'Distance was not recorded in this historical candidate snapshot.')}</span>
    {Number.isFinite(distance)&&<small className="block">{candidate.network_distance_status==='VALIDATED_REFERENCE'?'Validated reference':candidate.network_distance_status==='GEOMETRY_DERIVED'?'Reviewed geometry distance':candidate.network_distance_status==='ESTIMATED'?'Estimated distance':'Historical calculation method unavailable'}</small>}
    {candidate.network_distance_method&&<small className="block">{candidate.network_distance_method}</small>}
    {Number.isFinite(distance)&&candidate.network_distance_reason&&<small className="block">{candidate.network_distance_reason}</small>}
  </>
}

export function DataState({ status = 'EMPTY', title, message, action }) {
  const Icon = status === 'LOADING' ? LoaderCircle : status === 'ERROR' ? AlertCircle : Inbox
  return <div className={`data-state ${status.toLowerCase()}`}><Icon size={32}/><strong>{title}</strong><p>{message}</p>{action}</div>
}

export function Panel({ title, children, className = '' }) {
  return <section className={`panel ${className}`}><h2>{title}</h2>{children}</section>
}

export function Accordion({ title, open, onToggle, children, trailing }) {
  return <section className="accordion"><button className="accordion-head" onClick={onToggle} aria-expanded={open}><strong>{title}</strong><span>{trailing} {open ? '⌃' : '⌄'}</span></button>{open && <div className="accordion-body">{children}</div>}</section>
}
