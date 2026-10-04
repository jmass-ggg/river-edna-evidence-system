# Final project completion report

**Scientific-review status:** Draft  
**Verification date:** 2026-10-02

## Outcome

The current repository state is functionally verified as a reproducible research prototype for the frozen Wigger River investigation. The backend, frontend, browser workflow, deterministic reproduction, and report export passed their configured checks. The original scientific inputs, normalized output checksum, and `TIE` decision remain unchanged.

This completion status applies to software behavior and reproducibility. It does not imply that the method has been prospectively validated in the field, that it identifies the biological source, or that it improves time, cost, sampling efficiency, or accuracy.

## Evidence categories

| Category | Evidence in this repository | Boundary |
| --- | --- | --- |
| Functional verification | Automated backend, frontend, browser, API, persistence, and frozen-workflow checks | Demonstrates tested software behavior in the recorded environment. |
| Synthetic testing | Generated graph/property cases, mocked context-provider responses, and deterministic execution benchmark | Does not supply environmental measurements or field outcomes. |
| Historical observations | Carraro H001 at S1 and reviewed station records, including the 2014-06-25 *F. sultana* detections | Prior observations do not reveal counterfactual outcomes or independently establish source truth. |
| Real-world scientific validation | No prospective matched field campaign is present | Accuracy, benefit, safety, cost, and generalizability remain unvalidated. |

## Completed work

- Preserved the original historical eDNA observation and its evidence classification.
- Kept topology-only reasoning traceable and separated generated representatives from registered follow-up sites.
- Preserved the evidence-bounded One Health interpretation and Draft report status.
- Added case-scoped environmental context infrastructure without allowing contextual data to change biological evidence classifications.
- Connected historical weather to explicitly pinned ERA5 archive data with source, date, resolution, units, grid coordinates, retrieval time, missing-data reporting, and limitations.
- Kept GHSL urbanization unavailable because a reproducible raster buffer extraction is not configured.
- Added focused mocked integration coverage for weather success, missing data, invalid data, transport failure, persistence, and unchanged evidence classification.
- Added reproducible scientific-scope audits and benchmark tooling that refuse to infer benefits from missing measurements.
- Clarified the report UI's candidate-selection boundaries and One Health caveats without changing its scientific decision logic.

## Actual verification results

| Command or check | Actual result |
| --- | --- |
| `cd backend && ../venv/bin/pytest -q` | 174 passed, 149 warnings, 4.61 s |
| `cd frontend && npm run lint` | Passed |
| `cd frontend && npm run build` | Passed; 1,601 modules transformed; 1.41 s build reported by Vite |
| `cd frontend && npm run test:e2e` | 18 passed, 6 intentionally skipped; 40.3 s |
| `./venv/bin/python scripts/reproduce_wigger.py --isolated` | PASS on two consecutive clean isolated runs |
| Frozen registered-site decision | `TIE`: Site B, Site C, Site D |
| Frozen generated-candidate decision | `TIE` |
| Frozen normalized result SHA-256 | `55d0fb847f53f49efc8c44ab80b5ea1170fab529b45d5bb12f3524db3eb1d634` on both runs |

The backend warnings are currently non-failing. They identify SQLAlchemy UTC deprecations, SQLite teardown ordering around cyclic foreign keys, and a future `pytest-asyncio` default change.

## Original scientific checksums

| Input | Verified SHA-256 |
| --- | --- |
| `data_preflight/raw/carraro/eDNA_data.mat` | `9938c931402a902d686e26acca93fbc3a2cf78e061919ffebe416d7a61a536c2` |
| `data_preflight/raw/carraro/RUN_MODEL.m` | `c05f3cd49e0519029314357cb27d6c6265dd1067ff77633e2418f3b2e53b41eb` |
| `data_preflight/outputs/upstream_reaches_real.csv` | `f767d1068d7ee911a1a3cab07ff27db417858d611ae6951a629312be81ce449b` |
| `data_preflight/outputs/upstream_edges.csv` | `1811d989f680273729c2d4d24a3ad990e7a81ba7424c5336079b8f2004fcf312` |
| `data_preflight/outputs/candidate_zones_real.geojson` | `b19b025efdb5e918f340796a51f0f04d6b3adf2cbf3cc8af5e425e8289bd0368` |
| `data_preflight/outputs/candidate_sampling_sites.csv` | `8f296900d430587f01656ba9d3f82fa0ba54225d3434e74cade6ec9128f2ae59` |

