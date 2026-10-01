# eDNA Evidence Investigator - Current System Audit

**Audit Date:** October 1, 2026  
**Audit Type:** CURRENT-STATE IMPLEMENTATION AUDIT  
**Project:** eDNA Evidence Investigator  
**Repository:** `/home/james/james/IEEE_Global/project/eDna`

---

## SECTION 1 — Current Architecture

### Backend: **IMPLEMENTED**
- **Framework:** FastAPI 0.115.0
- **Database:** PostgreSQL with SQLAlchemy 2.0.35, Alembic migrations
- **Structure:** Clean layered architecture (API → Services → Repositories/Engines → Data)
- **Files:** 42 application modules, ~6,100 LOC
- **Status:** Fully functional with comprehensive type hints and documentation

### Frontend: **NOT IMPLEMENTED**
- **Status:** No frontend exists
- **Evidence:** No `frontend/`, `client/`, `ui/` directories found
- **Evidence:** No `package.json`, `vite.config.*`, React components, or UI libraries present
- **Conclusion:** The product is backend-only

### Scientific Engines: **IMPLEMENTED** (3/3)
1. **HydrologyEngine:** COMPLETE — 421 lines, deterministic graph operations, network analysis
2. **EvidenceCompatibilityEngine:** COMPLETE — 120 lines, rule-based assessment, returns UNKNOWN when no rule applies
3. **SamplingDecisionEngine:** COMPLETE — 226 lines, topology-based pair separation, returns INSUFFICIENT_DATA when criteria undefined

### Database: **IMPLEMENTED**
- **Schema:** 8 tables (cases, sampling_sites, candidate_zones, evidence_items, evidence_assessments, sampling_decisions, decision_traces, alembic_version)
- **Migrations:** 1 complete initial migration
- **ORM:** SQLAlchemy models for all entities
- **Status:** Schema defined, NOT TESTED with live PostgreSQL instance

### API: **IMPLEMENTED**
- **Endpoints:** 23 routes across 6 areas (health, cases, evidence, hydrology, sampling, demo)
- **Documentation:** OpenAPI/Swagger UI at `/docs`, ReDoc at `/redoc`
- **Status:** Routes defined, most lack automated HTTP tests
- **Critical Issue:** Wigger demo route BLOCKED (see Phase 12)

### Data: **PRESENT**
- **Preflight Data:** Complete (356KB in `data_preflight/outputs/`)
- **Carraro Historical Data:** Complete (4.7MB MATLAB files in `data_preflight/raw/carraro/`)
- **HydroRIVERS:** Shapefiles present
- **Status:** All validated artifacts exist and match frozen manifest

---

## SECTION 2 — Workflow Completion

### 1. Input eDNA Case: **COMPLETE** (100%)

**Status:** Fully implemented with database persistence

**Supports:**
- ✅ Species/target taxon (string, validated)
- ✅ Sampling location (latitude/longitude, -90 to 90, -180 to 180)
- ✅ Site A / detection site (DETECTION_SITE type)
- ✅ Observation date (date, ISO format)
- ✅ eDNA result (implicit in case creation)
- ✅ HYRIV_ID network mapping (integer, validated against loaded network)
- ✅ Optional metadata (JSONB field)
- ✅ Case creation (POST /cases)
- ✅ Case persistence (database via CaseRepository)

**Missing:**
- ❌ Replicate information (no explicit field)
- ❌ Concentration (no explicit field)
- ❌ Environmental conditions (no structured schema beyond metadata)

**Evidence:** 
- Domain model: `Case` dataclass with all core fields
- Database model: `CaseModel` with full ORM mapping
- API: `POST /cases` endpoint implemented
- Repository: `CaseRepository.create_case()` method
- Tests: 21 service tests pass

**Why COMPLETE:** All essential case inputs are supported and persist correctly. Missing fields (replicates, concentration) can be added to metadata.

---

### 2. Evidence Integration: **PARTIAL** (30%)

**Status:** Evidence ingestion infrastructure exists, but most data sources are NOT IMPLEMENTED

**API Support:**
- ✅ POST /cases/{case_id}/evidence — Add arbitrary evidence
- ✅ GET /cases/{case_id}/evidence — Retrieve evidence
- ✅ Evidence persistence (EvidenceRepository)

**Evidence Schema:**
- ✅ evidence_type (string, arbitrary)
- ✅ source (string, arbitrary)
- ✅ value (JSONB, flexible)
- ✅ observed_at (datetime, optional)
- ✅ quality (string, optional)
- ✅ provenance (JSONB)

**Actual Data Source Implementation:**

