# Browser Verification Report

## Result

The eDNA Evidence Investigator completed automated browser verification in a
real Chromium browser. The complete Wigger workflow, isolated investigation
creation, responsive layouts, API failure states, and print-to-PDF report were
exercised through the running FastAPI and Vite applications.

## Tested environment

| Component | Tested value |
| --- | --- |
| Operating system | Linux 7.0.0-34-generic, x86_64 |
| Browser | Chromium 153.0.8010.12, headless |
| Automation | Playwright 1.63.0 |
| Frontend | React 18, Vite 6 |
| Backend | Python 3.12, FastAPI |
| Browser database | Isolated temporary SQLite database |
| Normal application database | PostgreSQL configuration unchanged |

The Playwright runner started a real Uvicorn backend and Vite development
server on loopback interfaces. The browser received API responses over HTTP,
including CORS preflight requests. Test records existed only in the isolated
browser-test database, which is recreated for each run.

## Viewports

- Desktop: 1440 × 900
- Smaller desktop: 1280 × 800
- Tablet: 768 × 1024
- Mobile: 390 × 844

## Pages and workflows tested

### Homepage

- Header and footer navigation
- Start Investigation and Explore Wigger Demo links
- Two maps rendered from `GET /demo/wigger/map`
- Verified river geometry, sites, layers, CRS label, and responsive layout
- No unsupported scientific result added to the marketing content

### Dashboard and investigations

- Persisted active-case count
- Cases without a persisted scientific decision
- Follow-up sample count
- `UNDER_REVIEW` workflow count
- Workflow and scientific-decision status displayed separately
- Search, workflow filter, decision filter, date field, and Clear Filters
- Opening persisted investigations
- Backend-unavailable state

### Investigation creation

- Required-field validation
- Coordinate limits
- Future-date validation
- Required verified HydroRIVERS reach
- Unknown reach rejection without database writes
- Valid isolated record creation using reach 20446064
- Optional recorded replicate result submission
- Navigation to the created case and appearance in investigation search

### Wigger investigation workspace

- S1 and observation index 4
- *Fredericella sultana*
- 2014-06-25
- `1.2983219767633366e-17 mol/L`
- `DETECTED`
- 49 rendered HydroRIVERS reaches
- Sites A, B, C, and D
- Zones Z1, Z2, and Z3
- UNKNOWN historical-measurement compatibility
- Directed-connectivity evidence results
- Generated candidates and distinguished hypothesis pairs
- Actual `TIE` decision
- Persisted decision trace and `sampling.topology_pair_separation.v1`
- Detection Evidence, Possible Sources, Sampling Decision, and Next Steps
- Follow-up registration form remains explicit about required real metadata

### Map interactions

- Zoom in and out
- Reset view
- Fullscreen entry and exit
- River, site, and source-zone layers
- Mouse and keyboard marker selection
- Marker detail popup
- Site legend
- Site filtering and synchronized list, marker, and details selection

### Reports

- Table-of-contents navigation
- Historical observation and unavailable replicate/assay metadata
- Evidence source, rule, compatibility, explanation, and quality
- Hydrological totals and limitations
- Verified map
- Candidate comparison and pair-separation scores
- Actual decision and rationale
- Follow-up interpretation
- Environmental and One Health boundaries
- Provenance, assumptions, and limitations
- Browser PDF generation with navigation and controls excluded

The generated PDF is [WIGGER_BROWSER_REPORT.pdf](browser_artifacts/WIGGER_BROWSER_REPORT.pdf).
It is a four-page A4 document. All pages were rendered to PNG and visually
inspected for clipping, table readability, map inclusion, and page breaks.

### Failure handling

- Backend request aborted
- Invalid case identifier
- Map endpoint returning HTTP 500
- Missing persisted decision handled as `NOT_EVALUATED` without a trace 404
- Empty and unavailable scientific data remain explicit

## Screenshots

The final screenshots are stored in `browser_artifacts/screenshots/`:

