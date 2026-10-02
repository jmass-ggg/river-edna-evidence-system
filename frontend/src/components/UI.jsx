import { AlertCircle, Inbox, LoaderCircle } from 'lucide-react'

export function PageHeader({ title, description, action }) {
  return <div className="page-header"><div><h1>{title}</h1><p>{description}</p></div>{action}</div>
}

export function StatusBadge({ value = 'NOT_EVALUATED' }) {
  const key = String(value).toUpperCase()
  return <span className={`badge badge-${key.toLowerCase()}`}>{key.replaceAll('_', ' ')}</span>
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