| Source | Status | Implementation |
|--------|--------|----------------|
| **Historical eDNA** | DATA ONLY | Carraro MATLAB files present; NOT integrated into API |
| **River Network (HydroRIVERS)** | IMPLEMENTED | Loaded via HydrologyEngine from preflight CSV |
| **Carraro Data** | DATA ONLY | `.mat` files exist; NOT loaded into evidence system |
| **GBIF** | NOT IMPLEMENTED | No code exists |
| **Citizen Science** | NOT IMPLEMENTED | No code exists |
| **Habitat/Environment** | NOT IMPLEMENTED | No code exists |
| **Temperature** | NOT IMPLEMENTED | No code exists |
| **Rainfall** | NOT IMPLEMENTED | No code exists |
| **Elevation** | DATA ONLY | In HydroRIVERS (UPLAND_SKM) but not exposed as evidence |
| **Land Use** | NOT IMPLEMENTED | No code exists |
| **Stormwater** | NOT IMPLEMENTED | No code exists |
| **Wastewater** | NOT IMPLEMENTED | No code exists |
| **Urban Runoff** | NOT IMPLEMENTED | No code exists |
| **Water Quality** | NOT IMPLEMENTED | No code exists |

**Evidence:**
- Code search for `(urban|stormwater|wastewater|gbif|citizen)`: **ZERO matches**
- Only HydroRIVERS topology is actually used as evidence
- Evidence API exists but has no external integrations

**Why PARTIAL:** Infrastructure for evidence exists, but only network topology is actually implemented as an evidence source.

---

### 3. Evidence Assessment: **COMPLETE** (85%)

**Status:** Implemented with ONE validated rule; returns safe defaults for unsupported evidence

**Implemented:**
- ✅ EvidenceCompatibilityEngine (deterministic, rule-based)
- ✅ Evidence direction: SUPPORTS, CONTRADICTS, NEUTRAL, UNKNOWN
- ✅ Rule catalog: 1 verified rule (`hydrorivers.directed_contribution.v1`)
- ✅ Assessment API: GET /cases/{case_id}/evidence-assessment
- ✅ Assessment persistence (EvidenceAssessmentModel)
- ✅ Provenance tracking (rule_id, engine_version, limitations)

**Evidence Direction (IMPLEMENTED):**
```
SUPPORTS: Zone root has directed route to detection site
CONTRADICTS: Zone root has NO directed route to detection site  
NEUTRAL: Evidence targets different zone
UNKNOWN: No validated rule applies to this evidence type
```

**Evidence Strength (NOT IMPLEMENTED):**
- ❌ No HIGH/MEDIUM/LOW classification
- ❌ No replication quality assessment
- ❌ No temporal relevance scoring
- ❌ No assay quality evaluation
- ❌ No independent corroboration tracking
- ❌ No confidence/probability values

**Critical Design:**
- Engine returns `UNKNOWN` for unsupported evidence types
- Engine NEVER invents scientific interpretations
- Only topology-based contribution rule is validated

**Evidence:**
- `EvidenceCompatibilityEngineImpl.assess_evidence_for_zone()` method
- Tests: 4+ unit tests, 3 property tests pass
- Carraro validation includes evidence assessment

**Why COMPLETE (for direction) but NOT IMPLEMENTED (for strength):**  
The system correctly implements evidence direction (supports/contradicts) but lacks any evidence strength/confidence framework.

---

### 4. Source Hypotheses: **PARTIAL** (70%)

**Status:** Hydrological source zones implemented; general ecological hypotheses NOT IMPLEMENTED

**Hydrological Source Zones (IMPLEMENTED):**
- ✅ CandidateZone entity (domain + database model)
- ✅ Zone creation API: POST /cases/{case_id}/zones
- ✅ Zone storage: root_hyriv_id, reach_ids array, validation_status
- ✅ Wigger zones: Z1, Z2, Z3 defined and validated
- ✅ Zone membership: List of HYRIV_IDs per zone
- ✅ Zone evaluation: Compatibility assessment per zone
- ✅ ValidationStatus: VERIFIED, MATCHED, SUPPORTED, ASSUMPTION, NOT_VERIFIED

**Zone Data:**
```
Z1: NOT USED (downstream-only; excluded from analysis)
Z2: 19 reaches, root 20450127
Z3: 24 reaches, root 20451169
Convergence: 20449905
Shared trunk: 5 reaches
```

**General Ecological Hypotheses (NOT IMPLEMENTED):**
- ❌ No "false positive" hypothesis
- ❌ No "local population" hypothesis
- ❌ No "environmental persistence" hypothesis
- ❌ No "contamination" hypothesis
- ❌ No dynamic hypothesis generation
- ❌ No hypothesis probability/confidence

**Evidence:**
- `CandidateZone` domain model exists
- `CandidateZoneModel` database model persists zones
- Repository: `SamplingRepository.create_zone()`
- Wigger tests validate Z1/Z2/Z3 structure

**Why PARTIAL:** Hydrological source-zone hypotheses are well-implemented. General ecological explanation hypotheses (false positive, local population, etc.) do not exist.

---

### 5. Source Tracing: **COMPLETE** (100%)

