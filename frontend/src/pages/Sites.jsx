import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import ScientificMap from '../components/ScientificMap'
import useRemoteData from '../hooks/useRemoteData'
import { demoApi, casesApi, samplingApi } from '../services/api'

const colors={A:'#F97316',B:'#2563EB',C:'#16A34A',D:'#9333EA'}

export default function Sites() {
  const [caseId,setCaseId]=useState('')
  const casesRemote=useRemoteData(casesApi.list,[])
  const remote=useRemoteData(()=>caseId?samplingApi.map(caseId):demoApi.map(),[caseId]); const loadedSites=(remote.data?.sites||[]).map(s=>({...s,name:caseId?s.label:`Site ${s.label}`,type:(caseId?s.site_type==='DETECTION_SITE':s.label==='A')?'Original detection':'Candidate sample',color:caseId?undefined:colors[s.label],key:s.id||s.label}))
  const [selectedLabel,setSelectedLabel]=useState('A'); const [query,setQuery]=useState(''); const [type,setType]=useState('')
  const sites=useMemo(()=>loadedSites.filter(s=>(!type||s.type===type)&&s.name.toLowerCase().includes(query.toLowerCase())),[loadedSites,query,type])
  const selected=sites.find(s=>s.key===selectedLabel)||sites[0]
  useEffect(()=>{if(selected&&selected.key!==selectedLabel)setSelectedLabel(selected.key)},[selected,selectedLabel])
  const number=(value,digits)=>Number.isFinite(Number(value))?Number(value).toFixed(digits):'Unavailable'
  return <div className="sites-layout"><aside className="sites-list"><h1>Monitoring sites</h1><p>Select an investigation to view its reusable detection and sampling sites.</p><label>Site investigation<select aria-label="Site investigation" value={caseId} onChange={event=>{setCaseId(event.target.value);setSelectedLabel('')}}><option value="">Frozen Wigger reference</option>{(casesRemote.data?.cases||[]).map(record=><option key={record.id} value={record.id}>{record.metadata?.name||'Unnamed investigation'}</option>)}</select></label><label className="search"><Search size={17}/><input placeholder="Search sites" value={query} onChange={e=>setQuery(e.target.value)}/></label><select aria-label="Site type" value={type} onChange={e=>setType(e.target.value)}><option value="">All site types</option><option>Original detection</option><option>Candidate sample</option></select><div className="site-cards">{sites.map(site=><button key={site.key} onClick={()=>setSelectedLabel(site.key)} className={selected?.key===site.key?'selected':''}><span className="site-dot" style={{background:site.color}}>{site.label}</span><span><strong>{site.name}</strong><small>{site.type}</small><small>{site.latitude.toFixed(5)}, {site.longitude.toFixed(5)}</small></span></button>)}</div></aside>
    <ScientificMap selectedSite={selected} onSelectSite={s=>setSelectedLabel(s.key)} sites={sites} mapData={remote.data}/>
    <aside className="site-details"><h1>Selected site</h1><p>Selection is synchronized across the filtered list, map, and details.</p><hr/>{selected?<><h3>{selected.name}</h3>{[['Coordinates',`${number(selected.latitude,6)}, ${number(selected.longitude,6)}`],['Site type',selected.type],['HydroRIVERS reach ID',selected.hyriv_id??'Unavailable'],['River-network distance',selected.network_distance_to_site_a_km==null?'Unavailable':`${number(selected.network_distance_to_site_a_km,3)} km`],['Associated source zones',selected.zone||'Unavailable'],['Scientific purpose',selected.selection_reason||'Unavailable'],['Related investigation',caseId?(casesRemote.data?.cases||[]).find(record=>record.id===caseId)?.metadata?.name||'Unnamed investigation':'Wigger River Investigation'],['Validation',selected.validation_status||'Unavailable']].map(([k,v])=><div className="detail" key={k}><small>{k}</small><strong>{v}</strong></div>)}<footer>Source: validated Wigger preflight artifacts.</footer></>:<div className="data-state"><strong>{(remote.status==='ERROR'||remote.status==='UNAVAILABLE')?'Map service unavailable':'No sites match the current filters'}</strong><p>{remote.error?.message||'Clear the filters to view a validated site.'}</p></div>}</aside>
  </div>
}
