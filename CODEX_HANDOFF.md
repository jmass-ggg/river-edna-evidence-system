# Codex Sol Handoff: eDNA Evidence Investigator Scientific Core

**Project:** eDNA Evidence Investigator - Wigger case analysis  
**Repository:** `~/james/dogfood/wigger_data_preflight_artifacts`  
**Handoff Date:** 2026-10-01  
**Backend Status:** Foundation complete, scientific core requires implementation

---

## BACKEND STATUS: DO NOT REBUILD

The following backend infrastructure is **COMPLETE** and should **NOT** be modified:

### ✅ Implemented and Frozen
- **Domain Models**: `app/domain/models.py` - Case, SamplingSite, RiverReach, CandidateZone, EvidenceItem, EvidenceAssessment, DecisionTrace
- **Domain Enums**: `app/domain/enums.py` - All status enumerations (EvidenceCompatibility, SamplingDecisionStatus, ValidationStatus, SiteType, CaseStatus)
- **Database Models**: `app/db/models.py` - SQLAlchemy ORM for all entities
- **Database Session**: `app/db/session.py` + `app/db/base.py` - PostgreSQL connection management
- **Migrations**: `alembic/versions/6758ca39bed9_initial_schema_with_all_tables.py` - Complete schema
- **Repositories**: `app/repositories/{cases,evidence,sampling}.py` - CRUD operations, fully tested
- **API Schemas**: `app/schemas/{cases,evidence,hydrology,sampling}.py` - Pydantic request/response models
- **API Routes**: `app/api/routes/{cases,evidence,hydrology,sampling,demo,health}.py` - FastAPI endpoints
- **Services**: `app/services/{case_service,evidence_service,hydrology_service,sampling_service}.py` - Business logic orchestration
- **Wigger Loader**: `app/scientific/data_loader.py` - Preflight data loader (tested, working)
- **Interfaces**: `app/scientific/interfaces.py` - Protocol definitions for all engines

### 📊 Test Status
- **Total Tests:** 67 passed, 0 failed
- **Coverage:** Unit tests + property-based tests (Hypothesis)
- **Test Command:** `cd backend && pytest -q`

---

## FILES CODEX SHOULD EDIT

### 🔬 Primary Scientific Implementation (REQUIRED)

**1. `backend/app/scientific/hydrology/engine.py`**
- **Purpose:** River network analysis and routing
- **Current Status:** PARTIAL - graph built, basic queries work, `network_distance_km()` needs validation
- **What to do:**
  - Audit `network_distance_km()` method (line ~100-150)
  - Verify distance calculation uses LENGTH_KM correctly
  - Validate against known distances: B=19.226 km, C=23.936 km, D=10.941 km from Site A
  - Ensure NEXT_DOWN traversal is correct
- **Tests:** `tests/unit/test_hydrology_engine.py`, `tests/property/test_hydrology_properties.py`

**2. `backend/app/scientific/evidence/engine.py`**
- **Purpose:** Evidence compatibility assessment
- **Current Status:** SCAFFOLD - returns UNKNOWN for all evidence
- **What to do:**
  - Implement `assess_evidence_for_zone()` with validated scientific rules
  - Define rule catalog structure
  - Implement rule matching logic
  - Return SUPPORTS/CONTRADICTS/NEUTRAL based on rules
  - Keep UNKNOWN when no rule applies
- **Tests:** `tests/property/test_evidence_properties.py`

**3. `backend/app/scientific/sampling/engine.py`**
- **Purpose:** Sampling site recommendation
- **Current Status:** SCAFFOLD - returns INSUFFICIENT_DATA
- **What to do:**
  - Implement `evaluate_candidates()` with scoring criteria
  - Implement `make_recommendation()` decision logic
  - Support RECOMMEND/TIE/ABSTAIN/INSUFFICIENT_DATA statuses
  - **CRITICAL:** Must NOT hardcode "always recommend B"
  - Must support different outcomes based on evidence/hydrology
- **Tests:** `tests/property/test_sampling_properties.py`

### 📋 Supporting Files (if needed)

**4. `backend/app/scientific/rules/` (CREATE NEW)**
- **Purpose:** Scientific rule catalog
- **Current Status:** NOT STARTED
- **What to do:**
  - Create `catalog.py` or similar
  - Define rule structure (ID, conditions, outcomes)
  - Document rule provenance
  - Make rules auditable and traceable

