import { Expand, Layers3, Map as MapIcon, Minus, Plus, RotateCcw } from 'lucide-react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useMemo, useRef, useState } from 'react'

const colors={A:'#F97316',B:'#2563EB',C:'#16A34A',D:'#9333EA',Z1:'#38bdf8',Z2:'#34d399',Z3:'#a78bfa'}
const emptyCollection={type:'FeatureCollection',features:[]}
const mapStyle={version:8,sources:{basemap:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,attribution:'© OpenStreetMap contributors'}},layers:[{id:'background',type:'background',paint:{'background-color':'#e8f0ed'}},{id:'basemap',type:'raster',source:'basemap',paint:{'raster-opacity':.78}}]}
function coordinates(value,result=[]){if(!Array.isArray(value))return result;if(typeof value[0]==='number'&&typeof value[1]==='number')result.push(value);else value.forEach(item=>coordinates(item,result));return result}

export default function ScientificMap({ compact=false, selectedSite, onSelectSite, onSelectLocation, sites=null, title='River network', mapData=null, error=null, onRetry }) {
  const locationCallback=useRef(onSelectLocation)
  useEffect(()=>{locationCallback.current=onSelectLocation},[onSelectLocation])
  const containerRef=useRef(null), mapRef=useRef(null), markerRefs=useRef([]), boundsRef=useRef(null)
  const [layers,setLayers]=useState({river:true,sites:true,zones:true}), [fullscreen,setFullscreen]=useState(false), [mapSelection,setMapSelection]=useState(null), [ready,setReady]=useState(false), [basemapFailed,setBasemapFailed]=useState(false)
  const displaySites=useMemo(()=>sites??mapData?.sites??[],[sites,mapData]), activeSite=selectedSite||mapSelection
  const available=Boolean(mapData?.available!==false&&mapData?.river_network?.features?.length)

  useEffect(()=>{
    if(!available||!containerRef.current)return undefined
    setBasemapFailed(false)
    const river=mapData.river_network||emptyCollection, zones=mapData.source_zones||emptyCollection
    const map=new maplibregl.Map({container:containerRef.current,style:mapStyle,center:[0,0],zoom:8,attributionControl:false,preserveDrawingBuffer:true})
    mapRef.current=map;map.addControl(new maplibregl.AttributionControl({compact:true}))
    map.on('error',event=>{if(event?.sourceId==='basemap'||String(event?.error?.message||'').toLowerCase().includes('tile'))setBasemapFailed(true)})
    map.on('click',event=>locationCallback.current?.({latitude:event.lngLat.lat,longitude:event.lngLat.lng}))
    map.on('load',()=>{
      map.addSource('zones',{type:'geojson',data:zones});map.addLayer({id:'zones',type:'line',source:'zones',paint:{'line-color':['match',['get','zone'],'Z1',colors.Z1,'Z2',colors.Z2,'Z3',colors.Z3,'#48b9a0'],'line-width':8,'line-opacity':.45}})
      map.addSource('river',{type:'geojson',data:river});map.addLayer({id:'river',type:'line',source:'river',paint:{'line-color':'#168bc2','line-width':3}})
      const all=[...river.features,...zones.features].flatMap(feature=>coordinates(feature.geometry?.coordinates));(mapData.sites||[]).forEach(site=>{if(Number.isFinite(Number(site.longitude))&&Number.isFinite(Number(site.latitude)))all.push([Number(site.longitude),Number(site.latitude)])})
      if(all.length){const bounds=new maplibregl.LngLatBounds(all[0],all[0]);all.slice(1).forEach(point=>bounds.extend(point));boundsRef.current=bounds;map.fitBounds(bounds,{padding:compact?45:70,maxZoom:14,duration:0})}
      setReady(true)
    })
    return ()=>{setReady(false);mapRef.current=null;map.remove()}
  },[available,mapData,compact])

  useEffect(()=>{
    const map=mapRef.current;if(!map||!ready)return undefined
    markerRefs.current.forEach(({marker})=>marker.remove())
    markerRefs.current=displaySites.flatMap(site=>{const longitude=Number(site.longitude),latitude=Number(site.latitude);if(!Number.isFinite(longitude)||!Number.isFinite(latitude))return [];const label=String(site.label||'•').replace(/^Site\s+/,'');const element=document.createElement('button');element.type='button';element.className='maplibre-site-marker';element.textContent=label.length>3?label.slice(0,2):label;element.title=site.label;element.setAttribute('aria-label',`Select ${site.label||'sampling site'}`);element.style.background=site.color||colors[label]||stableSiteColor(site.id||site.label);element.addEventListener('click',()=>{setMapSelection(site);onSelectSite?.(site)});const marker=new maplibregl.Marker({element}).setLngLat([longitude,latitude]).addTo(map);return [{marker,element,site}]})
    return ()=>{markerRefs.current.forEach(({marker})=>marker.remove());markerRefs.current=[]}
  },[displaySites,onSelectSite,ready])

  useEffect(()=>{const map=mapRef.current;if(!map||!ready)return;for(const id of ['river','zones'])if(map.getLayer(id))map.setLayoutProperty(id,'visibility',layers[id]?'visible':'none');markerRefs.current.forEach(({element})=>{element.hidden=!layers.sites})},[layers,ready])
  useEffect(()=>{markerRefs.current.forEach(({element,site})=>element.classList.toggle('selected',Boolean(activeSite&&(site.id&&activeSite.id?site.id===activeSite.id:site.label===activeSite.label))))},[activeSite,ready])
  useEffect(()=>{mapRef.current?.resize()},[fullscreen])
  const selectSite=site=>{setMapSelection(site);onSelectSite?.(site)}
  const reset=()=>{if(boundsRef.current)mapRef.current?.fitBounds(boundsRef.current,{padding:compact?45:70,maxZoom:14})}
  return <div className={`scientific-map ${compact?'compact':''} ${fullscreen?'map-fullscreen':''}`}>
    <div className="map-title"><h2>{title}</h2><span className={`availability ${available?'verified':''}`}>{available?(basemapFailed?'Basemap unavailable · scientific overlays remain':'Verified HydroRIVERS geometry · EPSG:4326'):'Verified geographical data not loaded'}</span></div>
    {available&&<div className="map-tools"><button aria-label="Zoom in" onClick={()=>mapRef.current?.zoomIn()}><Plus/></button><button aria-label="Zoom out" onClick={()=>mapRef.current?.zoomOut()}><Minus/></button><button aria-label="Reset map view" onClick={reset}><RotateCcw/></button><button aria-label="Toggle fullscreen" aria-pressed={fullscreen} onClick={()=>setFullscreen(!fullscreen)}><Expand/></button></div>}
    {available?<div ref={containerRef} className="maplibre-canvas" role="img" aria-label="Verified river network and investigation sampling sites"/>:<div className="map-empty"><MapIcon size={46}/><strong>Geographical data unavailable</strong><p>{error?.message||mapData?.unavailable_reason||'No verified river geometry is linked to this investigation.'}</p>{error&&onRetry&&<button className="button" onClick={onRetry}>Retry map request</button>}</div>}
    {available&&<PrintMap mapData={mapData} sites={displaySites}/>} 
    {activeSite&&<div className="map-popup" role="status"><strong>{activeSite.name||activeSite.label||'Sampling site'}</strong><span>Reach {activeSite.hyriv_id}</span><small>{Number(activeSite.latitude).toFixed(5)}, {Number(activeSite.longitude).toFixed(5)}</small></div>}
    {displaySites.length>0&&<div className="site-key" aria-label="Site legend">{displaySites.map(site=><button key={site.id||site.label} className={activeSite&&(activeSite.id&&site.id?activeSite.id===site.id:activeSite.label===site.label)?'selected':''} onClick={()=>selectSite(site)}><span style={{background:site.color||colors[String(site.label).replace(/^Site\s+/,'')]||stableSiteColor(site.id||site.label)}}>{String(site.label||'•').replace(/^Site\s+/,'')}</span>{site.name||site.label}</button>)}</div>}
    {available&&<div className="layer-control"><strong><Layers3 size={14}/> Layers</strong>{Object.entries(layers).map(([key,value])=><label key={key}><input type="checkbox" checked={value} onChange={()=>setLayers({...layers,[key]:!value})}/>{key==='river'?'River network':key==='sites'?'Sites':'Source zones'}</label>)}</div>}
  </div>
}

