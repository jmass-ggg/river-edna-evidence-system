# Project completion report

**Status:** Draft - functional implementation verified; scientific field validation incomplete  
**Verification date:** 2026-10-02

## Scope

The repository implements a deterministic freshwater eDNA investigation workflow for the frozen Wigger example. The verified software path loads the historical H001 observation, represents competing hydrological source hypotheses, calculates topology-only candidate discrimination, records a decision trace, and exposes the investigation through the API and report UI.

This report distinguishes four forms of evidence:

| Category | What was checked | What it establishes |
| --- | --- | --- |
| Functional verification | Backend, frontend, browser, and reproducibility checks | The implemented software behaves as asserted in the tested environment. |
| Synthetic testing | Generated graphs, mocked provider responses, and timed synthetic workloads | Algorithmic properties, error handling, integration contracts, and software execution time for those fixtures. |
| Historical observations | Carraro H001 and reviewed station records | Measurements recorded at stated stations and dates, with their documented provenance. |
| Real-world scientific validation | Prospective sampling, independent source truth, field constraints, and matched workflow comparisons | Not completed. No field accuracy, efficiency, cost saving, or health outcome is established. |

## Verified implementation

The following capabilities are functionally verified:

- deterministic loading and checksum verification of the frozen Wigger inputs;
- preservation of the H001 observation at S1 on 2014-06-25;
- directed HydroRIVERS reachability and topology-only pair-separation scoring;
- separation of generated representative reaches from registered follow-up Sites B, C, and D;
- preservation of `UNKNOWN` compatibility for the historical eDNA observation where no validated rule applies;
- API persistence and retrieval, report rendering, error presentation, and responsive browser behavior;
- GBIF occurrence context and ERA5 historical-weather adapters with provenance and missing-data handling;
- explicit unavailability of GHSL urbanization until a reproducible raster extraction is configured.

The One Health report text remains evidence-bounded. It identifies literature-linked monitoring relevance without asserting local parasite presence, fish infection, disease, or human-health effects.

## Verification results

Executed on 2026-10-02:

| Check | Result |
| --- | --- |
| Complete backend suite | 174 passed; 149 warnings |
| Frontend ESLint | Passed |
| Frontend production build | Passed; 1,601 modules transformed |
| Playwright suite | 18 passed; 6 intentionally skipped by viewport configuration |
| Frozen Wigger isolated reproduction, run 1 | PASS; registered decision `TIE` |
| Frozen Wigger isolated reproduction, run 2 | PASS; registered decision `TIE` |
| Reproduced JSON stability | Byte-identical SHA-256 `55d0fb847f53f49efc8c44ab80b5ea1170fab529b45d5bb12f3524db3eb1d634` |

Warnings were not treated as failures. They consist mainly of SQLAlchemy UTC deprecations, SQLite foreign-key teardown ordering, and an unset future `pytest-asyncio` fixture-loop default. They should be addressed before dependency upgrades but did not change these results.

## Scientific result retained

The registered follow-up decision remains **TIE: Site B, Site C, Site D**. Each site has the same topology-only pair-separation score. This is a deterministic property of the implemented, validated network representation; it is not a biological source determination or a unique sampling recommendation.

All six source checksums match the values recorded in `REPRODUCIBILITY.md`. The historical H001 observation remains a real prior observation. Generated candidates and registered follow-up sites remain counterfactual until sampled.

## Performance and benefit evidence

The repeated execution benchmark used a deterministic synthetic graph with 256 candidate reaches, 64 candidate sites, eight hypotheses, and 512 decision reachability checks per run. After 10 warmups and 100 measured runs, median execution times on CPython 3.12.3 / Linux x86_64 were:

| Operation | Median |
| --- | ---: |
| Candidate generation | 0.000618741 seconds |
| Sampling decision | 0.000510001 seconds |

These measurements describe software execution for the synthetic fixture on one environment. They do not measure fieldwork, laboratory processing, investigator time, cost, savings, detection performance, or biological accuracy.

The workflow-measurement template contains no observed runs. Its summary is `NO_MEASUREMENTS`; therefore no comparative time, cost, efficiency, or accuracy claim is supported.

## Data availability

- Historical Wigger eDNA and reviewed hydrological inputs are available with frozen checksums.
- The Open-Meteo archive adapter can retrieve explicitly pinned ERA5 daily historical temperature and precipitation with date, units, grid coordinates, 0.25-degree resolution, provenance, and missing-data reporting. The deterministic Wigger reproduction does not invoke environmental providers and contains zero context records.
- GBIF context is available through the occurrence-search adapter but does not prove presence or absence at the case site.
- GHSL historical built-up tiles exist, but no reproducible buffer extraction and raster provisioning path is configured. Urbanization therefore remains unavailable.
- Field accessibility, permission, safety, assay sensitivity, transport, decay, dilution, abundance, replicate details, and complete laboratory metadata are not available for the proposed follow-up.

## Remaining validation

Scientific-review status remains **Draft**. Promotion beyond Draft requires:

1. independent confirmation of station-to-reach mappings and candidate accessibility;
2. prospective, replicated sampling at competing sites with assay controls and complete metadata;
3. an independent source-truth or defensible reference standard;
4. matched comparisons against predefined alternative planning workflows;
5. observed investigator time, field effort, laboratory effort, cost, and assay outcomes;
6. external scientific review of the interpretation and limitations;
7. a documented GHSL extraction if urbanization context is added.

The completed verification supports a reproducible research prototype and tested investigation workflow. It does not establish production deployment readiness, clinical or ecological decision authority, or validated field benefit.
