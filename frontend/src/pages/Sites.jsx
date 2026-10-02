import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import ScientificMap from '../components/ScientificMap'
import useRemoteData from '../hooks/useRemoteData'
import { demoApi } from '../services/api'

const colors={A:'#F97316',B:'#2563EB',C:'#16A34A',D:'#9333EA'}

export default function Sites() {
  const remote=useRemoteData(demoApi.map,[]); const loadedSites=(remote.data?.sites||[]).map(s=>({...s,name:`Site ${s.label}`,type:s.label==='A'?'Original detection':'Candidate sample',color:colors[s.label]}))
  const [selectedLabel,setSelectedLabel]=useState('A'); const [query,setQuery]=useState(''); const [type,setType]=useState('')
  const sites=useMemo(()=>loadedSites.filter(s=>(!type||s.type===type)&&s.name.toLowerCase().includes(query.toLowerCase())),[loadedSites,query,type])
  const selected=sites.find(s=>s.label===selectedLabel)||sites[0]
  useEffect(()=>{if(selected&&selected.label!==selectedLabel)setSelectedLabel(selected.label)},[selected,selectedLabel])
  const number=(value,digits)=>Number.isFinite(Number(value))?Number(value).toFixed(digits):'Unavailable'
  return <div className="sites-layout"><aside className="sites-list"><h1>Monitoring sites</h1><label className="search"><Search size={17}/><input placeholder="Search sites" value={query} onChange={e=>setQuery(e.target.value)}/></label><select aria-label="Site type" value={type} onChange={e=>setType(e.target.value)}><option value="">All site types</option><option>Original detection</option><option>Candidate sample</option></select><div className="site-cards">{sites.map(site=><button key={site.label} onClick={()=>setSelectedLabel(site.label)} className={selected?.label===site.label?'selected':''}><span className="site-dot" style={{background:site.color}}>{site.label}</span><span><strong>{site.name}</strong><small>{site.type}</small><small>{site.latitude.toFixed(5)}, {site.longitude.toFixed(5)}</small></span></button>)}</div></aside>
    <ScientificMap selectedSite={selected} onSelectSite={s=>setSelectedLabel(s.label)} sites={sites} mapData={remote.data}/>
    <aside className="site-details"><h1>Selected site</h1><p>Selection is synchronized across the filtered list, map, and details.</p><hr/>{selected?<><h3>{selected.name}</h3>{[['Coordinates',`${number(selected.latitude,6)}, ${number(selected.longitude,6)}`],['Site type',selected.type],['HydroRIVERS reach ID',selected.hyriv_id??'Unavailable'],['River-network distance',selected.network_distance_to_site_a_km==null?'Unavailable':`${number(selected.network_distance_to_site_a_km,3)} km`],['Associated source zones',selected.zone||'Unavailable'],['Scientific purpose',selected.selection_reason||'Unavailable'],['Related investigation','Wigger River Investigation'],['Validation',selected.validation_status||'Unavailable']].map(([k,v])=><div className="detail" key={k}><small>{k}</small><strong>{v}</strong></div>)}<footer>Source: validated Wigger preflight artifacts.</footer></>:<div className="data-state"><strong>{remote.status==='ERROR'?'Map service unavailable':'No sites match the current filters'}</strong><p>{remote.error?.message||'Clear the filters to view a validated site.'}</p></div>}</aside>
  </div>
}