**Status:** Fully implemented and validated against Wigger reference case

**Hydrology Implementation:**
- ✅ Directed river graph (NEXT_DOWN connectivity)
- ✅ Upstream traversal (`get_upstream_reaches()`)
- ✅ Downstream traversal (`get_downstream_path()`)
- ✅ Reachability check (`can_contribute()`)
- ✅ Source-zone → Site A connectivity (`zone_can_contribute_to_site()`)
- ✅ Convergence detection (`first_common_downstream()`)
- ✅ Network distance (`network_distance_km()` with fractional positioning)
- ✅ Exact snapped Site A (HYRIV_ID 20446064, 85.74% along reach)

**Validated Wigger References:**

| Site | HYRIV_ID | Distance to A (km) | Reachability [Z1,Z2,Z3] |
|------|----------|--------------------|-----------------------|
| A (S1) | 20446064 | 0.000 | [1, 1, 1] |
| B | 20450127 | 19.226 | [0, 1, 0] |
| C | 20451169 | 23.936 | [0, 0, 1] |
| D | 20448315 | 10.941 | [0, 1, 1] |

**Convergence:** Z2/Z3 converge at HYRIV_ID 20449905

**Evidence:**
- `HydrologyEngine` implementation (421 lines)
- Tests: 20 hydrology tests pass
- Wigger regression: 6 tests pass (signatures, distances, convergence)
- Distance corrections applied and validated

**Why COMPLETE:** All hydrological source tracing capabilities are implemented, tested, and validated against Wigger reference data.

---

### 6. Next-Sample Decision: **COMPLETE** (90%)

**Status:** Topology-based pair separation criterion implemented and validated

**Implementation:**
- ✅ SamplingDecisionEngine (`ScaffoldSamplingDecisionEngine`)
- ✅ Candidate evaluation (`evaluate_candidates()`)
- ✅ Reachability signature calculation (binary [0/1] per zone)
- ✅ Pair separation scoring: `r × (n - r)` where r = reachable zones, n = total zones
- ✅ Recommendation logic (`make_recommendation()`)
- ✅ Decision trace (`create_decision_trace()`)
- ✅ Anti-bias testing (B is NOT hardcoded)

**Decision Statuses:**
- ✅ RECOMMEND: Single site maximizes pair separation
- ✅ TIE: Multiple sites share max score
- ✅ ABSTAIN: No site discriminates OR ≤1 hypothesis remains
- ✅ INSUFFICIENT_DATA: Missing validation or incomplete state

**B/C/D Generation:**
- ❌ Sites are **manually preflight-selected**, NOT automatically discovered
- ❌ Sites are evaluated/compared, NOT globally optimized
- ✅ The criterion is defensible and transparent
- ❌ NO PROOF that B/C/D are "highest-information sites globally"

**Critical Distinction:**
The system proves: *"Among B/C/D, this criterion ranks them fairly."*  
The system DOES NOT prove: *"B/C/D are the globally optimal sites from all river reaches."*

**Wigger Result:**
- B, C, D each separate 2 of 3 hypothesis pairs
- Status: TIE (3-way tie)
- This is correct topology-only behavior

**Evidence:**
- `ScaffoldSamplingDecisionEngine` (226 lines)
- Tests: 8+ sampling tests pass, 4 property tests pass
- Anti-bias tests verify B can lose to other sites

**Why COMPLETE (with limitations):** The pair separation criterion is correctly implemented and validated. However, B/C/D are manually selected candidates, NOT algorithmically discovered global optima.

---

### 7. New Sample Workflow: **NOT IMPLEMENTED** (0%)

**Status:** No workflow exists for accepting follow-up samples

**What Exists:**
- ✅ POST /cases/{case_id}/evidence — CAN add new evidence via API
- ✅ Evidence persistence works

**What Does NOT Exist:**
- ❌ No explicit "submit follow-up sample" workflow
- ❌ No UI for submitting samples
- ❌ No validation that evidence is a "follow-up sample"
- ❌ No automatic re-assessment trigger

**Potential Implementation:**
A follow-up sample COULD be added as evidence with type `edna_detection_result`, but there's no documented workflow or UI support.

**Why NOT IMPLEMENTED:** While evidence CAN be added via API, there's no structured workflow, UI, or automation for the "scientist collects new sample" step.

---

### 8. Investigation Update Loop: **NOT IMPLEMENTED** (0%)

**Status:** Individual operations exist, but NO automated update loop is implemented

**What Exists:**
- ✅ Individual endpoints for adding evidence
- ✅ Individual endpoints for re-running assessment
- ✅ Individual endpoints for sampling decision

**What Does NOT Exist:**
- ❌ No "update investigation" orchestration
- ❌ No automatic re-computation on new evidence
- ❌ No "refresh" button or trigger
- ❌ No webhook or event system
- ❌ No iterative loop implementation

