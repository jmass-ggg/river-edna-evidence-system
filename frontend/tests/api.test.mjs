import test from 'node:test'
import assert from 'node:assert/strict'
import { apiRequest, ApiError, loadCaseBundle, loadReportBundle, loadCaseIndex, samplingApi, casesApi } from '../src/services/api.js'

const response=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}})
function mock(t,handler){const original=globalThis.fetch;globalThis.fetch=handler;t.after(()=>{globalThis.fetch=original})}

test('report history keeps unavailable old results separate from current results',async t=>{
  mock(t,bundleMock({
    'investigation-runs':response([{investigation_run_id:'old'},{investigation_run_id:'current'}]),
    old:response({detail:'Historical snapshot unavailable'},404),
    current:response({investigation_run_id:'current',change_comparison_status:'UNAVAILABLE_HISTORY',after:{decision:{status:'TIE'}}}),
  }))
  const bundle=await loadReportBundle('case')
  assert.equal(bundle.history[0].history_unavailable,true)
  assert.equal(bundle.history[0].after,undefined)
  assert.equal(bundle.history[1].after.decision.status,'TIE')
})

test('API exposes FastAPI field errors and backend error envelopes',async t=>{
  for(const body of [{detail:[{loc:['body','reach_ids'],msg:'Root reach is required'}]}, {error:{message:'Network unavailable'}}, {detail:'Invalid reach'}]){
    mock(t,async()=>response(body,422))
    await assert.rejects(apiRequest('/zones'),error=>error instanceof ApiError&&error.status===422&&/Root reach|Network unavailable|Invalid reach/.test(error.message))
  }
})
test('API handles network errors, non-JSON errors and empty responses',async t=>{
  mock(t,async()=>{throw new TypeError('offline')})
  await assert.rejects(apiRequest('/cases'),error=>error.status===0&&error.message.includes('offline'))
  globalThis.fetch=async()=>new Response('proxy failure',{status:502})
  await assert.rejects(apiRequest('/cases'),error=>error.status===502&&error.message.includes('502'))
  globalThis.fetch=async()=>new Response(null,{status:204})
  assert.equal(await apiRequest('/cases'),null)
})

function bundleMock(overrides={},calls=[]){return async url=>{
  calls.push(url)
  const path=new URL(url).pathname.split('/').at(-1)
  if(path in overrides){const value=overrides[path];if(value instanceof Error)throw value;return value}
  if(path==='case')return response({id:'case'})
  if(path==='sampling-decision')return response(null)
  return response([])
}}

test('bundle retains partial request failures and distinguishes them from empty results',async t=>{
  mock(t,bundleMock({zones:response({detail:'Invalid zone'},422),map:new Error('offline')}))
  const bundle=await loadCaseBundle('case')
  assert.equal(bundle.zones,null)
  assert.equal(bundle.errors.zones.message,'Invalid zone')
  assert.equal(bundle.errors.map.status,0)
  assert.deepEqual(bundle.evidence,[])
  assert.equal(bundle.errors.evidence,undefined)
})

test('case failure remains fatal',async t=>{
  mock(t,bundleMock({case:response({detail:'Case missing'},404)}))
  await assert.rejects(loadCaseBundle('case'),error=>error.status===404)
})

test('registered comparison and trace belong to the persisted decision',async t=>{
  const calls=[],snapshot={candidates:[{site_id:'b',hyriv_id:2}]}
  mock(t,bundleMock({'sampling-decision':response({id:'decision',candidate_scope:'REGISTERED_SITES',candidate_snapshot:snapshot}),
    'generated-candidates':response({candidates:[{hyriv_id:999}]}),'decision-trace':response({decision_id:'decision'})},calls))
  const bundle=await loadCaseBundle('case')
  assert.deepEqual(bundle.comparison,snapshot)
  assert.ok(calls.some(url=>url.endsWith('/decision-trace?decision_id=decision')))
})

