import { useCallback, useEffect, useState } from 'react'

export default function useRemoteData(loader, dependencies = []) {
  const [state,setState] = useState({ status:'LOADING', data:null, error:null })
  const reload = useCallback(async () => {
    setState(previous => ({...previous,status:'LOADING',error:null}))
    try { const data=await loader(); setState({status:Array.isArray(data)&&!data.length?'EMPTY':'READY',data,error:null}); return data }
    catch(error) { setState({status:error.status===503?'UNAVAILABLE':'ERROR',data:null,error}); return null }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies)
  useEffect(()=>{ reload() },[reload])
  return {...state,reload}
}