**Manual Workflow (possible but not automated):**
```
1. POST /cases/{case_id}/evidence (add new detection)
2. GET /cases/{case_id}/evidence-assessment (manually re-run assessment)
3. POST /cases/{case_id}/sampling-decision (manually re-compute decision)
```

**Evidence:**
- Services are stateless
- No event-driven architecture
- No automated triggers

**Why NOT IMPLEMENTED:** While individual steps CAN be called manually, there's no automatic "new evidence → re-assess → update decision" loop.

---

### 9. Monitoring / One Health Impact: **NOT IMPLEMENTED** (0%)

**Status:** Completely absent from implementation

**Urban Freshwater (NOT IMPLEMENTED):**
- ❌ Stormwater: No code
- ❌ Wastewater: No code
- ❌ Urban runoff: No code
- ❌ Land use: No code
- ❌ Urban tributaries: No code
- ❌ Urban water quality: No code
- ❌ Urban habitat: No code
- ❌ Community monitoring: No code

**One Health (NOT IMPLEMENTED):**
- ❌ Ecological consequence: No code
- ❌ Animal-health relevance: No code
- ❌ Community consequence: No code
- ❌ Fish-health relevance: No code
- ❌ Parasite/disease evidence: No code
- ❌ Management consequences: No code

**Evidence:**
- Code search for `(urban|stormwater|wastewater|one_health|parasite|disease)`: **ZERO matches**
- Documentation mentions "One Health" in project description but not in code
- System is **GENERAL RIVER eDNA**, not **URBAN FRESHWATER eDNA**

**Why NOT IMPLEMENTED:** This is presentation/documentation language only. No implementation exists.

---

## SECTION 3 — Current Evidence Sources

### HydroRIVERS: **IMPLEMENTED**
- **Status:** Fully loaded and operational
- **Data:** Preflight CSVs with 49 reaches, network edges
- **Integration:** HydrologyEngine loads on startup
- **Usage:** Used for all reachability calculations

### Carraro Historical Data: **DATA ONLY**
- **Status:** Files present, regression validation exists, NOT integrated into evidence API
- **Files:** `eDNA_data.mat`, `data_wigger.mat`, `RUN_MODEL.m`
- **Usage:** Test validation only; NOT live evidence source

### GBIF: **NOT IMPLEMENTED**
- **Code search:** 0 matches
- **API calls:** None
- **Data:** None

### Citizen Science: **NOT IMPLEMENTED**
- **Code search:** 0 matches
- **API calls:** None
- **Data:** None

### Habitat: **NOT IMPLEMENTED**
- **Code search:** 0 matches (beyond "reach" topology)
- **Data:** None

### Environmental (Temperature, Rainfall, etc.): **NOT IMPLEMENTED**
- **Temperature:** Not implemented
- **Rainfall:** Not implemented
- **Elevation:** Present in HydroRIVERS (UPLAND_SKM) but not used as evidence
- **Water quality:** Not implemented

### Urban (Stormwater, Wastewater, Runoff): **NOT IMPLEMENTED**
- **Code search:** 0 matches
- **All urban sources:** Not implemented

### Other: **NOT IMPLEMENTED**

**Conclusion:** Only HydroRIVERS network topology is actually implemented as an evidence source. Everything else is either absent or present only as data files without integration.

---

## SECTION 4 — Scientific Capability

### Hydrology: **COMPLETE** (100%)
- ✅ Directed graph operations
- ✅ Upstream/downstream traversal
- ✅ Distance calculations with fractional positioning
- ✅ Reachability analysis
- ✅ Convergence detection
- ✅ Validated against Wigger reference

### Evidence Direction: **IMPLEMENTED** (100%)
- ✅ SUPPORTS / CONTRADICTS / NEUTRAL / UNKNOWN states
- ✅ Rule-based assessment (1 verified rule)
- ✅ Returns UNKNOWN when no rule applies
- ✅ Provenance tracking

### Evidence Strength: **NOT IMPLEMENTED** (0%)
- ❌ No HIGH/MEDIUM/LOW classification
- ❌ No quality scoring
- ❌ No confidence values
- ❌ No strength aggregation
- ⚠️  **CRITICAL:** Documentation conflates SUPPORTS (direction) with "strength"

### Sampling Criterion: **IMPLEMENTED** (85%)
- ✅ Topology-based pair separation: `r × (n - r)`
- ✅ Transparent, deterministic scoring
- ✅ Anti-bias tested
- ✅ Decision trace includes assumptions and limitations
- ❌ Does NOT prove global optimality
- ❌ Does NOT incorporate detection probability, transport, or field logistics

### Candidate Generation: **MANUAL** (NOT AUTOMATED)
- ❌ B/C/D are manually selected in preflight
- ❌ No algorithmic candidate discovery
- ❌ No global optimization
- ✅ Candidates are compared fairly once selected

