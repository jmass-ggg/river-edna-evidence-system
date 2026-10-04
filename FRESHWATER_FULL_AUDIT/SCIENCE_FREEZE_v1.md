# Scientific Backend Freeze v1

## Freeze date

2026-10-01

## Environment

- Python 3.12.3
- SciPy 1.14.1
- GeoPandas 1.0.1

## Test baseline

`cd backend && pytest -q`: 91 passed, 0 failed, 0 skipped, 12 warnings. A separate pytest-asyncio configuration deprecation warning appears before collection.

## Frozen engines

- HydrologyEngine — FROZEN
- EvidenceCompatibilityEngine — FROZEN
- SamplingDecisionEngine — FROZEN
- Scientific rule catalog — FROZEN

## Wigger reference

| Site | HYRIV_ID | Distance to A (km) | Reachability (Z1, Z2, Z3) |
| --- | ---: | ---: | --- |
| A (S1) | 20446064 | 0 | [1, 1, 1] |
| B | 20450127 | 19.22593905163416 | [0, 1, 0] |
| C | 20451169 | 23.935939051634158 | [0, 0, 1] |
| D | 20448315 | 10.940939051634162 | [0, 1, 1] |

Z2/Z3 convergence: HYRIV_ID 20449905. The historical S1 coordinate and snapped HydroRIVERS coordinate are stored separately; the snap fraction and 64.81356293400535 m separation remain in the validated artifacts.

## Carraro H001

- Station: S1; Carraro coordinate: (634537.17, 240447.56); Carraro reach: 1; HydroRIVERS representation: 20446064
- Species: Fredericella sultana (Fs)
- Observation index: 4
- Date: 2014-06-25
- Concentration: 1.2983219767633366e-17 mol/L (1.29832198e-17 mol/L rounded)
- State: DETECTED
- Evidence: historical measurement UNKNOWN under the current rule catalog; directed topology SUPPORTS all three zone hypotheses
- Decision: TIE among B, C, and D; each separates two hypothesis pairs

## Frozen file list

- `backend/app/scientific/interfaces.py`
- `backend/app/scientific/data_loader.py`
- `backend/app/scientific/hydrology/engine.py`
- `backend/app/scientific/evidence/engine.py`
- `backend/app/scientific/sampling/engine.py`
- `backend/app/scientific/rules/catalog.py`
- `backend/app/domain/enums.py`
- `backend/tests/unit/test_hydrology_engine.py`
- `backend/tests/unit/test_wigger_loader.py`
- `backend/tests/unit/test_wigger_scientific_regression.py`
- `backend/tests/unit/test_carraro_validation.py`
- `backend/tests/property/test_hydrology_properties.py`
- `backend/tests/property/test_evidence_properties.py`
- `backend/tests/property/test_sampling_properties.py`
- `data_preflight/outputs/site_a.json`
- `data_preflight/outputs/site_a_snap_validation.json`
- `data_preflight/outputs/upstream_reaches_real.csv`
- `data_preflight/outputs/upstream_edges.csv`
- `data_preflight/outputs/candidate_zones_real.geojson`
- `data_preflight/outputs/candidate_sampling_sites.csv`
- `data_preflight/outputs/sampling_design_validation.json`
- `data_preflight/outputs/FINAL_REPORT.md`
- `data_preflight/raw/carraro/data_wigger.mat`
- `data_preflight/raw/carraro/eDNA_data.mat`
- `data_preflight/raw/carraro/data_explanation.xlsx`
- `data_preflight/raw/carraro/RUN_MODEL.m`
- `data_preflight/raw/carraro/ANALYSE_DATA.m`
- `data_preflight/raw/carraro/README.md`

## Scientific limitations

- Hydrological reachability is not eDNA detection probability.
- Positive eDNA at S1 does not prove an exact upstream biological source.
- B/C/D are counterfactual follow-up locations, not historical measurements.
- The decision criterion is topology-based hypothesis discrimination; H001 currently yields a three-way tie.
- `DIS_AV_CMS` is not sampling-day discharge.
- H001 validates reproducibility and current behavior, not universal ecological correctness or restoration effectiveness.
- The frozen `site_a.json` retains the earlier `sampling_date_status` value `NOT VERIFIED from accessible primary binary data`. The local Carraro MAT source and H001 regression now independently verify the date. The demo route still rejects that preflight field; this freeze preserves the artifact as requested.

## Frontend boundary

Frontend may call FastAPI, display evidence and DecisionTrace, render maps, zones, and B/C/D, and show RECOMMEND, TIE, ABSTAIN, or INSUFFICIENT_DATA.

Frontend must not calculate scientific scores independently, override backend decisions, convert TIE into RECOMMEND, modify reachability signatures, invent confidence values, or mutate frozen scientific inputs.

React → FastAPI → services → frozen deterministic scientific engines → structured result.

## Change policy

Any future scientific change requires scientific justification, Wigger regression, Carraro regression, the full pytest suite, a new checksum manifest, and a new freeze version such as `SCIENCE_FREEZE_v2`.