test('generated decision uses its exact run even if a later run exists',async t=>{
  const snapshot={candidates:[{site_id:'stable',hyriv_id:2}]}
  mock(t,bundleMock({'sampling-decision':response({id:'decision',candidate_scope:'GENERATED_REPRESENTATIVES'}),
    'investigation-runs':response([{investigation_run_id:'run',new_decision_id:'decision'},{investigation_run_id:'later',new_decision_id:'other'}]),
    run:response({investigation_run_id:'run',candidate_generation:snapshot,decision_trace:{decision_id:'decision'}}),
    'generated-candidates':response({candidates:[{hyriv_id:999}]})}))
  const bundle=await loadCaseBundle('case')
  assert.deepEqual(bundle.comparison,snapshot)
  assert.equal(bundle.investigationRun.investigation_run_id,'run')
  assert.equal(bundle.trace.decision_id,'decision')
})

test('trace errors and mismatched versions cannot masquerade as missing science',async t=>{
  mock(t,bundleMock({'sampling-decision':response({id:'decision',candidate_scope:'REGISTERED_SITES'}),
    'decision-trace':response({detail:'Trace unavailable'},503)}))
  let bundle=await loadCaseBundle('case')
  assert.equal(bundle.errors.trace.status,503)
  globalThis.fetch=bundleMock({'sampling-decision':response({id:'decision',candidate_scope:'REGISTERED_SITES'}),
    'decision-trace':response({decision_id:'wrong'})})
  bundle=await loadCaseBundle('case')
  assert.equal(bundle.trace,null)
  assert.match(bundle.errors.trace.message,/does not match/)
})

test('failed version lookup never falls back to a current candidate comparison',async t=>{
  mock(t,bundleMock({'sampling-decision':response({id:'decision',candidate_scope:'GENERATED_REPRESENTATIVES'}),
    'investigation-runs':response([{investigation_run_id:'run',new_decision_id:'decision'}]),
    run:response({detail:'Run unavailable'},503),'generated-candidates':response({candidates:[{hyriv_id:999}]})}))
  const bundle=await loadCaseBundle('case')
  assert.equal(bundle.comparison,null)
  assert.equal(bundle.trace,null)
  assert.equal(bundle.errors.investigationRun.status,503)
})


test('index distinguishes no persisted decision from request failure',async t=>{
  mock(t,async url=>{
    if(url.endsWith('/cases'))return response({cases:[{id:'case',detection_site_id:'site'}],total:1})
    if(url.endsWith('/sampling-decision'))return response(null)
    return response([])
  })
  assert.equal((await loadCaseIndex()).cases[0].scientificDecision,null)
  for(const endpoint of ['sampling-decision','sites','follow-up-samples']){
    const working=globalThis.fetch
    globalThis.fetch=async url=>url.endsWith('/'+endpoint)?response({detail:'unavailable'},503):working(url)
    await assert.rejects(loadCaseIndex(),error=>error.status===503)
    globalThis.fetch=working
  }
})

test('passive bundles use GET and explicit candidate generation uses POST',async t=>{
  const methods=[]
  mock(t,async (url,options)=>{methods.push([url,options.method||'GET']);return bundleMock()(url)})
  await loadCaseBundle('case')
  assert.ok(methods.every(([,method])=>method==='GET'))
  await samplingApi.generate('case')
  assert.equal(methods.at(-1)[1],'POST')
})

test('creation sends recorded evidence in one request and propagates failure',async t=>{
  const requests=[]
  mock(t,async (url,options)=>{requests.push([url,JSON.parse(options.body)]);return response({detail:'evidence insert failed'},500)})
  const payload={initial_evidence:[{value:{replicate_results:['Positive','Negative','Invalid']}}]}
  await assert.rejects(casesApi.create(payload),/evidence insert failed/)
  assert.equal(requests.length,1)
  assert.deepEqual(requests[0][1],payload)
})
