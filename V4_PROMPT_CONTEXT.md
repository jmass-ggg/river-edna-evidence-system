# V4 Prompt Context: Automatic Investigation Update & Held-Out Scientific Validation

## 1. V3 Baseline

### Test Baseline
- **Full suite**: 120 passed, 0 failed, 39 warnings
- **Coverage**: 75% overall
- **Wigger regression**: 7 passed
- **Carraro H001 regression**: 3 passed
- **Candidate-generation regression**: 1 passed, 6 deselected
- **Evidence-strength regression**: 5 passed, 7 deselected
- **V3 scientific-boundary tests**: 18 passed

### What V3 Added
- GBIF species-occurrence context provider (official API adapter)
- Generic GHSL-derived urbanization context provider interface
- Generic historical temperature/precipitation provider interface
- Provider-isolated case context collection APIs with provenance/limitations
- Structured FollowUpSample persistence, validation, API, and linked evidence
- Generic evidence-linked One Health relevance framework
- Literature-sourced F. sultana / T. bryosalmonae demonstration pathway

### Frozen Scientific Behavior (MUST NOT CHANGE)
- HydrologyEngine directed network and distance semantics
- Evidence direction: SUPPORTS, CONTRADICTS, NEUTRAL, UNKNOWN
- Hydrological-connectivity strength rule: HIGH / MEDIUM / LOW criteria
- Rule ID: `hydrorivers.directed_connectivity_strength.v1`
- Sampling criterion: pair-separation score `r × (n-r)`
- Candidate generation: deterministic equivalence-class representative selection
- Carraro H001 observation: S1, Fredericella sultana, index 4, 2014-06-25, 1.29832198e-17 mol/L, DETECTED
- Wigger Site A mapping: HYRIV_ID 20446064
- All v1/v2 freeze files and inputs

### Current Limitations
- Follow-up sample submission creates evidence but **does NOT trigger**:
  - Evidence reassessment
  - Hypothesis updates
  - Candidate regeneration
  - New sampling decision
- Response returns `reanalysis_required=true` but system takes no action
- GBIF/urbanization/weather/follow-up evidence remain `UNKNOWN` compatibility, `UNASSESSED` strength
- No automatic investigation orchestration (deferred to Step 7)

---

## 2. Follow-Up Sample Workflow

### Domain Model Fields
**File**: `backend/app/domain/models.py`

```python
@dataclass
class FollowUpSample:
    id: UUID
    case_id: UUID
    sampling_site_id: UUID | None       # Links to existing SamplingSite OR
    candidate_reference: str | None     # References generated candidate label
    hyriv_id: int
    sampled_at: datetime
    replicate_count: int
    positive_replicates: int
    concentration: float | None
    concentration_unit: str | None
    assay: str
    controls_status: str
    collector_source: str
    provenance: dict[str, Any]
    notes: str | None
    evidence_id: UUID | None            # Links to created EvidenceItem
    created_at: datetime
```

### DB Table: `follow_up_samples`
**File**: `backend/app/db/models.py` → `FollowUpSampleModel`

All domain fields mapped 1:1 to DB columns. Foreign keys:
- `case_id` → `cases.id` (required)
- `sampling_site_id` → `sampling_sites.id` (optional)
- `evidence_id` → `evidence_items.id` (optional)

### Repository Methods
**File**: `backend/app/repositories/follow_up_samples.py`

- `add(model: FollowUpSampleModel) -> FollowUpSampleModel`
- `list_for_case(case_id: UUID) -> list[FollowUpSample]`
- `get_for_case(case_id: UUID, sample_id: UUID) -> FollowUpSample | None`

### Service Methods
**File**: `backend/app/services/follow_up_sample_service.py`

- `create(case_id: UUID, **values) -> FollowUpSample`
  - Validates case exists
  - Validates exactly one of `sampling_site_id` or `candidate_reference` provided
  - Validates replicate counts: `0 <= positive_replicates <= replicate_count > 0`
  - Validates concentration/unit pairing
  - Validates HYRIV_ID exists in hydrology engine
  - **Atomically creates**:
    1. `FollowUpSampleModel` record
    2. `EvidenceItemModel` with type `follow_up_edna_sample`
    3. Links `evidence_id` back to sample
  - Uses single transaction: commit on success, rollback on failure
- `list(case_id: UUID) -> list[FollowUpSample]`
- `get(case_id: UUID, sample_id: UUID) -> FollowUpSample`

### Request/Response Schemas
**File**: `backend/app/schemas/follow_up_samples.py`

**FollowUpSampleCreateRequest**:
- All domain fields except `id`, `evidence_id`, `created_at`
- Pydantic validation: exactly one of `sampling_site_id`/`candidate_reference`, positive/replicate logic, concentration/unit pairing

**FollowUpSampleResponse**:
- All domain fields + `reanalysis_required: bool = True` (hardcoded)

### API Endpoints
**File**: `backend/app/api/routes/follow_up_samples.py`

- `POST /cases/{case_id}/follow-up-samples` → 201 Created
- `GET /cases/{case_id}/follow-up-samples` → list
- `GET /cases/{case_id}/follow-up-samples/{sample_id}` → single

