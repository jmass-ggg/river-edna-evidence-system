export const emptyCollection = Object.freeze({ status: 'EMPTY', items: [] })

export const siteShells = Object.freeze([
  { label: 'A', name: 'Site A', type: 'Original detection', color: '#F97316' },
  { label: 'B', name: 'Site B', type: 'Candidate sample', color: '#2563EB' },
  { label: 'C', name: 'Site C', type: 'Candidate sample', color: '#16A34A' },
  { label: 'D', name: 'Site D', type: 'Candidate sample', color: '#9333EA' },
])

export const reportSections = [
  ['summary', 'Investigation Summary'], ['detection', 'Original eDNA Detection'],
  ['evidence', 'Evidence Assessment'], ['hydrology', 'Hydrological Investigation'],
  ['map', 'Investigation Map'], ['sources', 'Competing Source Explanations'],
  ['candidates', 'Candidate Sampling Comparison'], ['decision', 'Sampling Decision and Scientific Reasoning'],
  ['monitoring', 'Actionable TIE Monitoring Plan'], ['history', 'Versioned Reinvestigation History'],
  ['followup', 'Follow-up Sampling'], ['context', 'Environmental and One Health Context'], ['next', 'Next Steps'], ['data', 'Data Sources'],
  ['assumptions', 'Assumptions'], ['limitations', 'Limitations'],
]
