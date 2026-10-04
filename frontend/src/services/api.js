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

const casePath=(id,suffix='',context)=>`/cases/${id}${suffix}${context?`?detection_context_id=${encodeURIComponent(context)}`:''}`
export const aiReportsApi = {
  latest: (id, context) => get(casePath(id, '/ai-report', context)),
  generate: (id, context) => post(casePath(id, '/ai-report', context)),
  approve: (id, reportId, context) => post(casePath(id, `/ai-report/${reportId}/approve`, context)),
}
export const casesApi = { list: () => get('/cases'), get: (id,context) => get(casePath(id,'',context)), create: payload => post('/cases', payload) }
export const demoApi = { loadWigger: () => get('/demo/wigger'), map: () => get('/demo/wigger/map') }
export const evidenceApi = { list: (id,c) => get(casePath(id,'/evidence',c)), assess: (id,c) => get(casePath(id,'/evidence-assessment',c)), create: (id,payload,c) => post(casePath(id,'/evidence',c),payload) }
export const samplingApi = {
  sites: (id,c) => get(casePath(id,'/sites',c)), zones: (id,c) => get(casePath(id,'/zones',c)), map: (id,c) => get(casePath(id,'/map',c)), generated: (id,c) => get(casePath(id,'/generated-candidates',c)), generate: (id,c) => post(casePath(id,'/generated-candidates',c)), importWigger: (id,c) => post(casePath(id,'/wigger-reference',c)),
  decide: (id,c) => post(casePath(id,'/sampling-decision',c)), latestDecision: (id,c) => get(casePath(id,'/sampling-decision',c)), trace: (id,decisionId,c) => get(`${casePath(id,'/decision-trace',c)}${decisionId?`${c?'&':'?'}decision_id=${decisionId}`:''}`),
  createSite: (id,payload,c) => post(casePath(id,'/sites',c),payload), createZone: (id,payload,c) => post(casePath(id,'/zones',c),payload),
  validateZone: (id,zone,c)=>post(`${casePath(id,`/zones/${zone}/validate-network`,c)}${c?'&':'?'}confirmed=true`),
}
export const detectionApi={
  createInvestigation:payload=>post('/cases/multi-detection',payload),
  species:id=>get(casePath(id,'/species')),contexts:id=>get(casePath(id,'/detection-contexts')),
  addSpecies:(id,payload)=>post(casePath(id,'/species'),payload),addSite:(id,payload)=>post(casePath(id,'/detection-sites'),payload),
  addContext:(id,payload)=>post(casePath(id,'/detection-contexts'),payload),
  observe:(id,context,payload)=>post(casePath(id,`/detection-contexts/${context}/observations`),payload),
  observations:(id,c)=>get(casePath(id,'/observations',c)),
}
export const hydrologyApi = { match:payload=>post('/hydrology/match-location',payload), reach: id => get(`/hydrology/reaches/${id}`), upstream: id => get(`/hydrology/upstream/${id}`), distance: (from,to) => get(`/hydrology/distance?from_hyriv_id=${from}&to_hyriv_id=${to}`) }
export const contextApi = { list: (id,c) => get(casePath(id,'/context',c)), collect: (id,payload,c) => post(casePath(id,'/context/collect',c),payload) }
export const oneHealthApi = { get: (id,c) => get(casePath(id,'/one-health',c)) }
export const followUpApi = { list: (id,c) => get(casePath(id,'/follow-up-samples',c)), create: (id,payload,c) => post(casePath(id,'/follow-up-samples',c),payload) }
export const investigationApi = { runs: (id,c) => get(casePath(id,'/investigation-runs',c)), run: (id,runId,c) => get(casePath(id,`/investigation-runs/${runId}`,c)), reinvestigate: (id,payload={},c) => post(casePath(id,'/reinvestigate',c),payload) }

export async function loadCaseBundle(caseId,context) {
  const entries = await Promise.allSettled([
    casesApi.get(caseId,context), evidenceApi.list(caseId,context), evidenceApi.assess(caseId,context), samplingApi.sites(caseId,context), samplingApi.zones(caseId,context),
    samplingApi.generated(caseId,context), samplingApi.latestDecision(caseId,context), contextApi.list(caseId,context), oneHealthApi.get(caseId,context), followUpApi.list(caseId,context), investigationApi.runs(caseId,context),
    samplingApi.map(caseId,context),
  ])
  if (entries[0].status === 'rejected') throw entries[0].reason
  const keys = ['case','evidence','assessments','sites','zones','generated','decision','context','oneHealth','followUps','runs','map']
  const bundle=Object.fromEntries(entries.map((result,index) => [keys[index], result.status === 'fulfilled' ? result.value : null]))
  bundle.errors=Object.fromEntries(entries.flatMap((result,index) => result.status === 'rejected' ? [[keys[index],result.reason]] : []))
  bundle.detectionContextId=context||null
  bundle.trace=null
  bundle.comparison=null
  bundle.investigationRun=null
  if (bundle.decision) {
    const decisionId=bundle.decision.id
    const run=bundle.runs?.find(item=>item.new_decision_id===decisionId)
    if (run) {
      try {
        bundle.investigationRun=await investigationApi.run(caseId,run.investigation_run_id,context)
        bundle.comparison=bundle.investigationRun.candidate_generation
        bundle.trace=bundle.investigationRun.decision_trace
      } catch(error) { bundle.errors.investigationRun=error }
    } else if (bundle.decision.candidate_scope !== 'GENERATED_REPRESENTATIVES' || bundle.runs) {
      bundle.comparison=bundle.decision.candidate_snapshot
      try { bundle.trace=await samplingApi.trace(caseId,decisionId,context) }
      catch(error) { bundle.errors.trace=error }
    }
    if (bundle.trace && bundle.trace.decision_id !== decisionId) {
      bundle.detectionContextId=context||null
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
    return {...record,scientificDecision:decision,followUpCount:followUps.length,detectionSiteLabel:detection?.label||'Detection site label unavailable'}
  }))
  return {cases,total:result.total}
}

export async function loadReportBundle(caseId,context) {
  const bundle=await loadCaseBundle(caseId,context)
  const runs=bundle.runs||[]
  const details=await Promise.allSettled(runs.map(run=>
    bundle.investigationRun?.investigation_run_id===run.investigation_run_id
      ?Promise.resolve(bundle.investigationRun):investigationApi.run(caseId,run.investigation_run_id,context)))
  bundle.history=details.map((result,index)=>result.status==='fulfilled'
    ?result.value:{...runs[index],history_unavailable:true,history_error:result.reason.message})
  return bundle
}