### FollowUpSample → EvidenceItem Creation
**Atomic**: Yes. Single transaction wraps:
1. Insert `follow_up_samples` row
2. Insert `evidence_items` row with:
   - `evidence_type="follow_up_edna_sample"`
   - `source=collector_source`
   - `value={sample_id, hyriv_id, replicate_count, positive_replicates, concentration, unit, assay, controls_status, sampled_at, provenance}`
   - `observed_at=sampled_at`
3. Update `follow_up_samples.evidence_id`
4. Commit

**Does submission trigger reassessment?** NO. Service creates records and returns. No downstream calls to evidence assessment, hypothesis updates, candidate regeneration, or decision engine.

---

## 3. Evidence Reassessment

### EvidenceService
**File**: `backend/app/services/evidence_service.py`

**Public Methods**:
- `add_evidence(case_id, evidence_type, source, value, observed_at, quality, provenance) -> EvidenceItem`
  - Validates inputs, calls repository
- `get_evidence_for_case(case_id: UUID) -> list[EvidenceItem]`
- `assess_evidence_for_zones(case, zones, scientific_rules) -> dict[str, dict[str, Any]]`
  - Retrieves all evidence for case
  - Calls engine's `assess_evidence_for_zone` for each zone
  - Returns `{zone_label: {zone_id, assessments, summary}}`

### EvidenceCompatibilityEngine
**File**: `backend/app/scientific/evidence/engine.py` → `EvidenceCompatibilityEngineImpl`

**Public Methods**:
- `assess_evidence_for_zone(case, zone, evidence_items, scientific_rules) -> list[EvidenceAssessment]`
  - Applies catalog rules to each evidence item
  - Returns list of assessments (one per evidence item)
- `summarize_zone_assessment(assessments) -> dict[str, int]`
  - Counts: `{"supports": N, "contradicts": M, "neutral": P, "unknown": Q}`

### EvidenceAssessment Structure
**File**: `backend/app/domain/models.py`

```python
@dataclass
class EvidenceAssessment:
    evidence_id: UUID
    compatibility: EvidenceCompatibility  # SUPPORTS/CONTRADICTS/NEUTRAL/UNKNOWN
    rule_id: str | None
    reason: str
    provenance: dict
    strength: EvidenceStrength            # HIGH/MEDIUM/LOW/UNASSESSED
    strength_criteria: list[dict]
    strength_reason: str
    strength_rule_id: str | None
    strength_rule_version: str | None
    strength_provenance: dict
    strength_limitations: list[str]
```

### Rule Catalog
**File**: `backend/app/scientific/rules/catalog.py`

**Current Rules**:
1. **`hydrorivers.directed_contribution.v1`** (topology compatibility)
   - Evidence type: `directed_hydrological_connectivity`
   - Required fields: `zone_root_hyriv_id`, `site_hyriv_id`, `can_contribute`, `network_validation_status`
   - Effect:
     - `can_contribute=true` → `SUPPORTS`
     - `can_contribute=false` → `CONTRADICTS`
     - Different zone root → `NEUTRAL`
     - Missing/unverified → `UNKNOWN`

2. **`hydrorivers.directed_connectivity_strength.v1`** (claim-specific strength)
   - Evidence type: `directed_hydrological_connectivity`
   - Criteria: network mapping validation, zone root validation, complete topology evaluation, validated graph coverage
   - Effect:
     - All criteria validated → `HIGH`
     - Topology complete, graph coverage unstated → `MEDIUM`
     - Unverified/missing → `LOW`
     - Unsupported evidence type → `UNASSESSED`

### Evidence Type Outcomes

| Evidence Type | Compatibility | Strength |
|---------------|---------------|----------|
| `directed_hydrological_connectivity` | SUPPORTS/CONTRADICTS/NEUTRAL | HIGH/MEDIUM/LOW |
| `historical_edna_measurement` | UNKNOWN | UNASSESSED |
| `follow_up_edna_sample` | UNKNOWN | UNASSESSED |
| GBIF occurrence | UNKNOWN | UNASSESSED |
| Urbanization | UNKNOWN | UNASSESSED |
| Weather (temp/precip) | UNKNOWN | UNASSESSED |

### Assessment Persistence
**NO**. Assessments are computed on-demand. Not stored in DB. Engine is stateless and deterministic.

**Old Assessments**: Not applicable. Each call to `assess_evidence_for_zones` recomputes from current evidence list.

### Assessment-Zone Association
Assessments are returned as part of API response but not persisted. Each assessment includes `zone_label` and `zone_root_hyriv_id` in provenance.

---

## 4. Hypothesis / Zone State

### CandidateZone Fields
**File**: `backend/app/domain/models.py`

```python
@dataclass
class CandidateZone:
    id: UUID
    case_id: UUID
    label: str                          # e.g. "Z1", "Z2", "Z3"
    root_hyriv_id: int                 # Root reach of zone
    reach_ids: list[int]               # All reaches in zone
    validation_status: ValidationStatus # MATCHED/VERIFIED/SUPPORTED/ASSUMPTION/NOT_VERIFIED
    metadata: dict
```

### HypothesisStatus Enum
**File**: `backend/app/domain/enums.py`