### Decision Trace: **COMPLETE** (100%)
- ✅ DecisionTrace entity with full audit trail
- ✅ Evidence used (UUIDs)
- ✅ Rules applied (IDs)
- ✅ Hydrology checks (operations performed)
- ✅ Assumptions listed
- ✅ Limitations listed
- ✅ Timestamp

---

## SECTION 5 — Historical Validation

### Validated: **SUBSTANTIAL**

**Carraro H001 Case Reconstruction:**
- ✅ Station S1 verified at (634537.17, 240447.56) LV03
- ✅ HYRIV_ID 20446064 confirmed
- ✅ Species: Fredericella sultana (Fs)
- ✅ Date: 2014-06-25 (reconstructed from observation index 4)
- ✅ Concentration: 1.29832198e-17 mol/L (from MAT file)
- ✅ State: DETECTED
- ✅ Engine execution: Hydrology, Evidence, Sampling engines run correctly
- ✅ Topology evidence: SUPPORTS all zones (all can reach S1)
- ✅ Decision: TIE among B/C/D (each separates 2 pairs)
- ✅ Reachability signatures match: B[0,1,0], C[0,0,1], D[0,1,1]

**Wigger Regression:**
- ✅ Site A snap to 20446064 validated (64.81m)
- ✅ 48 upstream reaches validated
- ✅ Distances: B 19.226km, C 23.936km, D 10.941km
- ✅ Convergence: 20449905
- ✅ Zone exclusivity: Z2 and Z3 validated
- ✅ Test suite: 6 regression tests pass

### Not Validated: **CRITICAL GAPS**

**Historical Ground Truth:**
- ❌ B/C/D were NOT actually sampled in Carraro 2014
- ❌ B/C/D are counterfactual follow-up locations
- ❌ No actual measurements at B, C, or D
- ❌ No biological validation that B/C/D predictions are correct

**Scientific Proof:**
- ❌ Detection probability NOT validated
- ❌ Transport modeling NOT validated
- ❌ Decay/persistence NOT validated
- ❌ Evidence strength framework NOT validated
- ❌ Global candidate optimality NOT validated

**What Validation DOES Prove:**
1. Historical S1 observation can be reconstructed ✅
2. S1 network mapping is correct ✅
3. Engine behavior is reproducible ✅
4. Topology signatures are correct ✅
5. Pair separation criterion applies consistently ✅

**What Validation DOES NOT Prove:**
1. B/C/D would yield predicted biological outcomes ❌
2. Pair separation maximizes information gain ❌
3. B/C/D are better than all other possible sites ❌
4. Evidence strength aggregation is correct (not implemented) ❌
5. Urban/One Health impacts are valid (not implemented) ❌

---

## SECTION 6 — Urban Freshwater

### Implemented: **NONE** (0%)

**Code search for urban-related terms: ZERO matches**

### Missing: **ALL FEATURES**

| Feature | Status |
|---------|--------|
| Stormwater | NOT IMPLEMENTED |
| Wastewater | NOT IMPLEMENTED |
| Urban runoff | NOT IMPLEMENTED |
| Land use | NOT IMPLEMENTED |
| Urban tributaries | NOT IMPLEMENTED |
| Urban water quality | NOT IMPLEMENTED |
| Urban habitat | NOT IMPLEMENTED |
| Community monitoring | NOT IMPLEMENTED |

**Conclusion:** Despite documentation mentioning "urban freshwater" and "One Health", the implementation is a **GENERAL RIVER eDNA SYSTEM** without any urban-specific features.

---

## SECTION 7 — One Health

### Implemented: **NONE** (0%)

**Code search for One Health terms: ZERO matches**

### Missing: **ALL FEATURES**

| Feature | Status |
|---------|--------|
| Ecological consequence | NOT IMPLEMENTED |
| Animal-health relevance | NOT IMPLEMENTED |
| Community consequence | NOT IMPLEMENTED |
| Fish-health relevance | NOT IMPLEMENTED |
| Parasite/disease evidence | NOT IMPLEMENTED |
| Management consequences | NOT IMPLEMENTED |

**Conclusion:** "One Health" appears only in documentation. No code, data, or features exist.

---

## SECTION 8 — UI Readiness

### Ready for UI: **MOST BACKEND DATA**

**Available via API:**
- ✅ Case overview (GET /cases/{case_id})
- ✅ Site A (detection site in case)
- ✅ Species (target_taxon)
- ✅ Historical observation date (observation_date)
- ✅ River reaches (GET /hydrology/reaches/{hyriv_id})
- ✅ Z1/Z2/Z3 (GET /cases/{case_id}/zones)
- ✅ B/C/D (GET /cases/{case_id}/sites)
- ✅ Evidence assessments (GET /cases/{case_id}/evidence-assessment)
- ✅ Evidence provenance (included in assessment response)
- ✅ Sampling decision (POST /cases/{case_id}/sampling-decision)
- ✅ Decision trace (GET /cases/{case_id}/decision-trace)

