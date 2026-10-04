import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { aiReportsApi } from '../services/api'

const sections = [
  ['scientific_summary', 'Scientific summary'],
  ['uncertainty_explanation', 'Scientific uncertainty'],
  ['sampling_decision_explanation', 'Sampling-decision explanation'],
  ['one_health_summary', 'One Health summary'],
]

const AIReportPanel = forwardRef(function AIReportPanel({ caseId, contextId }, ref) {
  const [state, setState] = useState({ loading: true, enabled: false, available: false, report: null, error: '' })
  const [printReady, setPrintReady] = useState(false)
  const generation = useRef(0)
  const refresh = useCallback(async (forPrint = false) => {
    const token = ++generation.current
    setPrintReady(false)
    try {
      const result = await aiReportsApi.latest(caseId, contextId)
      if (token !== generation.current) return
      setState({ ...result, loading: false, error: '' })
      setPrintReady(Boolean(forPrint && result.enabled && result.available && result.report?.exportable))
    } catch (error) {
      if (token === generation.current) setState(previous => ({ ...previous, report: null, loading: false, error: error.message }))
    }
  }, [caseId, contextId])
  useEffect(() => {
    const requests = generation
    refresh()
    const onFocus = () => refresh()
    const afterPrint = () => setPrintReady(false)
    window.addEventListener('focus', onFocus)
    window.addEventListener('afterprint', afterPrint)
    return () => { requests.current++; window.removeEventListener('focus', onFocus); window.removeEventListener('afterprint', afterPrint) }
  }, [refresh])
  useImperativeHandle(ref, () => ({ refreshForPrint: () => refresh(true) }), [refresh])
  async function act(action) {
    const token = ++generation.current
    setPrintReady(false)
    setState(previous => ({ ...previous, loading: true, error: '' }))
    try {
      const report = action === 'approve'
        ? await aiReportsApi.approve(caseId, state.report.id, contextId)
        : await aiReportsApi.generate(caseId, contextId)
      if (token === generation.current) setState(previous => ({ ...previous, loading: false, report }))
    } catch (error) {
      if (token === generation.current) setState(previous => ({ ...previous, loading: false, error: error.message,
        report: error.status === 409 && previous.report ? { ...previous.report, stale: true, current: false, exportable: false } : previous.report }))
    }
  }
  const report = state.report
  return <section id="ai-explanation" className={`report-section ai-report-panel ${printReady && report?.exportable ? 'ai-print-approved' : ''}`}>
    <h2>AI Scientific Explanation</h2>
    <p>AI-assisted explanation of recorded scientific results. The model arranges source-linked statements within scientific safeguards. Researcher review is required.</p>
    <div className="ai-controls">
      {state.loading && <p role="status">Loading AI explanation…</p>}
      {!state.loading && !state.enabled && <p>AI explanations are disabled. The scientific report remains available.</p>}
      {state.enabled && !state.available && <p>AI generation is unavailable until the server provider configuration is complete.</p>}
      {state.error && <p role="alert" className="error-banner">{state.error}</p>}
      <div className="button-row">
        {state.enabled && <button className="button" disabled={state.loading || !state.available} onClick={() => act('generate')}>{report ? 'Regenerate AI Explanation' : 'Generate AI Explanation'}</button>}
        {report && <button className="button" disabled={state.loading || report.stale || report.review_status === 'APPROVED'} onClick={() => act('approve')}>Approve AI Explanation</button>}
        <button className="button" disabled={state.loading} onClick={() => refresh()}>Refresh AI status</button>
      </div>
    </div>
    {report && <>
      <p className="ai-report-status">{report.stale ? 'STALE — regenerate before approval or export' : report.review_status === 'APPROVED' ? 'APPROVED — scientific input current' : 'DRAFT — researcher review required'}</p>
      <p>Model: {report.model_identifier} · Generated: {report.generated_at} · Validation: {report.validation_status} · Prompt: {report.prompt_version}</p>
      {sections.map(([name, title]) => <div key={name} className="ai-narrative-section"><h3>{title}</h3>
        <p>{report.narrative[name].statements.map((statement, index) => <span key={index}>{statement.text}{' '}
          <small className="ai-source-indicator" title={statement.source_references.map(reference => report.sources[reference]?.kind || 'Source record').join(', ')}>[{index + 1}]</small>{' '}
        </span>)}</p>
        <details className="ai-source-details"><summary>Supporting source records</summary>
          {report.narrative[name].statements.map((statement, index) => <p key={index}>[{index + 1}] {statement.source_references.map(reference => {
            const source = report.sources[reference] || {}
            return [source.kind, source.label, source.status, source.rule, ...(source.scientific_sources || []).map(item => item.doi)].filter(Boolean).join(' · ')
          }).join('; ')}</p>)}
        </details>
      </div>)}
    </>}
  </section>
})

export default AIReportPanel
