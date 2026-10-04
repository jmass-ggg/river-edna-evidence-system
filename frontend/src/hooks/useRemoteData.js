import { useCallback, useEffect, useState, useRef } from 'react'

export default function useRemoteData(loader, dependencies = []) {
  const [state,setState] = useState({ status:'LOADING', data:null, error:null })
  const generation=useRef(0)
  const reload = useCallback(async () => {
    const request=++generation.current
    setState(previous => ({...previous,status:'LOADING',error:null}))
    try { const data=await loader(); if(request!==generation.current)return null; setState({status:Array.isArray(data)&&!data.length?'EMPTY':'READY',data,error:null}); return data }
    catch(error) { if(request!==generation.current)return null; setState({status:error.status===503?'UNAVAILABLE':'ERROR',data:null,error}); return null }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies)
  useEffect(()=>{ const counter=generation;reload();return ()=>{counter.current++} },[reload])
  return {...state,reload}
}
