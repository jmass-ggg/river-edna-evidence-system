// Audit identifiers remain in API records; normal views use readable labels.
export function userFacingText(value) {
  return String(value??'').replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi,'[audit reference]')
}