```python
class HypothesisStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    POSSIBLE = "POSSIBLE"
    WEAKENED = "WEAKENED"
    CONFLICTING = "CONFLICTING"
    ELIMINATED = "ELIMINATED"
    UNKNOWN = "UNKNOWN"
```

### Is Hypothesis Status Currently Stored?
**NO**. `HypothesisStatus` enum is defined but **not used anywhere**. No field in `CandidateZone` or `CandidateZoneModel` stores hypothesis status.

### Can Zone Status Change?
Currently NO mechanism exists to change zone status. Zones are created once with `validation_status` (network-mapping validation, not hypothesis status).

### Repository Methods for Zones
**File**: `backend/app/repositories/sampling.py`

- `create_zone(case_id, label, root_hyriv_id, reach_ids, validation_status, metadata) -> CandidateZone`
- `get_zones_by_case(case_id: UUID) -> list[CandidateZone]`

No update methods exist.

### Existing Hypothesis Update Logic
**NOT IMPLEMENTED**. No code exists for:
- Computing hypothesis status from evidence assessments
- Updating zone records with new status
- Tracking status changes over time
- Triggering actions based on status transitions (e.g., ELIMINATED → stop considering zone)

---

## 5. Automatic Candidate Regeneration

### CandidateSiteGenerator
**File**: `backend/app/scientific/sampling/candidate_generator.py`

**Signature**:
```python
def generate(
    zones: list[CandidateZone],
    site_a_hyriv_id: int,
    site_a_fraction: float = 1.0,
    candidate_hyriv_ids: Iterable[int] | None = None
) -> CandidateGenerationResult
```

**Required Inputs**:
- `zones`: List of CandidateZone (must have root_hyriv_id, label)
- `site_a_hyriv_id`: Detection site reach ID
- `site_a_fraction`: Snapped position along detection reach (0.0-1.0)
- `candidate_hyriv_ids`: Optional subset of reaches to consider (defaults to all upstream)

**Returned Fields** (CandidateGenerationResult):
- `site_a_hyriv_id: int`
- `hypothesis_labels: list[str]`
- `eligible_reach_count: int`
- `equivalence_classes: list[CandidateEquivalenceClass]`
- `candidates: list[GeneratedCandidateSite]`
- `limitation: str`

**GeneratedCandidateSite Fields**:
- `hyriv_id: int`
- `latitude: float | None`
- `longitude: float | None`
- `network_distance_km: float`
- `signature: list[int]` (binary reachability vector)
- `pair_separation_score: int` (`r × (n-r)`)
- `equivalence_class: str` (e.g., "signature:011")
- `equivalent_hyriv_ids: list[int]`
- `selection_reason: str`
- `validation_status: ValidationStatus` (always VERIFIED)
- `road_access`, `safety`, `land_ownership`, `cost`, `field_accessibility`: all `NOT_EVALUATED`

**Eligibility Logic**:
1. Get all upstream reaches of detection site
2. Filter to requested subset (if provided)
3. Exclude detection site itself
4. For each reach, compute:
   - Reachability signature: binary vector indicating which zone roots can contribute
   - Network distance to detection site

**Signature Calculation**:
- For each zone, call `hydrology_engine.can_contribute(zone.root_hyriv_id, candidate_hyriv_id)`
- Result: `[int(can_contribute_Z1), int(can_contribute_Z2), int(can_contribute_Z3)]`

**Equivalence-Class Logic**:
- Group reaches by identical signature
- Compute pair-separation score: `reachable_count × (hypothesis_count - reachable_count)`
- Signatures with score = 0 (all zones reachable or none reachable) are excluded from candidates

**Representative Selection**:
- Sort reaches in each equivalence class by: (network_distance_km, hyriv_id)
- Select **nearest to detection site** as representative
- Selection reason: "Nearest network distance to Site A within this topology equivalence class. Representative selection does not imply greater ecological value."

**Generated Candidates → SamplingSite Conversion**:
Happens in `SamplingService.generate_sampling_candidates`:
- Creates transient `SamplingSite` objects with deterministic UUID (namespace-based on case_id + hyriv_id)
- `site_type=SiteType.FOLLOW_UP`
- `metadata={"status": "COUNTERFACTUAL"}`
- These are **NOT persisted to DB**

**Persistence**:
Generated candidates are NOT stored in `sampling_sites` table. They are ephemeral, returned in API response only.

---

## 6. Sampling Decision Flow

### SamplingDecisionEngine
**File**: `backend/app/scientific/sampling/engine.py` → `ScaffoldSamplingDecisionEngine`

**Public Methods**:
- `evaluate_candidates(case, zones, candidate_sites, hydrology_engine) -> list[dict]`
  - For each candidate site, computes reachability signature across zones
  - Returns: `[{site_id, site_label, signature, pair_separation_score}, ...]`
  
- `make_recommendation(evaluations) -> tuple[SamplingDecisionStatus, list[UUID], str]`
  - Returns: `(status, recommended_site_ids, rationale)`
  - Current implementation: always returns `INSUFFICIENT_DATA` with empty list and explanation
  - **Scaffold behavior**: refuses to invent recommendations without validated criteria