| Page | Desktop 1440 | Desktop 1280 | Tablet | Mobile |
| --- | --- | --- | --- | --- |
| Homepage | [PNG](browser_artifacts/screenshots/home-desktop-1440.png) | [PNG](browser_artifacts/screenshots/home-desktop-1280.png) | [PNG](browser_artifacts/screenshots/home-tablet.png) | [PNG](browser_artifacts/screenshots/home-mobile.png) |
| Wigger workspace | [PNG](browser_artifacts/screenshots/workspace-desktop-1440.png) | [PNG](browser_artifacts/screenshots/workspace-desktop-1280.png) | [PNG](browser_artifacts/screenshots/workspace-tablet.png) | [PNG](browser_artifacts/screenshots/workspace-mobile.png) |
| Sites | [PNG](browser_artifacts/screenshots/sites-desktop-1440.png) | [PNG](browser_artifacts/screenshots/sites-desktop-1280.png) | [PNG](browser_artifacts/screenshots/sites-tablet.png) | [PNG](browser_artifacts/screenshots/sites-mobile.png) |
| Report | [PNG](browser_artifacts/screenshots/report-desktop-1440.png) | [PNG](browser_artifacts/screenshots/report-desktop-1280.png) | [PNG](browser_artifacts/screenshots/report-tablet.png) | [PNG](browser_artifacts/screenshots/report-mobile.png) |

No canonical approved screenshot set was present in the repository for pixel
comparison. The existing visual identity, typography, colors, component
structure, and navigation model were retained.

## Confirmed defects and fixes

| Priority | Reproduction and root cause | Fix |
| --- | --- | --- |
| P0 | New-case creation accepted any positive reach number because the case route did not query the loaded hydrological graph. | Validate the supplied reach through `HydrologyEngine` before creating either the site or case. |
| P1 | Initial case loading requested a decision trace before a decision existed, producing a browser-console 404. | Add a nullable latest-decision endpoint and request the trace only when a persisted decision exists. |
| P1 | Homepage map panels were static placeholders despite the validated map endpoint being available. | Render the shared scientific map with the real Wigger response. |
| P1 | Investigation workflow, decision, and date controls did not affect the list. | Apply all filters to enriched persisted case records and reset every field through Clear Filters. |
| P1 | Dashboard decision and follow-up metrics were placeholders. | Derive counts from persisted decisions, follow-up samples, and workflow states. |
| P1 | Filtering the Sites list could leave a hidden site selected and markers were not filtered. | Derive selection from the filtered collection and render only filtered markers. |
| P1 | Map reset, keyboard marker activation, and marker details were missing. | Add reset, keyboard handling, a synchronized detail popup, and explicit fullscreen state. |
| P1 | The browser report omitted observation index, readable detection-site identity, follow-up interpretation, network totals, detailed evidence, and supported One Health context. | Aggregate those existing API fields in the report without duplicating scientific calculations. |
| P2 | Report tables expanded the document beyond tablet and mobile viewports. | Constrain grid children and use contained horizontal table scrolling on narrow screens. |
| P2 | Mobile map legend and layer controls overlapped. | Separate their bottom positions and make the legend horizontally scrollable. |
| P2 | Printed output split the decision unnecessarily and initially produced a sparse fifth page. | Add print-specific break rules and reduce the printed map height; final output is four readable A4 pages. |
| P2 | The persisted demo lacked a stable human-readable name. | Set `Wigger River Investigation` while retaining the existing idempotent demo key. |

## Automated results

### Baseline before browser fixes

- Backend: 134 passed
- Frontend ESLint: passed
- Frontend build: passed

### Final

- Playwright: **18 passed, 6 skipped, 0 failed**
- The six skips are desktop-only creation, PDF, and failure-path scenarios
  intentionally omitted from the other three viewport projects.
- Backend Pytest: **136 passed, 0 failed, 0 skipped**
- Frontend ESLint: **passed**
- Frontend production build: **passed**
- PDF generation and visual inspection: **passed**, four A4 pages

The backend reports 143 deprecation and SQLite teardown warnings. They do not
represent test failures; the existing UTC datetime and cyclic foreign-key
test-fixture warnings remain for later maintenance.

## Scientific reproducibility

`./venv/bin/python scripts/reproduce_wigger.py --isolated` completed with
`PASS` and decision `TIE` after the browser fixes.

The normalized output SHA-256 was unchanged before and after this work:

`55d0fb847f53f49efc8c44ab80b5ea1170fab529b45d5bb12f3524db3eb1d634`

The historical observation, 49-reach/145.23 km hydrology result, candidate
signatures, pair-separation scores, Sites B/C/D tie, and decision trace did not
change.

## Remaining limitations

- Browser testing used an isolated SQLite database. PostgreSQL-specific
  deployment operations were outside this functional browser run.
- External environmental providers were not invoked, so no environmental
  observations were added.
- The application has no scientific review or approval workflow; reports
  correctly remain Draft.
- The browser test uses a controlled isolated case to verify creation. It is
  not a historical observation and is deleted with the browser-test database.