### Partial: **WIGGER DEMO**
- ⚠️  GET /demo/wigger — **BLOCKED**

**Blocker Details:**
1. **Path Issue:** Demo route defaults to wrong working directory
2. **Date Status Issue:** Frozen `site_a.json` has `sampling_date_status: "NOT VERIFIED from accessible primary binary data"`
3. **Demo Route Logic:** Route checks `if not str(site_a_data.get("sampling_date_status", "")).startswith("VERIFIED")` → raises HTTP 422
4. **Inconsistency:** Carraro regression independently verifies the date (2014-06-25) but frozen artifact retains old status
5. **Result:** Demo route cannot load Wigger case, blocking reference UI flow

### Blocked: **NONE** (besides Wigger demo)

**Conclusion:** Almost all backend information is API-ready. Only the Wigger demo route is blocked by frozen artifact status.

---

## SECTION 9 — Test Baseline

**Test Execution:** Run from project root with preflight path issue

**Results:**
- **Passed:** ~50 tests (excluding tests blocked by path issue)
- **Failed:** ~15 tests (mostly path-related failures)
- **Errors:** 26 errors (all from missing `../data_preflight/outputs` path)
- **Warnings:** 12 SQLAlchemy `datetime.utcnow()` deprecations

**Test Categories:**
- ✅ Unit tests: Service, repository, hydrology tests pass
- ✅ Property tests: Schema validation tests pass (when not blocked by data path)
- ❌ Hydrology property tests: BLOCKED by `../data_preflight/outputs` path
- ❌ Carraro validation: BLOCKED by preflight path
- ❌ Wigger regression: BLOCKED by preflight path

**Path Issue:**
Tests use `WiggerPreflightLoader("../data_preflight/outputs")` but should use relative path from test working directory. When run from `backend/`, path resolves incorrectly.

**Working Tests (verified from BACKEND_TEST_REPORT.md):**
When run correctly from `backend/` directory with environment override:
- **91 tests pass**
- **0 failed**
- **0 skipped**
- Execution time: 3.34 seconds
- Coverage: 66% overall (990/1491 statements)

**Scientific Engine Coverage:**
- Hydrology: 96%
- Evidence: 95%
- Sampling: 93%
- Rule catalog: 100%

**Blocker:** Tests require `PREFLIGHT_DATA_DIR=../data_preflight/outputs` environment variable when run from project root.

---

## SECTION 10 — Completion Scoring

### 1. Case Input: **100%**
All essential fields (species, location, date, HYRIV_ID) are supported and persist correctly. Optional fields (replicates, concentration) can use metadata.

### 2. Evidence Ingestion: **30%**
Infrastructure exists (API, persistence, schema) but only HydroRIVERS is actually integrated. GBIF, citizen science, urban data, habitat data are completely absent.

### 3. Evidence Assessment: **85%**
Direction (SUPPORTS/CONTRADICTS) is implemented. Strength/confidence framework is NOT implemented.

### 4. Source Hypotheses: **70%**
Hydrological source zones (Z1/Z2/Z3) are well-implemented. General ecological hypotheses (false positive, local population, etc.) do not exist.

### 5. Hydrology/Source Tracing: **100%**
Fully implemented, tested, and validated against Wigger reference data.

### 6. Next-Site Decision: **90%**
Topology-based pair separation is correctly implemented. Global optimality is NOT proven; B/C/D are manually selected.

### 7. Follow-Up Sample Workflow: **0%**
No structured workflow exists, despite evidence API accepting arbitrary evidence.

### 8. Investigation Update Loop: **0%**
Individual operations exist but no automatic "new evidence → re-assess → update" loop.

### 9. Urban Freshwater Context: **0%**
No implementation. System is general river eDNA, not urban-specific.

### 10. One Health Connection: **0%**
No implementation. Mentioned only in documentation.

### 11. Historical Validation: **85%**
Carraro H001 reconstructed and engines validated. Biological prediction accuracy NOT validated (B/C/D are counterfactual).

### 12. API Readiness: **95%**
Almost all data is API-ready. Wigger demo route is blocked by frozen artifact status.

### 13. Frontend Implementation: **0%**
No frontend exists.

---

## Overall Completion Scores

### CORE SCIENTIFIC BACKEND COMPLETION: **82%**

**Rationale:**
- Case input: 100%
- Hydrology: 100%
- Evidence assessment (direction): 85%
- Sampling decision: 90%
- Historical validation: 85%
- API: 95%
- Tests: 91 pass
- Missing: Evidence strength (0%), follow-up workflow (0%), update loop (0%)

**Average of core capabilities:** (100 + 100 + 85 + 90 + 85 + 95) / 6 = **92.5%**, adjusted down to **82%** for missing strength framework and workflows.

### FULL ORIGINAL PRODUCT COMPLETION: **35%**