- `create_decision_trace(case, evaluations, status, recommended_site_ids, decision_id) -> DecisionTrace`
  - Creates audit trail with empty lists (no evidence/rules applied yet)

### SamplingService
**File**: `backend/app/services/sampling_service.py`

**Methods**:
- `evaluate_sampling_candidates(case, zones, candidate_sites) -> tuple[SamplingDecision, DecisionTrace]`
  - Calls engine's `evaluate_candidates` and `make_recommendation`
  - Saves decision + trace to DB via repository
  - Returns domain models

- `generate_sampling_candidates(case, zones, detection_site) -> tuple[CandidateGenerationResult, str, str]`
  - Calls `CandidateSiteGenerator.generate()`
  - Creates ephemeral `SamplingSite` objects
  - Calls engine's `evaluate_candidates` and `make_recommendation` on generated sites
  - Returns: `(result, decision_status_string, decision_reason)`
  - **Does NOT persist candidates or decision**

### SamplingRepository
**File**: `backend/app/repositories/sampling.py`

- `save_decision(case_id, status, recommended_site_ids, rationale, evidence_used, rules_applied, hydrology_checks, assumptions, limitations) -> tuple[SamplingDecision, DecisionTrace]`
  - Creates `SamplingDecisionModel` and `DecisionTraceModel` in single transaction
  - Flushes decision to get ID, then creates trace with that decision_id
  - Commits both

### DecisionTrace Creation
Decision trace is created by repository with provided lists (currently empty from scaffold engine). Includes:
- `evidence_used: list[UUID]`
- `rules_applied: list[str]`
- `hydrology_checks: list[dict]`
- `assumptions: list[str]`
- `limitations: list[str]`

### Decision Persistence
Decisions ARE persisted to `sampling_decisions` table. Each decision has:
- `id`, `case_id`, `status`, `recommended_site_ids`, `rationale`, `created_at`

### Multiple Decisions Per Case
**YES SUPPORTED**. No uniqueness constraint on `(case_id)`. Repository allows multiple decisions per case. API `/cases/{case_id}/decision-trace` retrieves **most recent** decision by `ORDER BY created_at DESC LIMIT 1`.

### Old Decisions Preserved
**YES**. New decisions append to table. Old decisions remain unchanged.

### Latest Decision Logic
Exists in API route: queries `SamplingDecisionModel` filtering by `case_id`, ordered by `created_at DESC`, limit 1.

---

## 7. Investigation History / Versioning

### Currently Preserved
✅ **Multiple evidence additions**: `evidence_items` table appends. No deletion. Each has `created_at`.
✅ **Multiple sampling decisions**: `sampling_decisions` table appends. Each has `created_at`.
✅ **Multiple decision traces**: `decision_traces` table appends via foreign key to decisions.
✅ **Follow-up samples**: `follow_up_samples` table appends. Each has `created_at`.

### Currently Overwritten / Not Versioned
❌ **Evidence assessments**: Not persisted. Computed on-demand.
❌ **Candidate zone definitions**: Created once. No update mechanism. No history.
❌ **Hypothesis status**: Not stored anywhere.
❌ **Candidate site generations**: Not persisted. Generated on-demand, returned in API response.

### Timestamped Tables
- `cases`: `created_at`, `updated_at`
- `evidence_items`: `created_at`
- `sampling_decisions`: `created_at`
- `decision_traces`: `created_at`
- `follow_up_samples`: `created_at`

### InvestigationRun / Revision Model
**NOT IMPLEMENTED**. No table or model exists for grouping related operations (new evidence → reassessment → regeneration → decision) into a versioned "run" or "revision".

---

## 8. Database Transaction Flow

### Session Lifecycle
**File**: `backend/app/db/session.py`

- Engine: SQLAlchemy `create_engine` with connection pool (size=5, max_overflow=10)
- Session factory: `SessionLocal = sessionmaker(autocommit=False, autoflush=False)`
- Dependency: `get_db()` yields session, closes after request

### Repository Session Pattern
Repositories receive `Session` in `__init__`:
```python
class FollowUpSampleRepository:
    def __init__(self, db: Session):
        self.db = db
```

Services receive repositories with sessions already injected.

### Commit Behavior
- **Services call `db.commit()`** after successful operations
- **Services call `db.rollback()`** in exception handlers
- Repository methods typically `db.flush()` to get IDs within transaction, then service commits

### Multiple Repository Writes in One Transaction
**YES**. Example: `FollowUpSampleService.create()`:
1. Add `FollowUpSampleModel` → `db.flush()`
2. Add `EvidenceItemModel` → `db.flush()`
3. Update `follow_up_samples.evidence_id`
4. `db.commit()`

All succeed or all rollback.

### Tables Written During Full Investigation Update

**Step 7 orchestration would write**:
1. `follow_up_samples` (new sample)
2. `evidence_items` (linked evidence)
3. **(Not implemented)** `evidence_assessments` table (if persisted)
4. **(Not implemented)** `zone_status_history` or similar (hypothesis status tracking)
5. **(Not implemented)** `generated_candidates` table (if persisted)
6. `sampling_decisions` (new decision)
7. `decision_traces` (new trace)
8. **(Not implemented)** `investigation_runs` or `investigation_revisions` (orchestration metadata)

