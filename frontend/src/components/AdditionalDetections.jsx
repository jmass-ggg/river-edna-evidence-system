import LocationMatcher from './LocationMatcher'

export default function AdditionalDetections({events,onChange}) {
  const update=(index,key,value)=>onChange(events.map((event,i)=>i===index?{...event,[key]:value}:event))
  return <fieldset><legend>Additional species and sampling events</legend><p>Each entry creates an independent species/site/date context with its own replicates.</p>
    {events.map((event,index)=><div className="notice" key={index}>
      <label>Additional target species {index+1}<input required value={event.taxon} onChange={e=>update(index,'taxon',e.target.value)}/></label>
      <label>Additional sampling date {index+1}<input required type="date" max={new Date().toISOString().slice(0,10)} value={event.date} onChange={e=>update(index,'date',e.target.value)}/></label>
      <label>Additional event label {index+1}<input value={event.event} onChange={e=>update(index,'event',e.target.value)}/></label>
      <label>Additional physical site {index+1}<select value={event.newSite?'new':'primary'} onChange={e=>update(index,'newSite',e.target.value==='new')}><option value="primary">Reuse primary detection site</option><option value="new">Register a new detection site</option></select></label>
      {event.newSite&&<><label>Additional site label {index+1}<input required value={event.label} onChange={e=>update(index,'label',e.target.value)}/></label>
        <label>Additional latitude {index+1}<input required type="number" step="any" value={event.latitude} onChange={e=>update(index,'latitude',e.target.value)}/></label>
        <label>Additional longitude {index+1}<input required type="number" step="any" value={event.longitude} onChange={e=>update(index,'longitude',e.target.value)}/></label>
        <LocationMatcher latitude={event.latitude} longitude={event.longitude} onChange={(latitude,longitude)=>onChange(events.map((item,i)=>i===index?{...item,latitude,longitude,confirmed:false}:item))} onConfirmed={reach=>onChange(events.map((item,i)=>i===index?{...item,reach,confirmed:true}:item))}/>
        <p>{event.confirmed?`Reviewed reach ${event.reach}`:'Review and confirm the geographic match before submitting.'}</p></>}
      <label>Additional replicate results {index+1}<input placeholder="Positive, Negative, Invalid" value={event.replicates} onChange={e=>update(index,'replicates',e.target.value)}/></label>
      <label>Additional observation source {index+1}<input required={Boolean(event.replicates.trim())} value={event.source} onChange={e=>update(index,'source',e.target.value)}/></label>
      <button type="button" className="button" onClick={()=>onChange(events.filter((_,i)=>i!==index))}>Remove additional event {index+1}</button>
    </div>)}
    <button type="button" className="button" onClick={()=>onChange([...events,{taxon:'',date:'',event:'',replicates:'',source:'',newSite:false,label:'',latitude:'',longitude:'',reach:'',confirmed:false}])}>Add species or sampling event</button>
  </fieldset>
}