**5. `backend/tests/unit/test_carraro_validation.py` (CREATE NEW)**
- **Purpose:** Historical case validation against Carraro 2020
- **Current Status:** NOT STARTED
- **What to do:**
  - Load Carraro results (if available)
  - Compare against system outputs
  - Document discrepancies
  - Validate scientific correctness

---

## FROZEN PREFLIGHT INPUTS

**Status:** All required files **EXIST** and are **FROZEN**

These files are **READ-ONLY** scientific inputs. Do NOT modify unless you find a verified scientific error:

| File | Status | Purpose |
|------|--------|---------|
| `data_preflight/outputs/site_a.json` | ✅ EXISTS | Site A (S1) coordinates, HYRIV_ID=20446064 |
| `data_preflight/outputs/upstream_reaches_real.csv` | ✅ EXISTS | Reach metadata (HYRIV_ID, NEXT_DOWN, LENGTH_KM, etc.) |
| `data_preflight/outputs/upstream_edges.csv` | ✅ EXISTS | Parent-child relationships for graph construction |
| `data_preflight/outputs/candidate_zones_real.geojson` | ✅ EXISTS | Z1/Z2/Z3 zone definitions and geometries |
| `data_preflight/outputs/candidate_sampling_sites.csv` | ✅ EXISTS | Sites B/C/D with corrected distances |
| `data_preflight/outputs/sampling_design_validation.json` | ✅ EXISTS | Validation metadata |
| `data_preflight/outputs/site_a_snap_validation.json` | ✅ EXISTS | Site A network-match audit |
| `data_preflight/outputs/FINAL_REPORT.md` | ✅ EXISTS | Complete S1→20446064 match justification |

---

## SCIENTIFIC TODOs

### TODO 1: Finalize Site A Snap Resolution
- **Status:** ✅ COMPLETE
- **Details:** S1 matched to HYRIV_ID 20446064, validated via Swiss federal hydrography, documented in FINAL_REPORT.md
- **Files:** `site_a.json`, `site_a_snap_validation.json`, `FINAL_REPORT.md`

### TODO 2: Implement/Audit Exact `network_distance_km()`
- **Status:** 🟡 PARTIAL - method exists but needs validation
- **Files:** `backend/app/scientific/hydrology/engine.py` (lines ~100-150)
- **Dependencies:** Must match preflight distances: B=19.226, C=23.936, D=10.941 km
- **Test:** Property test exists but may need expansion

### TODO 3: Implement Approved Scientific Rule Catalog
- **Status:** ⚪ NOT STARTED
- **Files:** `backend/app/scientific/rules/catalog.py` (CREATE NEW)
- **Dependencies:** Requires scientific reviewer approval
- **Notes:** Rules must be documented, auditable, and traceable

### TODO 4: Implement EvidenceCompatibilityEngine
- **Status:** 🟡 SCAFFOLDED - infrastructure exists, logic missing
- **Files:** `backend/app/scientific/evidence/engine.py`
- **Dependencies:** TODO 3 (rule catalog)
- **Tests:** `tests/property/test_evidence_properties.py`

### TODO 5: Implement SamplingDecisionEngine
- **Status:** 🟡 SCAFFOLDED - infrastructure exists, logic missing
- **Files:** `backend/app/scientific/sampling/engine.py`
- **Dependencies:** TODO 2 (distance), TODO 4 (evidence)
- **Tests:** `tests/property/test_sampling_properties.py`
- **Critical:** Must NOT hardcode "always recommend B"

### TODO 6: Wigger Regression Tests
- **Status:** 🟡 PARTIAL - basic tests exist, need scientific validation
- **Files:** `tests/unit/test_wigger_loader.py` (exists), need integration test
- **Dependencies:** TODOs 2, 4, 5
- **Notes:** Verify Sites A/B/C/D handling, Z1/Z2/Z3 evaluation

### TODO 7: Historical Carraro Validation
- **Status:** ⛔ BLOCKED - FINAL_REPORT.md explicitly states "NOT STARTED"
- **Files:** `tests/unit/test_carraro_validation.py` (CREATE NEW)
- **Dependencies:** TODOs 2-6 complete
- **Notes:** Separate phase per FINAL_REPORT.md Section 9
- **Carraro Reference:** Authors assigned S1 to reach index 1, ~147.75 m offset

---

## KNOWN WIGGER IDS

**Site A (S1) - Detection Site:**
- **Coordinates:** 47.31400039098192, 7.895400745863826 (WGS84)
- **HYRIV_ID:** 20446064
- **NEXT_DOWN:** 20445973
- **Snap Distance:** 64.81 m
- **Validation:** MATCHED via Swiss federal hydrography