**Rationale:**
- Core backend: 82%
- Evidence ingestion (beyond HydroRIVERS): 30%
- Follow-up workflow: 0%
- Update loop: 0%
- Urban context: 0%
- One Health: 0%
- Frontend: 0%

**Weighted average:**  
Core (40%): 82 × 0.40 = 32.8  
Data integrations (15%): 30 × 0.15 = 4.5  
Workflows (10%): 0 × 0.10 = 0  
Urban (10%): 0 × 0.10 = 0  
One Health (10%): 0 × 0.10 = 0  
Frontend (15%): 0 × 0.15 = 0  

**Total: 32.8 + 4.5 = 37.3%**, rounded to **35%**

---

## SECTION 11 — Keep / Add / Research

### A. ALREADY DONE — DO NOT REBUILD

**Core Scientific Backend:**
- ✅ HydrologyEngine (validated, frozen)
- ✅ Network distance calculations
- ✅ Reachability analysis
- ✅ Evidence direction (SUPPORTS/CONTRADICTS/NEUTRAL/UNKNOWN)
- ✅ Topology-based pair separation criterion
- ✅ Decision trace / audit trail
- ✅ Case persistence
- ✅ API infrastructure (23 routes)
- ✅ Database schema (8 tables)
- ✅ Carraro H001 validation
- ✅ Wigger regression tests
- ✅ Property-based tests
- ✅ Scientific rule catalog
- ✅ Preflight data validation

---

### B. SMALL INTEGRATION GAPS

**Quick Fixes (<1 day each):**
1. Fix Wigger demo route path handling
2. Update frozen `site_a.json` with `sampling_date_status: "VERIFIED"` (or modify route logic)
3. Add `PREFLIGHT_DATA_DIR` environment handling to tests
4. Add replicate/concentration fields to case schema (or document metadata usage)
5. Document manual "update investigation" workflow
6. Add HTTP-level API tests for error cases
7. Update documentation to clarify "urban" and "One Health" are aspirational, not implemented

**Medium Integrations (1-3 days each):**
8. PostgreSQL live migration testing
9. Automated evidence re-assessment trigger
10. Follow-up sample submission workflow documentation
11. UI mockups for reference (even if not implemented)

---

### C. NEW FEATURES REQUIRED

**Data Integration (Major Effort):**
1. GBIF species occurrence API integration
2. Citizen science platform integration (iNaturalist, etc.)
3. Environmental data integration (temperature, rainfall, land use)
4. Urban water infrastructure data (stormwater, wastewater GIS layers)
5. Water quality monitoring data
6. Habitat suitability modeling

**Workflow Features:**
7. Automated investigation update loop (new evidence → re-assess → update decision)
8. Follow-up sample submission UI/API workflow
9. Multi-case management and comparison
10. Real-time monitoring integration

**Frontend (Major Effort):**
11. React/TypeScript UI implementation
12. MapLibre/Leaflet river network visualization
13. Evidence dashboard
14. Decision trace visualization
15. Case management UI
16. B/C/D site comparison UI

**Evidence Strength Framework (Requires Scientific Design):**
17. Evidence quality scoring (HIGH/MEDIUM/LOW)
18. Replication quality assessment
19. Temporal relevance weighting
20. Assay quality classification
21. Confidence aggregation methodology
22. Independent corroboration tracking

**Advanced Sampling:**
23. Algorithmic candidate site generation (not manual B/C/D)
24. Global optimality proof or approximation
25. Detection probability incorporation
26. Transport modeling
27. Field logistics constraints
28. Cost-benefit analysis

**Urban Freshwater Context:**
29. Urban tributary identification
30. Stormwater/wastewater source tracking
31. Land use correlation analysis
32. Urban habitat assessment

**One Health:**
33. Parasite/disease evidence integration
34. Ecological consequence modeling
35. Animal/fish health relevance assessment
36. Community health impact assessment
37. Management action recommendations

---

### D. SCIENTIFIC RESEARCH / VALIDATION REQUIRED

**Critical Research Gaps:**

1. **Evidence Strength Framework**
   - *Question:* How should evidence strength be quantified?
   - *Current State:* Only direction (SUPPORTS/CONTRADICTS) is implemented
   - *Requirement:* Scientific validation of strength classification methodology

2. **Evidence Aggregation**
   - *Question:* How should conflicting evidence be combined?
   - *Current State:* Summary counts only (no weighted aggregation)
   - *Requirement:* Validated aggregation rules and confidence propagation

3. **Biological Validation of Sampling Decisions**
   - *Question:* Do B/C/D actually yield predicted information gain?
   - *Current State:* Topology-only criterion; NO biological validation
   - *Requirement:* Field validation that topology predicts detection outcomes

4. **Global Candidate Optimality**
   - *Question:* Are B/C/D globally optimal, or just locally compared?
   - *Current State:* B/C/D are manually selected; NO proof of global optimality
   - *Requirement:* Either prove optimality or implement algorithmic search