function PrintMap({mapData,sites}){const river=mapData.river_network?.features||[],zones=mapData.source_zones?.features||[],all=[...river,...zones].flatMap(feature=>coordinates(feature.geometry?.coordinates));sites.forEach(site=>{if(Number.isFinite(Number(site.longitude))&&Number.isFinite(Number(site.latitude)))all.push([Number(site.longitude),Number(site.latitude)])});if(!all.length)return null;const xs=all.map(point=>point[0]),ys=all.map(point=>point[1]),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys),dx=maxX-minX||1,dy=maxY-minY||1;const point=([x,y])=>[35+(x-minX)/dx*930,120+(maxY-y)/dy*525];const paths=geometry=>{const groups=geometry?.type==='LineString'?[geometry.coordinates]:geometry?.type==='MultiLineString'?geometry.coordinates:[];return groups.map(line=>line.map((value,index)=>`${index?'L':'M'}${point(value).join(' ')}`).join(' ')).join(' ')};return <svg className="map-print-fallback" viewBox="0 0 1000 700" aria-hidden="true"><rect width="1000" height="700" fill="#e8f0ed"/>{zones.map((feature,index)=><path key={`z${index}`} d={paths(feature.geometry)} fill="none" stroke={colors[feature.properties?.zone]||'#48b9a0'} strokeWidth="10" opacity=".45"/>)}{river.map((feature,index)=><path key={`r${index}`} d={paths(feature.geometry)} fill="none" stroke="#168bc2" strokeWidth="3"/>)}{sites.map(site=>{const [x,y]=point([Number(site.longitude),Number(site.latitude)]),label=String(site.label||'•').replace(/^Site\s+/,'');return <g key={site.id||site.label} transform={`translate(${x} ${y})`}><circle r="14" fill={site.color||colors[label]||stableSiteColor(site.id||site.label)} stroke="#fff" strokeWidth="3"/><text y="4" fill="#fff" fontSize="10" fontWeight="700" textAnchor="middle">{label}</text></g>})}</svg>}

function stableSiteColor(identifier){const hash=Array.from(String(identifier||'site')).reduce((sum,char)=>(sum*31+char.charCodeAt(0))>>>0,0);return `hsl(${hash%360} 60% 42%)`}