---

## 9. Current API Contracts

### Evidence
**File**: `backend/app/api/routes/evidence.py`

| Method | Path | Request Schema | Response Schema |
|--------|------|----------------|-----------------|
| POST | `/cases/{case_id}/evidence` | `EvidenceCreateRequest` | `EvidenceResponse` |
| GET | `/cases/{case_id}/evidence` | - | `list[EvidenceResponse]` |
| GET | `/cases/{case_id}/evidence-assessment` | - | `list[AssessmentSummaryResponse]` |

**EvidenceCreateRequest**: `evidence_type`, `source`, `value`, `observed_at?`, `quality?`, `provenance?`
**EvidenceResponse**: `id`, `case_id`, `evidence_type`, `source`, `value`, `observed_at`, `quality`, `provenance`, `created_at`
**AssessmentSummaryResponse**: `zone_id`, `zone_label`, `assessments: list[EvidenceAssessmentResponse]`, `summary: {supports, contradicts, neutral, unknown}`

### Follow-Up Samples
**File**: `backend/app/api/routes/follow_up_samples.py`

| Method | Path | Request Schema | Response Schema |
|--------|------|----------------|-----------------|
| POST | `/cases/{case_id}/follow-up-samples` | `FollowUpSampleCreateRequest` | `FollowUpSampleResponse` |
| GET | `/cases/{case_id}/follow-up-samples` | - | `list[FollowUpSampleResponse]` |
| GET | `/cases/{case_id}/follow-up-samples/{sample_id}` | - | `FollowUpSampleResponse` |

**FollowUpSampleCreateRequest**: `sampling_site_id?`, `candidate_reference?`, `hyriv_id`, `sampled_at`, `replicate_count`, `positive_replicates`, `concentration?`, `concentration_unit?`, `assay`, `controls_status`, `collector_source`, `provenance`, `notes?`
**FollowUpSampleResponse**: All request fields + `id`, `case_id`, `evidence_id`, `created_at`, `reanalysis_required=True`

### Zones
**File**: `backend/app/api/routes/sampling.py`

| Method | Path | Request Schema | Response Schema |
|--------|------|----------------|-----------------|
| POST | `/cases/{case_id}/zones` | `CandidateZoneCreateRequest` | `CandidateZoneResponse` |
| GET | `/cases/{case_id}/zones` | - | `list[CandidateZoneResponse]` |

### Candidate Generation
| Method | Path | Request Schema | Response Schema |
|--------|------|----------------|-----------------|
| GET | `/cases/{case_id}/generated-candidates` | - | `CandidateGenerationResponse` |

**CandidateGenerationResponse**: `site_a_hyriv_id`, `hypothesis_labels`, `eligible_reach_count`, `equivalence_classes`, `candidates`, `decision_status`, `decision_reason`, `limitation`

### Sampling Decisions
| Method | Path | Request Schema | Response Schema |
|--------|------|----------------|-----------------|
| POST | `/cases/{case_id}/sampling-decision` | - | `SamplingDecisionResponse` |
| GET | `/cases/{case_id}/decision-trace` | - | `DecisionTraceResponse` |

**SamplingDecisionResponse**: `id`, `case_id`, `status`, `recommended_site_ids`, `rationale`, `created_at`
**DecisionTraceResponse**: `decision_id`, `evidence_used`, `rules_applied`, `hydrology_checks`, `assumptions`, `limitations`, `created_at`

### Reinvestigate Endpoint
**DOES NOT EXIST**. No `POST /cases/{case_id}/reinvestigate` or equivalent.

---

## 10. Carraro Data Inventory

### Data Files
- `eDNA_data.mat`: eDNA concentration measurements for 2 species (Fs, Tb) at 15 stations
- `data_wigger.mat`: River network morphology, drainage, coordinates
- `data_explanation.xlsx`: Field definitions (binary format, not text-readable)
- `RUN_MODEL.m`: Metropolis-within-Gibbs sampling model
- `ANALYSE_DATA.m`: Result visualization

### Station Structure
**15 stations**: S1 through S15

**eDNA_data.mat**:
- `Fs` (Fredericella sultana): struct with fields `S1`, `S2`, ..., `S15`
- `Tb` (Tetracapsuloides bryosalmonae): struct with fields `S1`, `S2`, ..., `S15`
- `Date`: struct with fields `S1`, `S2`, ..., `S15`

Each station field contains array of observations.

**Example (S1)**:
- `Fs.S1`: numpy array, shape (21,), eDNA concentrations in mol/L
- `Date.S1`: numpy array, shape (21,), MATLAB date serial numbers
- Observation index 4: date=735775 (2014-06-25), concentration=1.29832198e-17 mol/L

### Taxa
- **Fs**: Fredericella sultana (bryozoan)
- **Tb**: Tetracapsuloides bryosalmonae (myxozoan parasite)

### Observation Structure
- Each station has multiple temporal observations (variable count per station)
- Date format: MATLAB datenum (days since 0000-01-01, with 366-day offset correction)
- Concentration: mol/L (float, 0.0 = non-detection)
- **Approximate usable observations**: ~21 per station for S1 (varies by station)