## Measured benchmarks

The available measured execution benchmark is synthetic. It used 256 candidate reaches, 64 candidate sites, eight hypotheses, and 512 decision reachability checks per run on CPython 3.12.3 / Linux x86_64. After 10 warmups and 100 recorded runs:

| Operation | Median execution time |
| --- | ---: |
| Candidate generation | 0.000618741 s |
| Sampling decision | 0.000510001 s |

These figures are local software timings for deterministic generated inputs. They are not field, laboratory, end-to-end workflow, cost, savings, or biological-accuracy measurements.

The observed-workflow measurement file has no rows. The corresponding summary is `NO_MEASUREMENTS`, with no workflow statistics. No percentage improvement, cost reduction, time saving, or accuracy claim is supported.

## Historical observations and scientific interpretation

The frozen record contains the H001 *Fredericella sultana* observation at S1 on 2014-06-25 with concentration `1.2983219767633366e-17 mol/L`, recorded as detected. The reviewed station table also contains an S14 detection on that date. These are real historical observations with documented provenance.

They do not establish the organism's source zone, predict what would have been measured at Sites B, C, or D, validate binary negative outcomes, or prove that the proposed sampling strategy would outperform another strategy. The historical eDNA item correctly remains `UNKNOWN` in compatibility because no validated biological compatibility rule applies to that evidence type.

The registered follow-up decision remains `TIE` because Sites B, C, and D each have the same topology-only pair-separation score. No unique field site is selected.

## Environmental data status

| Source | Status | Scientific boundary |
| --- | --- | --- |
| GBIF occurrence search | Integrated | Occurrence context does not prove present-day presence or absence at the site. |
| ERA5 historical weather via Open-Meteo | Integrated | Gridded reanalysis is contextual, not an on-site measurement. The frozen Wigger reproduction contains no collected weather record. |
| GHSL built-up surface | Unavailable in the application | Historical tiles exist, but reproducible raster provisioning and buffer extraction are not configured. |
| Field and laboratory follow-up data | Unavailable | No prospective B/C/D outcomes, replicate series, controls, accessibility review, or measured costs are present. |

## PDF report verification

The Playwright workflow regenerated `browser_artifacts/WIGGER_BROWSER_REPORT.pdf` from the current report page after the report-content and print-style changes. The PDF was then rendered and visually reviewed for page count, clipping, overlap, map presence, decision text, Draft status, and scientific caveats. The PDF is a presentation of the current application record; it adds no new scientific evidence.

## Remaining field-validation requirements

Before scientific-review status can move beyond Draft:

1. independently confirm the station-to-reach crosswalk and candidate-site accessibility;
2. preregister the investigation objective, competing workflows, outcomes, and analysis plan;
3. collect prospective replicated samples at competing sites with blanks, controls, assay details, timestamps, and full provenance;
4. establish an independent source truth or defensible reference standard;
5. record investigator time, candidates inspected, samples and replicates, travel, field, laboratory, and analytical costs;
6. evaluate transport, decay, dilution, hydrological conditions, assay sensitivity, and false-positive/false-negative behavior;
7. validate any environmental-context rule against matched field observations before it can affect source-hypothesis status;
8. obtain external scientific review of the methods, data lineage, interpretation, and limitations.

No unsupported completion, production-readiness, publication-readiness, performance-benefit, cost-saving, or scientific-accuracy claim is retained in this report.
