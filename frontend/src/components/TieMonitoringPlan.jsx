import { useState } from 'react'

function tieAlternatives(decision, comparison, sites, labels) {
  if (decision?.status !== 'TIE') return []
  const pairs=labels.flatMap((left,index)=>labels.slice(index+1).map(right=>[left,right]))
  return (decision.recommended_site_ids||[]).map(id=>{
    const candidate=comparison?.candidates?.find(item=>item.site_id===id)
    const site=sites.find(item=>item.id===id)
    const distinguished=candidate?.distinguished_hypothesis_pairs
    return {id,...site,...candidate,
      label:candidate?.label||site?.label||`Generated reach ${candidate?.hyriv_id??'unavailable'}`,
      distinguished,
      coordinateSource:candidate?.latitude!=null&&candidate?.longitude!=null?'Persisted decision coordinates':
        site?.latitude!=null?'Current registered coordinates; historical coordinates unavailable':'Coordinates unavailable',
      unresolved:Array.isArray(distinguished)?pairs.filter(pair=>!distinguished.some(other=>pair.every(label=>other.includes(label)))):null,
    }
  })
}

export default function TieMonitoringPlan({decision,comparison,sites=[],labels=[],evidence=[],busy=false,onSubmit}) {
  const alternatives=tieAlternatives(decision,comparison,sites,labels)
  const initial={site_id:'',source:'',accessibility:'',field_restrictions:'',practical_observations:'',researcher_selected:true}
  const [form,setForm]=useState(initial)
  if (!alternatives.length) return null
  const notes=evidence.filter(item=>item.evidence_type==='sampling_field_plan'&&item.value?.decision_id===decision.id)
  const comparisonAvailable=alternatives.every(candidate=>typeof candidate.pair_separation_score==='number'&&Array.isArray(candidate.distinguished))
  async function submit(event){event.preventDefault();const {source,...value}=form;if(await onSubmit({
    evidence_type:'sampling_field_plan',source,value:{...value,decision_id:decision.id},
    provenance:{entry_method:'manual',purpose:'practical field planning'},quality:'USER_REPORTED',
  }))setForm(initial)}
  return <div className="tie-monitoring-plan"><h3>TIE monitoring alternatives</h3>
    <p>{comparisonAvailable?'These alternatives share the best pair-separation score under the persisted topology criterion. None has a superior scientific score.':'The stored decision is TIE. Its comparison is incomplete, so the original scoring cannot be independently checked from these records.'} Practical field choices do not change the TIE or its scores.</p>
    {alternatives.map(candidate=><div key={candidate.id} className="notice"><h4>{candidate.label}</h4>
      <p>Reach: {candidate.hyriv_id??'Unavailable'} · {candidate.coordinateSource}: {candidate.latitude!=null&&candidate.longitude!=null?`${candidate.latitude}, ${candidate.longitude}`:'Unavailable'} · Pair-separation score: {candidate.pair_separation_score??'Unavailable'}</p>
      <p>Uncertainty this alternative could help resolve: {candidate.distinguished?.length?candidate.distinguished.map(pair=>pair.join(' vs ')).join('; '):'Historical comparison unavailable'}. This describes ideal binary discrimination; actual sample outcomes and detection probability remain unknown.</p>
      <p>Unresolved hypothesis pairs at this alternative: {candidate.unresolved?.map(pair=>pair.join(' vs ')).join('; ')|| (candidate.unresolved?'None under the ideal topology criterion':'Unavailable')}.</p>
    </div>)}
    <p>Recommended field observations: record access and permissions, restrictions, actual sample location and time, assay, controls, replicate results, and any practical departure from the proposed reach.</p>
    {notes.map(item=><div className="notice" key={item.id}><strong>{item.value.researcher_selected?'Researcher-selected field site':'Practical observation'}: reach {item.value.hyriv_id}</strong><p>{item.value.researcher_selected?'This is a researcher field choice; scientific preference remains tied. ':''}Recorded by {item.source}.</p><p>Accessibility: {item.value.accessibility||'Not recorded'}; restrictions: {item.value.field_restrictions||'Not recorded'}; practical observations: {item.value.practical_observations||'Not recorded'}.</p></div>)}
    {onSubmit&&<form className="follow-up-form" onSubmit={submit}><h4>Record practical field choice</h4>
      <label>Monitoring alternative<select required value={form.site_id} onChange={e=>setForm({...form,site_id:e.target.value})}><option value="">Select alternative</option>{alternatives.filter(candidate=>candidate.hyriv_id!=null).map(candidate=><option key={candidate.id} value={candidate.id}>{candidate.label}</option>)}</select></label>
      <input required aria-label="Researcher or team" placeholder="Researcher or team" value={form.source} onChange={e=>setForm({...form,source:e.target.value})}/>
      {['accessibility','field_restrictions','practical_observations'].map(key=><label key={key}>{key.replaceAll('_',' ')}<textarea aria-label={key.replaceAll('_',' ')} value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})}/></label>)}
      <label><input type="checkbox" checked={form.researcher_selected} onChange={e=>setForm({...form,researcher_selected:e.target.checked})}/>Researcher-selected field site</label>
      <button className="button" disabled={busy||!form.site_id||![form.accessibility,form.field_restrictions,form.practical_observations].some(note=>note.trim())}>Save field choice</button>
    </form>}
  </div>
}
