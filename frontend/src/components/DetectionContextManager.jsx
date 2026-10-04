import { useState } from 'react'
import { detectionApi } from '../services/api'
import LocationMatcher from './LocationMatcher'

export default function DetectionContextManager({caseId,contexts=[],sites=[],onSaved}) {
  const [form,setForm]=useState({taxon:'',site:'',label:'',latitude:'',longitude:'',reach:'',confirmed:false,date:'',event:'',replicates:'',source:''}),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const update=(key,value)=>setForm(previous=>({...previous,[key]:value}))
  async function save(event){event.preventDefault();setBusy(true);setError('');try{
    const species=await detectionApi.addSpecies(caseId,{taxon:form.taxon})
    const site=form.site?{id:form.site}:await detectionApi.addSite(caseId,{label:form.label,latitude:Number(form.latitude),longitude:Number(form.longitude),hyriv_id:Number(form.reach),confirmed:form.confirmed})
    const context=await detectionApi.addContext(caseId,{species_id:species.id,site_id:site.id,sampled_on:form.date,event_label:form.event})
    if(form.replicates.trim())await detectionApi.observe(caseId,context.id,{replicate_results:form.replicates.split(',').map(value=>value.trim()),source:form.source,provenance:{entry_method:'manual',observation_class:'USER_ENTERED'}})
    await onSaved(context.id);setForm({...form,replicates:'',event:''})
  }catch(error){setError(`${error.message}. Successfully registered species or sites remain available; context registration is incremental.`)}finally{setBusy(false)}}
  return <details className="notice"><summary>Add species or sampling context</summary><form className="follow-up-form" onSubmit={save}>
    <label>Target species<input required value={form.taxon} onChange={event=>update('taxon',event.target.value)} list="registered-taxa"/></label><datalist id="registered-taxa">{[...new Set(contexts.map(context=>context.target_taxon))].map(taxon=><option key={taxon}>{taxon}</option>)}</datalist>
    <label>Physical detection site<select value={form.site} onChange={event=>update('site',event.target.value)}><option value="">Register new physical site</option>{sites.filter(site=>site.site_type==='DETECTION_SITE').map(site=><option key={site.id} value={site.id}>{site.label} · reach {site.hyriv_id}</option>)}</select></label>
    {!form.site&&<><label>Site label<input required value={form.label} onChange={event=>update('label',event.target.value)}/></label><label>WGS84 latitude<input required type="number" step="any" value={form.latitude} onChange={event=>setForm({...form,latitude:event.target.value,confirmed:false})}/></label><label>WGS84 longitude<input required type="number" step="any" value={form.longitude} onChange={event=>setForm({...form,longitude:event.target.value,confirmed:false})}/></label>
      <LocationMatcher latitude={form.latitude} longitude={form.longitude} onChange={(latitude,longitude)=>setForm({...form,latitude,longitude,confirmed:false})} onConfirmed={reach=>setForm({...form,reach,confirmed:true})}/>
      <p>{form.confirmed?`Reviewed reach ${form.reach}`:'A matching alternative must be reviewed and confirmed.'}</p></>}
    <label>Sampling date<input required type="date" max={new Date().toISOString().slice(0,10)} value={form.date} onChange={event=>update('date',event.target.value)}/></label>
    <label>Sampling event label<input value={form.event} onChange={event=>update('event',event.target.value)}/></label>
    <label>Replicate results (comma separated)<input placeholder="Positive, Negative, Invalid" value={form.replicates} onChange={event=>update('replicates',event.target.value)}/></label>
    <label>Observation source<input required={Boolean(form.replicates.trim())} value={form.source} onChange={event=>update('source',event.target.value)}/></label>
    {error&&<p className="error-banner">{error}</p>}<button className="button" disabled={busy||(!form.site&&!form.confirmed)}>Register detection context</button>
  </form></details>
}