### Station Coordinates
**RUN_MODEL.m**:
```matlab
station_coord=[634537.17  240447.56  1;   % Row 1 only extracted so far
```
- Column 1: X coordinate (Swiss LV03)
- Column 2: Y coordinate (Swiss LV03)
- Column 3: Carraro reach index (internal network ID, 1-based)

Only first row coordinates extracted in tests. **Assumption**: Additional rows exist for other stations.

### HydroRIVERS Mapping
**Currently mapped**:
- Station S1 (Carraro reach index 1) → HYRIV_ID 20446064 (Site A in preflight)

**NOT mapped**: Stations S2-S15. No crosswalk exists between Carraro reach indices and HYRIV_IDs for these stations.

### Historical Ground Truth
**Observed**: S1 Fs detection on 2014-06-25 at 1.29832198e-17 mol/L (index 4 of 21 observations).

**Temporal series**: Each station has dated observations. Can compare detection/non-detection patterns over time.

**Upstream/Downstream Relationships**: `data_wigger.mat` contains network topology (`reach_upstream`, `outlet`), but no explicit upstream/downstream station pairings documented.

---

## 11. Held-Out Validation Feasibility

### A. Held-Out Station Validation
**PARTIALLY SUPPORTED**

**Data**: 15 stations, only S1 mapped to HYRIV_ID. Multiple observations per station.

**Possible**:
- Hold out S1 entirely, use S2-S15 for "training" (zone definition)
- Predict whether S1 should detect Fs based on network topology + other station detections
- Compare prediction to actual S1 observation (2014-06-25 detection)

**Limitation**: Requires mapping S2-S15 to HydroRIVERS. Current system only has S1 crosswalk.

**Verdict**: Requires additional data engineering (station coordinate → HYRIV_ID mapping for S2-S15).

---

### B. Held-Out Observation Validation
**SUPPORTED BY DATA**

**Data**: S1 has 21 temporal observations. Other stations have similar series.

**Possible**:
- Hold out specific S1 observations (e.g., index 4)
- Use remaining S1 observations + network + zones to predict held-out observation state
- Temporal cross-validation: train on dates 1-15, test on dates 16-21

**Why genuine**: Observations are independent temporal samples. Holding out a specific date is valid scientific validation.

**Verdict**: SUPPORTED. Can test whether system would correctly predict detection/non-detection at held-out dates.

---

### C. Upstream/Downstream Detection Comparison
**PARTIALLY SUPPORTED**

**Data**: Multiple stations exist. Network topology in `data_wigger.mat` includes `reach_upstream` relationships.

**Possible**:
- If stations are upstream/downstream of each other in network, compare detections
- Test whether upstream detection predicts downstream detection (transport hypothesis)

**Limitation**: Requires:
1. Mapping all stations to HydroRIVERS
2. Identifying which station pairs are upstream/downstream
3. Carraro network != HydroRIVERS network (internal reach indices vs. HYRIV_IDs)

**Verdict**: Data structure supports concept, but requires significant preprocessing and network alignment.

---

### D. Candidate-Site Outcome Validation
**PARTIALLY SUPPORTED**

**Data**: System generates candidates at specific HYRIV_IDs. If any candidate HYRIV_ID matches a real historical sampling station, we can compare recommendation to observed outcome.

**Possible**:
- Generate candidates for Wigger case (Z1, Z2, Z3 zones)
- Check if any generated candidate HYRIV_ID == S2-S15 historical station
- If match exists: "System recommended this site" vs. "Site detected/did not detect Fs"

**Limitation**:
- Requires mapping S2-S15 to HYRIV_IDs
- Historical stations may not align with generated candidates (different selection criteria in 2014 study)
- Generated candidates optimize for topology discrimination, not historical sampling design

**Verdict**: Theoretically possible if station mappings exist. Provides weak validation (historical sampling not designed by current algorithm).

---

### E. Next-Sampling Decision Validation
**PARTIALLY SUPPORTED**

**Data**: If we can reconstruct system state as of date D (zones, initial evidence, recommendations), then check whether following the recommendation led to informative result at date D+1.

**Possible**:
- Simulate: "Given S1 detection on 2014-06-25, system recommends site X"
- Check: Did historical data include follow-up sampling at X? If yes, was result informative?

**Limitation**:
- Historical study did not use this algorithm
- No record of "which site was sampled because of which prior evidence"
- Temporal sequence of sampling decisions unknown

**Verdict**: Data structure supports concept (temporal observations exist), but lacks decision provenance (why station X was sampled after station Y).

---

### Can We Test Whether Algorithm-Recommended Site Would Have Been More Informative?
**PARTIALLY / NO**

**Question**: If system recommends site B (generated candidate), would historical sampling at B have produced more informative result than actual sampling at S2?

**Requirements**:
1. Map S2 (actual historical site) to HYRIV_ID ✅ (possible if coordinates exist)
2. Map generated candidate B to HYRIV_ID ✅ (already done)
3. Know historical eDNA result at both S2 and B ❌ (only have data for actually-sampled stations)
4. Define "more informative" quantitatively ✅ (pair-separation score, zone elimination)

**What supports**: Multiple stations with detections/non-detections. If a generated candidate matches S2-S15, we have ground truth.

