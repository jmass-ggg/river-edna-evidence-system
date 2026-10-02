import { Expand, Layers3, Map, Minus, Plus, RotateCcw } from 'lucide-react'
import { useState } from 'react'

const colors={A:'#F97316',B:'#2563EB',C:'#16A34A',D:'#9333EA',Z1:'#38bdf8',Z2:'#34d399',Z3:'#a78bfa'}
const lines=geometry=>geometry?.type==='LineString'?[geometry.coordinates]:geometry?.type==='MultiLineString'?geometry.coordinates:[]

export default function ScientificMap({ compact = false, selectedSite, onSelectSite, sites = null, title = 'Wigger River network', mapData = null }) {
  const [layers, setLayers] = useState({ river: true, sites: true, zones: true }), [zoom,setZoom]=useState(1), [fullscreen,setFullscreen]=useState(false), [mapSelection,setMapSelection]=useState(null)
  const coordinates=mapData?.river_network?.features?.flatMap(f=>lines(f.geometry).flat())||[]
  const xs=coordinates.map(c=>c[0]), ys=coordinates.map(c=>c[1]); const bounds=coordinates.length?{minX:Math.min(...xs),maxX:Math.max(...xs),minY:Math.min(...ys),maxY:Math.max(...ys)}:null
  const point=([x,y])=>bounds?[40+(x-bounds.minX)/(bounds.maxX-bounds.minX)*920,40+(bounds.maxY-y)/(bounds.maxY-bounds.minY)*620]:[0,0]
  const pathFor=geometry=>lines(geometry).map(line=>line.map((c,i)=>`${i?'L':'M'}${point(c).join(' ')}`).join(' ')).join(' ')
  const width=1000/zoom,height=700/zoom,viewBox=`${(1000-width)/2} ${(700-height)/2} ${width} ${height}`
  const displaySites=sites??mapData?.sites??[], activeSite=selectedSite||mapSelection
  const selectSite=site=>{setMapSelection(site);onSelectSite?.(site)}
  return <div className={`scientific-map ${compact ? 'compact' : ''} ${fullscreen?'map-fullscreen':''}`}>
    <div className="map-title"><h2>{title}</h2><span className={`availability ${mapData?'verified':''}`}>{mapData?'Verified preflight geometry · EPSG:4326':'Verified geographical data not loaded'}</span></div>
    <div className="map-tools"><button aria-label="Zoom in" onClick={()=>setZoom(Math.min(4,zoom*1.25))}><Plus/></button><button aria-label="Zoom out" onClick={()=>setZoom(Math.max(1,zoom/1.25))}><Minus/></button><button aria-label="Reset map view" onClick={()=>setZoom(1)}><RotateCcw/></button><button aria-label="Toggle fullscreen" aria-pressed={fullscreen} onClick={()=>setFullscreen(!fullscreen)}><Expand/></button></div>
    {mapData&&bounds?<svg className="geo-svg" viewBox={viewBox} role="img" aria-label="Validated Wigger river network and sampling sites">
      {layers.zones&&mapData.source_zones.features.map((f,i)=><path key={`z${i}`} d={pathFor(f.geometry)} className="zone-reach" style={{stroke:colors[f.properties?.zone]||'#48b9a0'}}/>)}
      {layers.river&&mapData.river_network.features.map((f,i)=><path key={`r${i}`} d={pathFor(f.geometry)} className="river-reach"/>)}
      {layers.sites&&displaySites.map(site=>{const [x,y]=point([site.network_longitude,site.network_latitude]);return <g key={site.label} aria-label={`Select Site ${site.label}`} transform={`translate(${x} ${y})`} onClick={()=>selectSite(site)} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectSite(site)}}} className="map-marker" role="button" tabIndex="0"><circle r={activeSite?.label===site.label?15:12} fill={colors[site.label]}/><text y="4">{site.label}</text></g>})}
    </svg>:<div className="map-empty"><Map size={46}/><strong>Geographical data unavailable</strong><p>River geometry, site coordinates, and source-zone boundaries will appear after verified backend data is connected.</p></div>}
    {activeSite&&<div className="map-popup" role="status"><strong>{activeSite.name||`Site ${activeSite.label}`}</strong><span>Reach {activeSite.hyriv_id}</span><small>{Number(activeSite.latitude).toFixed(5)}, {Number(activeSite.longitude).toFixed(5)}</small></div>}
    {displaySites.length > 0 && <div className="site-key" aria-label="Site legend">{displaySites.map(site => <button key={site.label} className={activeSite?.label === site.label ? 'selected' : ''} onClick={() => selectSite(site)}><span style={{background: site.color||colors[site.label]}}>{site.label}</span>{site.name||`Site ${site.label}`}</button>)}</div>}
    <div className="layer-control"><strong><Layers3 size={14}/> Layers</strong>{Object.entries(layers).map(([key,value]) => <label key={key}><input type="checkbox" checked={value} onChange={() => setLayers({...layers,[key]:!value})}/>{key === 'river' ? 'River network' : key === 'sites' ? 'Sites' : 'Source zones'}</label>)}</div>
  </div>
}
