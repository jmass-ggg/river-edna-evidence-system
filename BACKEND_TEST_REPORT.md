# Backend Test Report

## Environment

- Python: 3.12.3 (`venv/bin/python`)
- FastAPI: 0.115.0
- Pydantic: 2.9.2
- SQLAlchemy: 2.0.35
- SciPy: 1.14.1
- GeoPandas: 1.0.1
- Pandas: 2.2.3
- Scientific freeze: both v1 files present; all 28 manifest entries verify.

## Test Summary

- Full suite: `cd backend && pytest -q`
- Passed: 91
- Failed: 0
- Skipped: 0
- Warnings: 12 SQLAlchemy `datetime.utcnow()` deprecations; one pytest-asyncio configuration deprecation emitted before collection
- Execution time: 3.34 seconds
- `python -m compileall -q backend/app`: PASS

## Test Groups

- Unit: 68 passed
- Property: 23 passed
- Hydrology: 20 passed
- Repositories: 8 passed
- Services: 21 passed; CaseService, EvidenceService, HydrologyService, and SamplingService are exercised and delegate scientific calculations to engines
- Schemas: case, evidence, hydrology, and sampling response structure property tests pass
- API: 23 routes register and `/health` responds; most route bodies lack automated tests
- Wigger loader: 10 passed
- Wigger regression: 6 passed
- Carraro regression: 3 passed

## Coverage

`pytest --cov=app --cov-report=term-missing -q`: 91 passed; overall 66% (990/1491 statements).

- Scientific engines: hydrology 96%, evidence 95%, sampling 93%, rule catalog 100%
- Services: case 91%, evidence 86%, hydrology 69%, sampling 85%
- Repositories: cases 34%, evidence 42%, sampling 80%
- API: most route modules 0%; demo 39%; app startup and API dependencies 0% in the test suite

Coverage is informational; no tests or algorithms were changed to raise it.

## Domain and Schema Validation

- Domain enums and models import; tests construct Case, SamplingSite, RiverReach, CandidateZone, EvidenceItem, EvidenceAssessment, and DecisionTrace: PASS
- Pydantic case, evidence, hydrology, and sampling schemas import, and response structure property tests pass: PASS for tested response paths
- Dedicated invalid request and live API validation tests: GAP

## Scientific Validation

- HydrologyEngine: PASS; directed traversal, invalid IDs, disconnected paths, fractional distance, and convergence tests pass
- EvidenceCompatibilityEngine: PASS; SUPPORTS, CONTRADICTS, NEUTRAL, UNKNOWN, unsupported evidence, and provenance are covered
- SamplingDecisionEngine: PASS; RECOMMEND, TIE, ABSTAIN, INSUFFICIENT_DATA, DecisionTrace, and anti-bias tests pass; B is not hardcoded
- Wigger: PASS; A 20446064, B 20450127 at 19.225939 km, C 20451169 at 23.935939 km, D 20448315 at 10.940939 km; convergence 20449905; signatures A [1,1,1], B [0,1,0], C [0,0,1], D [0,1,1]
- Carraro H001: PASS; original MAT and RUN_MODEL.m checks establish S1, Fredericella sultana (Fs), observation 4, 2014-06-25, 1.29832198e-17 mol/L, DETECTED; B/C/D remain counterfactual; decision TIE among B/C/D

## API Validation

- Application import: PASS; title `eDNA Evidence Investigator API`
- Route count: 23 including documentation routes; health, cases, evidence, hydrology, sampling, and demo areas are registered
- Health check: direct read-only ASGI `GET /health` returned HTTP 200 and `healthy` after lifespan startup with `PREFLIGHT_DATA_DIR=../data_preflight/outputs`
- Without that override from `backend/`, health returned HTTP 200 `degraded` because the default relative preflight path is wrong for that working directory
- FastAPI TestClient: unavailable because `httpx` is not installed; the ASGI smoke request exercised the route without it
- Wigger demo: BLOCKED. From `backend/`, its default loader ignores `PREFLIGHT_DATA_DIR` and raises FileNotFoundError. From repository root, it returns HTTP 422 because frozen `site_a.json` says the date is `NOT VERIFIED`, despite independent Carraro regression verification. No data were created.

## Database Validation

- Models: six SQLAlchemy tables import and `configure_mappers()` passes; relationships initialize
- Repositories: focused repository tests pass using test fixtures
- Migration: one initial Alembic revision `6758ca39bed9`; revision graph has one head and one base; metadata imports
- Live PostgreSQL test: NOT EXECUTED — DATABASE INSTANCE NOT CONFIGURED. No database was changed.
- SQLAlchemy reports a table sorting warning for circular foreign keys between `cases` and `sampling_sites`; the migration creates the second foreign key after both tables exist. Live migration execution remains unverified.

## Warnings

- NON-BLOCKING: 12 `datetime.utcnow()` deprecations from SQLAlchemy during repository tests
- FUTURE MAINTENANCE: pytest-asyncio fixture loop scope default deprecation
- FUTURE MAINTENANCE: SQLAlchemy table sort warning for circular case/site foreign keys during metadata inspection

## Known Gaps

- Wigger demo cannot complete under either tested working directory. This blocks a UI flow that loads the reference case.
- Automated API route coverage is mostly zero; invalid API input and missing-case responses were not exercised through HTTP.
- Live PostgreSQL connectivity and migration application were not tested.
- The default preflight path requires an explicit environment override when starting from `backend/`.

## Final Backend Gate

NOT READY FOR UI — the Wigger demo route is blocked by its path handling and frozen Site A date status. Scientific engines and all existing tests pass, but the reference-case API flow is not usable as currently configured.