**Site B - Branch-Specific (Z2):**
- **HYRIV_ID:** 20450127
- **Zone:** Z2
- **Distance to A:** 19.226 km (corrected)

**Site C - Branch-Specific (Z3):**
- **HYRIV_ID:** 20451169
- **Zone:** Z3
- **Distance to A:** 23.936 km (corrected)

**Site D - Shared Trunk (Z2+Z3):**
- **HYRIV_ID:** 20448315
- **Zone:** Shared trunk
- **Distance to A:** 10.941 km (corrected)

**Convergence Point (Z2 + Z3):**
- **HYRIV_ID:** 20449905 (where Z2 root 20450127 and Z3 root 20451169 meet)

---

## TEST COMMANDS

### Focused Scientific Tests
```bash
cd backend
pytest tests/unit/test_hydrology_engine.py -v
pytest tests/property/test_hydrology_properties.py -v
pytest tests/property/test_evidence_properties.py -v
pytest tests/property/test_sampling_properties.py -v
```

### Full Backend Test Suite
```bash
cd backend
pytest -q
# Expected: 67 passed (or more as you add tests)
```

### Property-Based Test Configuration
- Each property test runs 100+ iterations (Hypothesis default)
- Tests are tagged with Feature + Property number
- Example: `# Feature: edna-backend-foundation, Property 15: Network distance accuracy`

### Test Coverage
```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

---

## CURRENT TEST SUMMARY

**Status:** 67 tests passing, 0 failures  
**Warnings:** 112 deprecation warnings (datetime.utcnow() - low priority)  
**Execution Time:** ~3 seconds

**Test Distribution:**
- Unit tests: Coverage of repositories, services, domain models, Wigger loader
- Property tests: Hydrology, evidence, sampling, schema validation
- Integration: Minimal (backend foundation focus)

**Missing Tests:**
- Carraro historical validation (TODO 7)
- Full evidence rule application (waiting on TODO 3/4)
- Full sampling decision logic (waiting on TODO 5)

---

## DEFINITION OF DONE

The scientific core is complete when:

1. ✅ Site A status resolved (DONE)
2. ⬜ HydrologyEngine audited and distance calculations validated
3. ⬜ `network_distance_km()` verified against B/C/D known distances
4. ⬜ Approved scientific rule catalog implemented
5. ⬜ EvidenceCompatibilityEngine returns SUPPORTS/CONTRADICTS/NEUTRAL with rules
6. ⬜ SamplingDecisionEngine supports RECOMMEND/TIE/ABSTAIN/INSUFFICIENT_DATA
7. ⬜ System does NOT hardcode "always recommend B" (anti-bias test passes)
8. ⬜ Wigger regression tests pass with real scientific logic
9. ⬜ Historical Carraro case validated (separate phase)
10. ⬜ Full backend test suite passes (67+ tests, 0 failures)
11. ✅ Raw scientific data unchanged (DONE - all files frozen)
12. ✅ Frontend untouched (DONE - no frontend exists)
13. ✅ No LLM integration (DONE - verified in tests)

---

## TOKEN-EFFICIENCY NOTES

**What NOT to ask Codex to read:**
- Full CSV contents (use summaries above)
- Full GeoJSON contents (use HYRIV_IDs above)
- Entire FINAL_REPORT.md (key facts extracted above)
- Backend infrastructure code (repositories, services, routes - already working)

**What Codex SHOULD focus on:**
- Scientific method implementation in 3 engine files
- Rule catalog design and validation
- Distance calculation validation
- Anti-bias verification
- Carraro comparison (when ready)

**Codex can assume:**
- Database works
- API works
- Repositories work
- Wigger data loads correctly
- Test infrastructure exists

---

## ARCHITECTURE SUMMARY

```
FastAPI Routes (DONE)
    ↓
Services (DONE)
    ↓
Repositories (DONE) + Scientific Engines (TODO)
    ↓                      ↓
Database (DONE)     Preflight Data (DONE)
```

**Clean separation:** Backend engineering complete, scientific logic awaits implementation.

---

## CONTACT NOTES

- Backend passes 67 tests with 0 failures
- All 8 required preflight files exist and validated
- S1→HYRIV_ID 20446064 match documented and defensible
- Distances corrected: B=19.226, C=23.936, D=10.941 km
- No production changes required
- Scientific engines scaffolded and ready for logic insertion
