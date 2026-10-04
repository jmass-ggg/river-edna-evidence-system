const API_BASE = import.meta.env?.VITE_API_BASE_URL || 'http://localhost:8000'

export class ApiError extends Error {
  constructor(message, status, details) { super(message); this.name = 'ApiError'; this.status = status; this.details = details }
}

export async function apiRequest(path, options = {}) {
  let response
  try { response = await fetch(`${API_BASE}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers } }) }
  catch (error) { throw new ApiError(`Unable to reach the API: ${error.message}`, 0, error) }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail ?? body?.error
    const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(item => `${item.loc?.join('.') || 'Request'}: ${item.msg}`).join('; ') : detail?.message || `Request failed with status ${response.status}`
    throw new ApiError(message, response.status, detail)
  }
  return response.status === 204 ? null : response.json()
}

const get = path => apiRequest(path)
const post = (path, payload = {}) => apiRequest(path, { method: 'POST', body: JSON.stringify(payload) })

export const casesApi = { list: () => get('/cases'), get: id => get(`/cases/${id}`), create: payload => post('/cases', payload) }
export const demoApi = { loadWigger: () => get('/demo/wigger'), map: () => get('/demo/wigger/map') }
export const evidenceApi = { list: id => get(`/cases/${id}/evidence`), assess: id => get(`/cases/${id}/evidence-assessment`), create: (id,payload) => post(`/cases/${id}/evidence`,payload) }
export const samplingApi = {
  sites: id => get(`/cases/${id}/sites`), zones: id => get(`/cases/${id}/zones`), map: id => get(`/cases/${id}/map`), generated: id => get(`/cases/${id}/generated-candidates`), generate: id => post(`/cases/${id}/generated-candidates`), importWigger: id => post(`/cases/${id}/wigger-reference`),
  decide: id => post(`/cases/${id}/sampling-decision`), latestDecision: id => get(`/cases/${id}/sampling-decision`), trace: (id,decisionId) => get(`/cases/${id}/decision-trace${decisionId ? `?decision_id=${decisionId}` : ''}`),
  createSite: (id,payload) => post(`/cases/${id}/sites`,payload), createZone: (id,payload) => post(`/cases/${id}/zones`,payload),
}
export const hydrologyApi = { reach: id => get(`/hydrology/reaches/${id}`), upstream: id => get(`/hydrology/upstream/${id}`), distance: (from,to) => get(`/hydrology/distance?from_hyriv_id=${from}&to_hyriv_id=${to}`) }
export const contextApi = { list: id => get(`/cases/${id}/context`), collect: (id,payload) => post(`/cases/${id}/context/collect`,payload) }
export const oneHealthApi = { get: id => get(`/cases/${id}/one-health`) }
export const followUpApi = { list: id => get(`/cases/${id}/follow-up-samples`), create: (id,payload) => post(`/cases/${id}/follow-up-samples`,payload) }
export const investigationApi = { runs: id => get(`/cases/${id}/investigation-runs`), run: (id,runId) => get(`/cases/${id}/investigation-runs/${runId}`), reinvestigate: (id,payload={}) => post(`/cases/${id}/reinvestigate`,payload) }

export async function loadCaseBundle(caseId) {
  const entries = await Promise.allSettled([
    casesApi.get(caseId), evidenceApi.list(caseId), evidenceApi.assess(caseId), samplingApi.sites(caseId), samplingApi.zones(caseId),
    samplingApi.generated(caseId), samplingApi.latestDecision(caseId), contextApi.list(caseId), oneHealthApi.get(caseId), followUpApi.list(caseId), investigationApi.runs(caseId),
    samplingApi.map(caseId),
  ])
  if (entries[0].status === 'rejected') throw entries[0].reason
  const keys = ['case','evidence','assessments','sites','zones','generated','decision','context','oneHealth','followUps','runs','map']
  const bundle=Object.fromEntries(entries.map((result,index) => [keys[index], result.status === 'fulfilled' ? result.value : null]))
  bundle.errors=Object.fromEntries(entries.flatMap((result,index) => result.status === 'rejected' ? [[keys[index],result.reason]] : []))
  bundle.trace=null
  bundle.comparison=null
  bundle.investigationRun=null
  if (bundle.decision) {
    const decisionId=bundle.decision.id
    const run=bundle.runs?.find(item=>item.new_decision_id===decisionId)
    if (run) {
      try {
        bundle.investigationRun=await investigationApi.run(caseId,run.investigation_run_id)
        bundle.comparison=bundle.investigationRun.candidate_generation
        bundle.trace=bundle.investigationRun.decision_trace
      } catch(error) { bundle.errors.investigationRun=error }
    } else if (bundle.decision.candidate_scope !== 'GENERATED_REPRESENTATIVES' || bundle.runs) {
      bundle.comparison=bundle.decision.candidate_snapshot
      try { bundle.trace=await samplingApi.trace(caseId,decisionId) }
      catch(error) { bundle.errors.trace=error }
    }
    if (bundle.trace && bundle.trace.decision_id !== decisionId) {
      bundle.trace=null
      bundle.errors.trace=new ApiError('Decision trace does not match the selected decision', 0)
    }
  } else if (!bundle.errors.decision) bundle.comparison=bundle.generated
  return bundle
}

export async function loadCaseIndex() {
  const result=await casesApi.list()
  const cases=await Promise.all(result.cases.map(async record=>{
    const [decision,followUps,sites]=await Promise.all([
      samplingApi.latestDecision(record.id), followUpApi.list(record.id), samplingApi.sites(record.id),
    ])
    const detection=sites.find(site=>site.id===record.detection_site_id)
    return {...record,scientificDecision:decision,followUpCount:followUps.length,detectionSiteLabel:detection?.label||record.detection_site_id.slice(0,8)}
  }))
  return {cases,total:result.total}
}

export async function loadReportBundle(caseId) {
  const bundle=await loadCaseBundle(caseId)
  const runs=bundle.runs||[]
  const details=await Promise.allSettled(runs.map(run=>
    bundle.investigationRun?.investigation_run_id===run.investigation_run_id
      ?Promise.resolve(bundle.investigationRun):investigationApi.run(caseId,run.investigation_run_id)))
  bundle.history=details.map((result,index)=>result.status==='fulfilled'
    ?result.value:{...runs[index],history_unavailable:true,history_error:result.reason.message})
  return bundle
}