**What blocks**: Cannot retroactively sample at counterfactual locations. Only have observations where historical study actually sampled.

**Verdict**: **PARTIALLY**. Can validate: "System recommended S5 (high pair-separation). S5 historically detected Fs, confirming zone Z2 is supported." Cannot validate: "System recommended unsampled location X. Would X have been better than S2?"

---

## 12. Existing Test Guarantees

### Wigger Tests
**File**: `backend/tests/unit/test_wigger_scientific_regression.py`

✅ Site A matched representation separate from observation coordinate (snap validation)
✅ Demo uses verified Carraro H001 observation (S1, Fs, index 4, 2014-06-25, 1.29832198e-17 mol/L)
✅ Network topology: 48 upstream reaches, correct first common downstream, downstream paths
✅ Zone exclusivity: Z1, Z2, Z3 reach sets are mutually disjoint
✅ Reachability signatures: {A: [1,1,1], B: [0,1,0], C: [0,0,1], D: [0,1,1]}
✅ Snapped Site A distances match preflight validation
✅ Automatic candidate generation: 48 eligible, 5 equivalence classes, correct pair-separation scores
✅ Representative selection: nearest to Site A, excludes Site A itself

### Carraro Validation Tests
**File**: `backend/tests/unit/test_carraro_validation.py`

✅ H001 real source and RUN_MODEL.m station coordinates match
✅ Observed data preserved distinct from counterfactual follow-up sites
✅ Historical observation remains `UNKNOWN` compatibility (no validated rule)
✅ Topology evidence for Z1, Z2, Z3 all `SUPPORTS` (all zones can contribute to S1)
✅ Sampling engine returns TIE with all candidates (B, C, D) at max score=2
✅ No replicate fields in historical observation (future follow-up distinction preserved)

### Candidate Generation Tests
✅ Eligible reach count correct
✅ Equivalence classes have correct signatures and pair-separation scores
✅ Representatives selected by nearest distance
✅ Site A excluded from candidates
✅ Generated candidates have latitude/longitude (from reach_geometries)
✅ All generated candidates have `field_accessibility=NOT_EVALUATED`

### Evidence Direction Tests
✅ Directed connectivity evidence produces SUPPORTS/CONTRADICTS/NEUTRAL based on `can_contribute`
✅ Different zone root produces NEUTRAL
✅ Missing/unverified network status produces UNKNOWN
✅ Unsupported evidence types produce UNKNOWN

### Evidence Strength Tests
✅ Hydrological-connectivity strength: HIGH (all criteria), MEDIUM (topology complete, graph coverage unstated), LOW (unverified)
✅ Strength rule is claim-specific (does not assess biology, transport, decay, abundance, assay quality)
✅ Unsupported evidence types: `UNASSESSED`

### Urban Context Tests
✅ GHSL urbanization context provider returns structured metadata (source year, resolution, spatial window, version, provenance)
✅ Provider outcomes isolated: SUCCESS/PARTIAL/UNAVAILABLE/ERROR
✅ Urbanization evidence assesses as `UNKNOWN` compatibility, `UNASSESSED` strength

### One Health Tests
✅ F. sultana eDNA observation triggers Fs/Tb/PKD pathway
✅ Claims labeled: OBSERVED, SUPPORTED_RELATIONSHIP, POSSIBLE_RELEVANCE, UNKNOWN
✅ No aggregate score, no disease probability, no human-health diagnosis
✅ Peer-reviewed sources included (Morris & Adams 2007, Sudhagar et al. 2020)

### Follow-Up Sample Tests
✅ Validation: replicate counts, concentration/unit pairing, HYRIV_ID validity
✅ Atomic transaction: sample + evidence creation, rollback on failure
✅ Response returns `reanalysis_required=true`
✅ Submission does not trigger reassessment (tested implicitly by lack of downstream calls)

---

## 13. Relevant File Map

### Follow-Up Workflow
- Domain: `backend/app/domain/models.py` → `FollowUpSample`
- DB Model: `backend/app/db/models.py` → `FollowUpSampleModel`
- Repository: `backend/app/repositories/follow_up_samples.py`
- Service: `backend/app/services/follow_up_sample_service.py`
- Schema: `backend/app/schemas/follow_up_samples.py`
- API: `backend/app/api/routes/follow_up_samples.py`
- Tests: `backend/tests/unit/test_follow_up_samples.py`

### Evidence Assessment
- Domain: `backend/app/domain/models.py` → `EvidenceItem`, `EvidenceAssessment`
- DB Model: `backend/app/db/models.py` → `EvidenceItemModel`
- Repository: `backend/app/repositories/evidence.py`
- Service: `backend/app/services/evidence_service.py`
- Engine: `backend/app/scientific/evidence/engine.py` → `EvidenceCompatibilityEngineImpl`
- Rules: `backend/app/scientific/rules/catalog.py`
- Schema: `backend/app/schemas/evidence.py`
- API: `backend/app/api/routes/evidence.py`
- Tests: `backend/tests/property/test_evidence_properties.py`