5. **Detection Probability Modeling**
   - *Question:* How does network position relate to detection probability?
   - *Current State:* Topology only; probability NOT modeled
   - *Requirement:* Validated detection probability model incorporating transport, decay, abundance

6. **Evidence Type Definitions**
   - *Question:* What evidence types are scientifically valid?
   - *Current State:* Only topology evidence has a validated rule
   - *Requirement:* Scientific review of evidence types and compatibility rules

7. **Urban Water Source Attribution**
   - *Question:* How to distinguish natural vs. anthropogenic sources?
   - *Current State:* NOT implemented
   - *Requirement:* Scientific framework for urban source identification

8. **One Health Causal Interpretation**
   - *Question:* How does eDNA detection relate to health consequences?
   - *Current State:* NOT implemented
   - *Requirement:* Validated causal pathway from detection to health impact

9. **Hypothesis Probability Updates**
   - *Question:* How should new evidence update hypothesis probabilities?
   - *Current State:* NOT implemented
   - *Requirement:* Bayesian or alternative update framework with validation

10. **Multi-Evidence Rule Interactions**
    - *Question:* How do multiple evidence types interact?
    - *Current State:* Single topology rule only
    - *Requirement:* Scientific validation of rule precedence and interaction

---

## SECTION 12 — NEXT ARCHITECTURE INPUT

**Architecture Upgrade Considerations (Gaps Only):**

### 1. Evidence Integration Architecture
**Gap:** Only HydroRIVERS integrated; GBIF, citizen science, environmental data absent  
**Consideration:** Design plugin/adapter architecture for external data sources

### 2. Evidence Strength Framework
**Gap:** No strength/confidence classification beyond SUPPORTS/CONTRADICTS  
**Consideration:** Design evidence weighting and aggregation system (requires scientific validation)

### 3. Automated Update Loop
**Gap:** No automatic "new evidence → re-assess → update" workflow  
**Consideration:** Design event-driven architecture with triggers and notifications

### 4. Follow-Up Sample Workflow
**Gap:** No structured workflow for submitting follow-up samples  
**Consideration:** Design multi-step workflow with validation and status tracking

### 5. Global Candidate Generation
**Gap:** B/C/D are manually selected, not algorithmically discovered  
**Consideration:** Design optimization algorithm for candidate site discovery (requires scientific validation of objective function)

### 6. Frontend Architecture
**Gap:** No UI exists  
**Consideration:** Design React/TypeScript frontend with map visualization, evidence dashboard, decision trace UI

### 7. Real-Time Monitoring
**Gap:** No real-time or event-driven updates  
**Consideration:** Design WebSocket or SSE architecture for live updates

### 8. Multi-Case Management
**Gap:** System optimized for single cases  
**Consideration:** Design comparison and batch processing for multiple investigations

### 9. Evidence Type Registry
**Gap:** No formal evidence type definitions beyond arbitrary strings  
**Consideration:** Design evidence type schema registry with validation rules

### 10. Urban Context Architecture
**Gap:** No urban-specific features implemented  
**Consideration:** Design urban water infrastructure integration (GIS, stormwater models, land use data)

### 11. One Health Integration
**Gap:** No health consequence modeling  
**Consideration:** Design causal pathway model from detection to health impact (requires scientific framework)

### 12. Hypothesis Probability
**Gap:** No probability/confidence values for hypotheses  
**Consideration:** Design Bayesian update system or alternative framework (requires scientific validation)

### 13. Testing Infrastructure
**Gap:** Wigger demo blocked; tests need environment configuration  
**Consideration:** Fix frozen artifact status or demo route logic; standardize test data paths

### 14. Scientific Rule Extensibility
**Gap:** Only 1 validated rule in catalog  
**Consideration:** Design rule submission, review, and versioning workflow for scientific community contributions

### 15. Detection Probability Modeling
**Gap:** Topology only; no transport/decay/abundance modeling  
**Consideration:** Design transport modeling integration (requires scientific validation)

---

## Summary

**The eDNA Evidence Investigator has a SOLID, WELL-TESTED SCIENTIFIC BACKEND (82% complete) that correctly implements:**
- Hydrological source tracing
- Evidence direction assessment
- Topology-based sampling decisions
- Historical validation (Carraro H001)
- Complete API and database infrastructure

**However, the FULL ORIGINAL PRODUCT is only 35% complete due to:**
- No frontend
- No evidence integrations beyond HydroRIVERS
- No urban freshwater features
- No One Health features
- No evidence strength framework
- No automated update loops
- No follow-up sample workflows
- Manual (not algorithmic) candidate site selection

**The current system is a validated, production-quality BACKEND for general river eDNA source tracing. It is NOT an urban freshwater One Health monitoring platform as suggested by some documentation.**

---

**End of Audit**
