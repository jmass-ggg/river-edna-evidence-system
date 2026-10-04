export default function BundleErrors({ errors={}, onRetry }) {
  const entries=Object.entries(errors).filter(([,error])=>error)
  if (!entries.length) return null
  return <div className="error-banner" role="alert">
    {entries.map(([key,error])=><p key={key}>{key}: {error.message||String(error)}</p>)}
    {onRetry&&<button className="button" onClick={onRetry}>Retry failed requests</button>}
  </div>
}
