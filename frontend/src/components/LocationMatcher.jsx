import { useEffect,useState } from 'react'
import ScientificMap from './ScientificMap'
import { demoApi,hydrologyApi } from '../services/api'

export default function LocationMatcher({latitude,longitude,onChange,onConfirmed}) {
  const [map,setMap]=useState(null),[match,setMatch]=useState(null),[selected,setSelected]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  useEffect(()=>{demoApi.map().then(setMap).catch(error=>setError(error.message))},[])
  useEffect(()=>{setMatch(null);setSelected('')},[latitude,longitude])
  async function query(){setBusy(true);setError('');try{const result=await hydrologyApi.match({latitude:Number(latitude),longitude:Number(longitude)});setMatch(result);setSelected(String(result.alternatives[0]?.hyriv_id||''))}catch(error){setError(error.message)}finally{setBusy(false)}}
  return <div className="notice"><strong>Review geographic network match</strong>
    <p>Click the map or enter WGS84 coordinates. Matching does not verify species presence or source origin.</p>
    <ScientificMap compact mapData={map} sites={[]} onSelectLocation={point=>onChange(point.latitude,point.longitude)} title="Select detection location"/>
    <button type="button" className="button" disabled={busy||latitude===''||longitude===''} onClick={query}>Match coordinates</button>
    {error&&<p className="error-banner">{error}</p>}
    {match&&<><p>Geographic match: {match.status}. Explicit researcher review is required.</p>
      <p>Screening thresholds: close ≤ {match.thresholds.close_m} m; supported ≤ {match.thresholds.maximum_m} m; ambiguity margin {match.thresholds.ambiguity_margin_m} m.</p>
      <select aria-label="Matching river alternative" value={selected} onChange={event=>setSelected(event.target.value)}><option value="">Select alternative</option>{match.alternatives.map(candidate=><option key={candidate.hyriv_id} value={candidate.hyriv_id}>Reach {candidate.hyriv_id} · {candidate.snap_distance_m.toFixed(1)} m</option>)}</select>
      <p>{match.limitations.join(' ')}</p>
      <button type="button" className="button" disabled={!selected||match.status==='UNSUPPORTED'} onClick={()=>onConfirmed(Number(selected),match)}>Confirm reviewed match</button>
    </>}
  </div>
}