### Hypotheses / Zones
- Domain: `backend/app/domain/models.py` → `CandidateZone`
- Enums: `backend/app/domain/enums.py` → `HypothesisStatus` (defined but unused)
- DB Model: `backend/app/db/models.py` → `CandidateZoneModel`
- Repository: `backend/app/repositories/sampling.py` → zone methods
- Schema: `backend/app/schemas/sampling.py` → `CandidateZoneCreateRequest`, `CandidateZoneResponse`
- API: `backend/app/api/routes/sampling.py` → zone endpoints

### Candidate Generation
- Domain: `backend/app/domain/models.py` → `CandidateGenerationResult`, `GeneratedCandidateSite`, `CandidateEquivalenceClass`
- Engine: `backend/app/scientific/sampling/candidate_generator.py` → `CandidateSiteGenerator`
- Service: `backend/app/services/sampling_service.py` → `generate_sampling_candidates`
- Schema: `backend/app/schemas/sampling.py` → `CandidateGenerationResponse`
- API: `backend/app/api/routes/sampling.py` → `GET /cases/{case_id}/generated-candidates`
- Tests: `backend/tests/unit/test_wigger_scientific_regression.py::test_wigger_automatic_candidate_generation`

### Sampling Decisions
- Domain: `backend/app/domain/models.py` → `SamplingDecision`, `DecisionTrace`
- DB Models: `backend/app/db/models.py` → `SamplingDecisionModel`, `DecisionTraceModel`
- Repository: `backend/app/repositories/sampling.py` → `save_decision`, `get_decision_by_id`, `get_trace_by_decision_id`
- Service: `backend/app/services/sampling_service.py` → `evaluate_sampling_candidates`
- Engine: `backend/app/scientific/sampling/engine.py` → `ScaffoldSamplingDecisionEngine`
- Schema: `backend/app/schemas/sampling.py` → `SamplingDecisionResponse`, `DecisionTraceResponse`
- API: `backend/app/api/routes/sampling.py` → decision/trace endpoints

### Repositories
- Cases: `backend/app/repositories/cases.py`
- Evidence: `backend/app/repositories/evidence.py`
- Sampling: `backend/app/repositories/sampling.py`
- Follow-up: `backend/app/repositories/follow_up_samples.py`

### DB Models & Session
- Base: `backend/app/db/base.py`
- Models: `backend/app/db/models.py`
- Session: `backend/app/db/session.py`
- Migrations: `backend/alembic/versions/`

### Schemas
- Cases: `backend/app/schemas/cases.py`
- Evidence: `backend/app/schemas/evidence.py`
- Sampling: `backend/app/schemas/sampling.py`
- Follow-up: `backend/app/schemas/follow_up_samples.py`
- Context: `backend/app/schemas/context.py`
- Hydrology: `backend/app/schemas/hydrology.py`
- One Health: `backend/app/schemas/one_health.py`

### API Routes
- Cases: `backend/app/api/routes/cases.py`
- Evidence: `backend/app/api/routes/evidence.py`
- Sampling: `backend/app/api/routes/sampling.py`
- Follow-up: `backend/app/api/routes/follow_up_samples.py`
- Hydrology: `backend/app/api/routes/hydrology.py`
- Demo: `backend/app/api/routes/demo.py`

### Regression Tests
- Wigger: `backend/tests/unit/test_wigger_scientific_regression.py`
- Wigger loader: `backend/tests/unit/test_wigger_loader.py`
- Carraro: `backend/tests/unit/test_carraro_validation.py`
- V3 boundaries: `backend/tests/unit/test_v3_scientific_boundaries.py`

### Carraro Data
- eDNA measurements: `data_preflight/raw/carraro/eDNA_data.mat`
- Network morphology: `data_preflight/raw/carraro/data_wigger.mat`
- Field definitions: `data_preflight/raw/carraro/data_explanation.xlsx`
- Model code: `data_preflight/raw/carraro/RUN_MODEL.m`, `ANALYSE_DATA.m`
- Documentation: `data_preflight/raw/carraro/README.md`

---

## Summary for V4 Planning

### Step 7 Orchestration Currently Exists?
**NO**. No endpoint, service method, or workflow exists to trigger:
1. Evidence reassessment after new follow-up sample
2. Hypothesis status update based on assessments
3. Automatic candidate regeneration
4. New sampling decision creation

All components exist in isolation. Orchestration layer missing.

### Genuine Held-Out Validation Appears Feasible?
**PARTIALLY**

**What IS feasible**:
- ✅ Temporal cross-validation: hold out specific observation dates, predict detection state
- ✅ Candidate recommendation validation: if generated candidate matches historical station S2-S15, compare recommendation to observed outcome
- ✅ Evidence assessment correctness: verify SUPPORTS/CONTRADICTS matches ground truth reachability

**What IS NOT feasible without additional work**:
- ❌ Held-out station validation: requires mapping S2-S15 to HYRIV_IDs
- ❌ Counterfactual site comparison: cannot sample at unsampled locations retroactively
- ❌ Decision sequence validation: historical study lacks provenance of why/when stations were sampled

**Overall**: Partial validation possible with current data. Full biological validation (does zone X truly contain species?) requires ground truth surveys, not available in historical eDNA dataset.

---

**Files Inspected**: 28
**Step 7 Orchestration Exists**: NO
**Held-Out Validation Feasible**: PARTIALLY
