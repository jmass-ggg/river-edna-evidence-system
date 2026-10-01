# V3 Prompt Context

## Purpose

This document provides the compact technical context extracted from the V2 eDNA Evidence Investigator system. It contains only the essential information needed to understand the system's architecture, models, APIs, and frozen behaviors.

---

## 1. V2 Status & Limitations

### From UPGRADE_V2_REPORT.md

**Final V2 Verification:**
- Full suite: 102 passed, 0 failed, 15 warnings
- Coverage: 75% overall
- Wigger regression: 7 passed
- Carraro regression: 3 passed
- Sampling properties: 12 passed
- Evidence properties: 12 passed
- Scientific coverage: hydrology 96%, evidence 97%, sampling 93%, candidate generator 93%, rule catalog 100%

**Generated Candidates:**
- Eligible validated upstream reaches: 48 (Site A excluded)
- Hypothesis order: deterministic (Z1, Z2, Z3)
- Equivalence classes: [0,0,0] (39 reaches, score 0), [0,0,1] (1, score 2), [0,1,0] (1, score 2), [0,1,1] (6, score 2), [1,0,0] (1, score 2)
- Representatives: 20451169 (C), 20450127 (B), 20446568, 20447392
- B and C naturally reproduced
- D (20448315) belongs to [0,1,1] class but not selected (20446568 is nearer to Site A)
- Decision result: TIE under pair-separation criterion

**Evidence Strength:**
- Direction values unchanged: SUPPORTS, CONTRADICTS, NEUTRAL, UNKNOWN
- New rule: `hydrorivers.directed_connectivity_strength.v1`
- HIGH: validated mapping + validated zones + complete topology + explicit graph coverage
- MEDIUM: validated mapping + validated zones + complete topology (no explicit graph-coverage metadata)
- LOW: missing validation or topology completeness
- UNASSESSED: unsupported evidence types
- Strength is metadata only; does not affect sampling scores
- No numeric confidence or biological occurrence probability

**Known Limitations:**
- Topology score is NOT eDNA detection probability
- Candidate optimization: topology-based hypothesis discrimination only
- NOT modeled: field accessibility, cost, transport, decay, abundance
- Evidence strength is claim-specific; unsupported evidence remains UNASSESSED
- Counterfactual sites are NOT historical measurements
- Representative selection does NOT imply ecological value

### From SCIENCE_FREEZE_v2.md

**What Is Frozen:**
- HydrologyEngine directed network and distance semantics
- Evidence direction: SUPPORTS, CONTRADICTS, NEUTRAL, UNKNOWN
- Sampling criterion: pair-separation score `r × (n-r)`
- Carraro H001: S1, Fredericella sultana (Fs), observation 4, 2014-06-25, 1.29832198e-17 mol/L, DETECTED
- Wigger Site A mapping: HYRIV_ID 20446064
- SCIENCE_FREEZE_v1.md, SCIENCE_FREEZE_v1.sha256, all frozen v1 input/source data: UNEDITED

**What Changed in V2:**
- Stable repository-root preflight path handling
- Working Wigger demo using independently loaded Carraro H001
- Automatic candidate generation
- Deterministic topology equivalence classes
- Claim-specific evidence strength metadata

**What Must NOT Be Modified:**
- Scientific semantics listed above
- Any v1 frozen data or checksums
- v1 scientific code semantics (v2 is forward-versioned)

**Change Policy:**
- Any scientific change requires: scientific justification, Wigger and Carraro regressions, candidate-generation and evidence-strength regressions, full test suite, new checksum manifest, new freeze version

---

## 2. Domain Enums

### From backend/app/domain/enums.py

```python
class EvidenceCompatibility(str, Enum):
    SUPPORTS = "SUPPORTS"          # Consistent with hypothesis
    CONTRADICTS = "CONTRADICTS"    # Inconsistent with hypothesis
    NEUTRAL = "NEUTRAL"            # Neither supports nor contradicts
    UNKNOWN = "UNKNOWN"            # No validated rule applies

class EvidenceStrength(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNASSESSED = "UNASSESSED"

class CandidateConstraintStatus(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"

class HypothesisStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    POSSIBLE = "POSSIBLE"
    WEAKENED = "WEAKENED"
    CONFLICTING = "CONFLICTING"
    ELIMINATED = "ELIMINATED"
    UNKNOWN = "UNKNOWN"

class SamplingDecisionStatus(str, Enum):
    RECOMMEND = "RECOMMEND"              # One or more sites clearly recommended
    TIE = "TIE"                          # Multiple sites have equal value
    ABSTAIN = "ABSTAIN"                  # No basis for preference
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

class ValidationStatus(str, Enum):
    MATCHED = "MATCHED"                  # Validated network crosswalk
    VERIFIED = "VERIFIED"                # Independently verified
    SUPPORTED = "SUPPORTED"              # Has supporting evidence
    ASSUMPTION = "ASSUMPTION"            # Assumed correct but not verified
    NOT_VERIFIED = "NOT_VERIFIED"

class SiteType(str, Enum):
    DETECTION_SITE = "DETECTION_SITE"
    BRANCH_SPECIFIC = "BRANCH_SPECIFIC"
    SHARED_TRUNK = "SHARED_TRUNK"
    FOLLOW_UP = "FOLLOW_UP"

class CaseStatus(str, Enum):
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"
```

---

## 3. Domain Models

### From backend/app/domain/models.py

**Core Fields Only (excluding default_factory, basic types understood):**

```python
@dataclass
class Case:
    id: UUID
    target_taxon: str
    observation_date: date
    detection_site_id: UUID
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]

@dataclass
class SamplingSite:
    id: UUID
    case_id: UUID | None
    label: str
    latitude: float
    longitude: float
    hyriv_id: int
    site_type: SiteType
    validation_status: ValidationStatus
    network_latitude: float | None
    network_longitude: float | None
    snap_distance_m: float | None
    role: str | None
    metadata: dict[str, Any]

@dataclass
class RiverReach:
    hyriv_id: int
    next_down: int | None
    length_km: float
    upland_skm: float
    dis_av_cms: float
    geometry: Any | None

@dataclass
class CandidateZone:
    id: UUID
    case_id: UUID
    label: str
    root_hyriv_id: int
    reach_ids: list[int]
    validation_status: ValidationStatus
    metadata: dict[str, Any]

@dataclass
class EvidenceItem:
    id: UUID
    case_id: UUID
    evidence_type: str
    source: str
    value: Any
    observed_at: datetime | None
    quality: str | None
    provenance: dict[str, Any]
    created_at: datetime

@dataclass
class EvidenceAssessment:
    evidence_id: UUID
    compatibility: EvidenceCompatibility
    rule_id: str | None
    reason: str
    provenance: dict[str, Any]
    strength: EvidenceStrength
    strength_criteria: list[dict[str, Any]]
    strength_reason: str
    strength_rule_id: str | None
    strength_rule_version: str | None
    strength_provenance: dict[str, Any]
    strength_limitations: list[str]

@dataclass
class CandidateEquivalenceClass:
    equivalence_class: str
    signature: list[int]
    pair_separation_score: int
    hyriv_ids: list[int]
    representative_hyriv_id: int | None

@dataclass
class GeneratedCandidateSite:
    hyriv_id: int
    latitude: float | None
    longitude: float | None
    network_distance_km: float
    signature: list[int]
    pair_separation_score: int
    equivalence_class: str
    equivalent_hyriv_ids: list[int]
    selection_reason: str
    validation_status: ValidationStatus
    road_access: CandidateConstraintStatus
    safety: CandidateConstraintStatus
    land_ownership: CandidateConstraintStatus
    cost: CandidateConstraintStatus
    field_accessibility: CandidateConstraintStatus

@dataclass
class CandidateGenerationResult:
    site_a_hyriv_id: int
    hypothesis_labels: list[str]
    eligible_reach_count: int
    equivalence_classes: list[CandidateEquivalenceClass]
    candidates: list[GeneratedCandidateSite]
    limitation: str

@dataclass
class SamplingDecision:
    id: UUID
    case_id: UUID
    status: SamplingDecisionStatus
    recommended_site_ids: list[UUID]
    rationale: str
    created_at: datetime

@dataclass
class DecisionTrace:
    decision_id: UUID
    evidence_used: list[UUID]
    rules_applied: list[str]
    hydrology_checks: list[dict[str, Any]]
    assumptions: list[str]
    limitations: list[str]
    created_at: datetime
```

---

## 4. Scientific Engines

### Evidence Compatibility Engine

**From backend/app/scientific/evidence/engine.py:**

```python
class EvidenceCompatibilityEngineImpl:
    def assess_evidence_for_zone(
        self,
        case: Case,
        zone: CandidateZone,
        evidence_items: list[EvidenceItem],
        scientific_rules: list[dict[str, Any]],
    ) -> list[EvidenceAssessment]:
        """Assess each evidence item for one candidate-zone hypothesis."""
        # Returns list of EvidenceAssessment with:
        # - compatibility (SUPPORTS/CONTRADICTS/NEUTRAL/UNKNOWN)
        # - rule_id (or None if no rule applies)
        # - strength (HIGH/MEDIUM/LOW/UNASSESSED)
        # - strength_criteria, strength_reason, strength_limitations
        
    def summarize_zone_assessment(
        self,
        assessments: list[EvidenceAssessment],
    ) -> dict[str, int]:
        """Count assessments by compatibility state."""
        # Returns: {"supports": N, "contradicts": M, "neutral": P, "unknown": Q}
```

**Key Logic:**
- Uses topology rule `hydrorivers.directed_contribution.v1`
- Uses strength rule `hydrorivers.directed_connectivity_strength.v1`
- Unsupported evidence → compatibility=UNKNOWN, strength=UNASSESSED
- Direction and strength are independent

### Rule Catalog

**From backend/app/scientific/rules/catalog.py:**

```python
TOPOLOGY_CONTRIBUTION_RULE = {
    "id": "hydrorivers.directed_contribution.v1",
    "version": "1.0.0",
    "condition": {
        "evidence_type": "directed_hydrological_connectivity",
        "required_value_fields": [
            "zone_root_hyriv_id",
            "site_hyriv_id",
            "can_contribute",
            "network_validation_status",
        ],
        "accepted_network_statuses": ["VERIFIED", "SUPPORTED", "MATCHED"],
    },
    "effect": {
        "can_contribute=true": "SUPPORTS",
        "can_contribute=false": "CONTRADICTS",
        "different_zone_root": "NEUTRAL",
        "missing_or_unverified": "UNKNOWN",
    },
    "limitations": [
        "Reachability is evaluated at mapped-reach resolution.",
        "Connectivity does not establish eDNA transport, persistence, detection, biological presence, or abundance.",
        "CONTRADICTS applies only to represented-network hydrological contribution.",
    ],
    "validation_status": "VERIFIED",
}

TOPOLOGY_STRENGTH_RULE = {
    "id": "hydrorivers.directed_connectivity_strength.v1",
    "version": "1.0.0",
    "evidence_type": "directed_hydrological_connectivity",
    "criteria": [
        "network mapping validation",
        "zone root validation",
        "complete directed topology evaluation",
        "validated graph coverage",
    ],
    "effect": {
        "all_criteria_validated": "HIGH",
        "topology_complete_graph_coverage_unstated": "MEDIUM",
        "unverified_or_missing_topology": "LOW",
        "unsupported_evidence_type": "UNASSESSED",
    },
    "limitations": [
        "Strength applies only to the hydrological-connectivity claim.",
        "It is not the probability that the species occurs at a location.",
        "It does not assess transport, decay, abundance, assay quality, or detection probability.",
    ],
    "validation_status": "VERIFIED",
}

def get_rule_catalog() -> list[dict[str, Any]]:
    """Return defensive copy of direction rules."""

def get_strength_rule_catalog() -> list[dict[str, Any]]:
    """Return defensive copy of strength rules."""
```

### Candidate Generator

**From backend/app/scientific/sampling/candidate_generator.py:**

```python
class CandidateSiteGenerator:
    def __init__(
        self,
        hydrology_engine: HydrologyEngine,
        reach_coordinates: dict[int, tuple[float, float]] | None = None,
    ):
        ...
    
    def generate(
        self,
        zones: list[CandidateZone],
        site_a_hyriv_id: int,
        site_a_fraction: float = 1.0,
        candidate_hyriv_ids: Iterable[int] | None = None,
    ) -> CandidateGenerationResult:
        """Generate one nearest-to-A representative per useful signature."""
        # Logic:
        # 1. Get validated upstream reaches of site_a
        # 2. Exclude site_a itself
        # 3. For each reach: compute signature = [can_reach_Z1, can_reach_Z2, ...]
        # 4. Group by signature into equivalence classes
        # 5. Score each class: reachable_count × (hypothesis_count - reachable_count)
        # 6. For classes with score > 0: select nearest reach to site_a as representative
        # 7. Sort candidates by: (-score, equivalence_class, distance, hyriv_id)
```

**Output:**
- `CandidateGenerationResult` with equivalence classes and candidates
- Each candidate has: signature, score, validation_status=VERIFIED, constraint statuses=NOT_EVALUATED

### Sampling Decision Engine

**From backend/app/scientific/sampling/engine.py:**

```python
DISCRIMINATION_RULE_ID = "sampling.topology_pair_separation.v1"

class ScaffoldSamplingDecisionEngine:
    def evaluate_candidates(
        self,
        case: Case,
        zones: list[CandidateZone],
        candidate_sites: list[SamplingSite],
        hydrology_engine: HydrologyEngine,
    ) -> list[dict[str, Any]]:
        """Calculate reachability signatures and pair separation per site."""
        # For each site:
        #   signature = [zone1_can_reach, zone2_can_reach, ...]
        #   separated_pairs = reachable_count × (hypothesis_count - reachable_count)
        # Returns list with: site_id, signature, scores, hydrology_checks, rationale
    
    def make_recommendation(
        self,
        evaluations: list[dict[str, Any]],
    ) -> tuple[SamplingDecisionStatus, list[UUID], str]:
        """Choose strict pair-separation winner, tie, or abstain."""
        # RECOMMEND: one site with max score
        # TIE: multiple sites with max score
        # ABSTAIN: score 0 or ≤1 hypothesis
        # INSUFFICIENT_DATA: incomplete validation or inconsistent hypothesis sets
    
    def create_decision_trace(
        self,
        case: Case,
        evaluations: list[dict[str, Any]],
        status: SamplingDecisionStatus,
        recommended_site_ids: list[UUID],
        decision_id: UUID,
    ) -> DecisionTrace:
        """Create auditable trace for decision."""
```

### Hydrology Engine

**From backend/app/scientific/hydrology/engine.py:**

**Public Methods:**

```python
class HydrologyEngine:
    def __init__(self, reaches: pd.DataFrame, edges: pd.DataFrame):
        """Initialize with HydroRIVERS data."""
        # reaches columns: HYRIV_ID, NEXT_DOWN, LENGTH_KM, UPLAND_SKM, DIS_AV_CMS
        # edges columns: upstream, downstream
    
    def get_reach(self, hyriv_id: int) -> RiverReach:
        """Retrieve reach metadata by HYRIV_ID."""
    
    def get_upstream_reaches(self, hyriv_id: int) -> list[int]:
        """Return all reach IDs that flow toward the specified reach."""
    
    def get_downstream_path(
        self, start_hyriv_id: int, stop_hyriv_id: int | None = None
    ) -> list[int]:
        """Return ordered reach IDs from start to stop (or terminus)."""
    
    def is_upstream(self, source_hyriv_id: int, target_hyriv_id: int) -> bool:
        """Check if source reach flows toward target reach."""
    
    def can_contribute(self, source_hyriv_id: int, site_hyriv_id: int) -> bool:
        """Return whether a source reach can reach a site at reach resolution."""
        # Same reach or upstream relationship
    
    def first_common_downstream(self, hyriv_id_a: int, hyriv_id_b: int) -> int | None:
        """Find where two branches converge."""
    
    def network_distance_km(
        self,
        from_hyriv_id: int,
        to_hyriv_id: int,
        from_fraction: float = 0.5,
        to_fraction: float = 0.5,
    ) -> float | None:
        """Calculate network distance using LENGTH_KM."""
        # Returns None if not connected
    
    def zone_can_contribute_to_site(
        self, zone_reaches: list[int], site_hyriv_id: int
    ) -> bool:
        """Check if any reach in zone flows to site."""
```

---

## 5. Schemas (API Request/Response)

### Evidence Schemas

**From backend/app/schemas/evidence.py:**

```python
class EvidenceCreateRequest(BaseModel):
    evidence_type: str
    source: str
    value: Any
    observed_at: datetime | None
    quality: str | None
    provenance: dict[str, Any]

class EvidenceResponse(BaseModel):
    id: UUID
    case_id: UUID
    evidence_type: str
    source: str
    value: Any
    observed_at: datetime | None
    quality: str | None
    provenance: dict[str, Any]
    created_at: datetime

class EvidenceAssessmentResponse(BaseModel):
    evidence_id: UUID
    compatibility: EvidenceCompatibility
    rule_id: str | None
    reason: str
    provenance: dict[str, Any]
    strength: EvidenceStrength
    strength_criteria: list[dict[str, Any]]
    strength_reason: str
    strength_rule_id: str | None
    strength_rule_version: str | None
    strength_provenance: dict[str, Any]
    strength_limitations: list[str]

class AssessmentSummaryResponse(BaseModel):
    zone_id: UUID
    zone_label: str
    assessments: list[EvidenceAssessmentResponse]
    summary: dict[str, int]  # {"supports": N, "contradicts": M, ...}
```

### Sampling Schemas

**From backend/app/schemas/sampling.py:**

```python
class SamplingSiteCreateRequest(BaseModel):
    label: str
    latitude: float
    longitude: float
    hyriv_id: int
    site_type: SiteType
    validation_status: ValidationStatus
    network_latitude: float | None
    network_longitude: float | None
    snap_distance_m: float | None
    role: str | None
    metadata: dict[str, Any]

class SamplingSiteResponse(BaseModel):
    id: UUID
    case_id: UUID | None
    label: str
    latitude: float
    longitude: float
    hyriv_id: int
    site_type: SiteType
    validation_status: ValidationStatus
    network_latitude: float | None
    network_longitude: float | None
    snap_distance_m: float | None
    role: str | None
    metadata: dict[str, Any]

class CandidateZoneCreateRequest(BaseModel):
    label: str
    root_hyriv_id: int
    reach_ids: list[int]
    validation_status: ValidationStatus
    metadata: dict[str, Any]

class CandidateZoneResponse(BaseModel):
    id: UUID
    case_id: UUID
    label: str
    root_hyriv_id: int
    reach_ids: list[int]
    validation_status: ValidationStatus
    metadata: dict[str, Any]

class GeneratedCandidateResponse(BaseModel):
    hyriv_id: int
    latitude: float | None
    longitude: float | None
    network_distance_km: float
    signature: list[int]
    pair_separation_score: int
    equivalence_class: str
    equivalent_hyriv_ids: list[int]
    selection_reason: str
    validation_status: ValidationStatus
    road_access: CandidateConstraintStatus
    safety: CandidateConstraintStatus
    land_ownership: CandidateConstraintStatus
    cost: CandidateConstraintStatus
    field_accessibility: CandidateConstraintStatus

class CandidateGenerationResponse(BaseModel):
    site_a_hyriv_id: int
    hypothesis_labels: list[str]
    eligible_reach_count: int
    equivalence_classes: list[CandidateEquivalenceClassResponse]
    candidates: list[GeneratedCandidateResponse]
    decision_status: SamplingDecisionStatus
    decision_reason: str
    limitation: str

class SamplingDecisionResponse(BaseModel):
    id: UUID
    case_id: UUID
    status: SamplingDecisionStatus
    recommended_site_ids: list[UUID]
    rationale: str
    created_at: datetime

class DecisionTraceResponse(BaseModel):
    decision_id: UUID
    evidence_used: list[UUID]
    rules_applied: list[str]
    hydrology_checks: list[dict[str, Any]]
    assumptions: list[str]
    limitations: list[str]
    created_at: datetime
```

---

## 6. Services (Public Methods Only)

### Evidence Service

**From backend/app/services/evidence_service.py:**

```python
class EvidenceService:
    def __init__(
        self,
        evidence_repository: EvidenceRepository,
        evidence_engine: EvidenceCompatibilityEngine
    ):
        ...
    
    def add_evidence(
        self,
        case_id: UUID,
        evidence_type: str,
        source: str,
        value: Any,
        observed_at: Optional[datetime] = None,
        quality: Optional[str] = None,
        provenance: Optional[dict] = None
    ) -> EvidenceItem:
        """Add new evidence item to a case."""
    
    def get_evidence_for_case(self, case_id: UUID) -> list[EvidenceItem]:
        """Retrieve all evidence items for a case."""
    
    def assess_evidence_for_zones(
        self,
        case: Case,
        zones: list[CandidateZone],
        scientific_rules: Optional[list[dict[str, Any]]] = None
    ) -> dict[str, dict[str, Any]]:
        """Assess evidence compatibility for all candidate zones."""
        # Returns: {
        #   "Z1": {"zone_id": UUID, "assessments": [...], "summary": {...}},
        #   ...
        # }
```

---

## 7. API Endpoints

### Evidence Routes

**From backend/app/api/routes/evidence.py:**

```
POST /cases/{case_id}/evidence
  - Body: EvidenceCreateRequest
  - Response: EvidenceResponse (201)
  - Validates: Requirements 5.1, 5.2, 13.1, 13.4, 18.1, 18.3

GET /cases/{case_id}/evidence
  - Response: list[EvidenceResponse]
  - Validates: Requirements 5.2, 18.1, 18.3

GET /cases/{case_id}/evidence-assessment
  - Response: list[AssessmentSummaryResponse]
  - Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 13.1, 13.4, 18.1, 18.3
```

---

## 8. Database Tables

### From backend/app/db/models.py

**Table: cases**
- id (UUID, PK)
- target_taxon (String)
- observation_date (Date)
- detection_site_id (UUID, FK → sampling_sites.id)
- status (String)
- created_at, updated_at (DateTime)
- meta (JSONB)

**Table: sampling_sites**
- id (UUID, PK)
- case_id (UUID, FK → cases.id, nullable)
- label, latitude, longitude (String, Float, Float)
- hyriv_id (Integer)
- site_type, validation_status (String)
- network_latitude, network_longitude, snap_distance_m (Float, nullable)
- role (String, nullable)
- meta (JSONB)

**Table: candidate_zones**
- id (UUID, PK)
- case_id (UUID, FK → cases.id)
- label (String)
- root_hyriv_id (Integer)
- reach_ids (Array/JSON)
- validation_status (String)
- meta (JSONB)

**Table: evidence_items**
- id (UUID, PK)
- case_id (UUID, FK → cases.id)
- evidence_type, source (String)
- value (JSONB)
- observed_at (DateTime, nullable)
- quality (String, nullable)
- provenance (JSONB)
- created_at (DateTime)

**Table: sampling_decisions**
- id (UUID, PK)
- case_id (UUID, FK → cases.id)
- status (String)
- recommended_site_ids (Array/JSON)
- rationale (Text)
- created_at (DateTime)

**Table: decision_traces**
- id (UUID, PK)
- decision_id (UUID, FK → sampling_decisions.id)
- evidence_used, rules_applied (Array/JSON)
- hydrology_checks (JSONB)
- assumptions, limitations (Array/JSON)
- created_at (DateTime)

**Adding New Tables:**
- SQLAlchemy ORM with Alembic migrations
- Easy to add: create model in `backend/app/db/models.py`, generate migration, run migration

---

## 9. Repositories (Create/Read/Update Methods)

### Evidence Repository

**From backend/app/repositories/evidence.py:**

```python
class EvidenceRepository:
    def __init__(self, db: Session):
        ...
    
    def add_evidence(
        self, case_id: UUID, evidence_type: str, source: str, value: Any,
        observed_at: Optional[datetime], quality: Optional[str],
        provenance: Optional[dict]
    ) -> EvidenceItem:
        """Add evidence and return domain model."""
    
    def get_evidence_by_case(self, case_id: UUID) -> list[EvidenceItem]:
        """Retrieve all evidence for a case."""
    
    def get_evidence_by_id(self, evidence_id: UUID) -> EvidenceItem:
        """Retrieve single evidence item."""
```

---

## 10. Protected Test Behaviors

### Evidence Property Tests

**From backend/tests/property/test_evidence_properties.py:**

**Property 11: Evidence assessment summary accuracy (Validates Requirements 6.5)**
- For any set of assessments, summary counts must equal actual distribution
- Summary total must equal assessment count
- No double-counting or loss

**Topology Rule States:**
- root=200, can_contribute=True → SUPPORTS
- root=200, can_contribute=False → CONTRADICTS
- root=201 (different zone) → NEUTRAL

**Unknown Handling:**
- Incomplete evidence (missing required fields) → UNKNOWN
- Unsupported evidence type → UNKNOWN
- No rule_id for UNKNOWN

**Conflicting Evidence:**
- Conflicting evidence not collapsed (1 SUPPORTS + 1 CONTRADICTS preserved)

**Rule Catalog:**
- All rules have required fields: id, version, name, description, condition, effect, reason, provenance/source, limitations, validation_status
- All rules have validation_status="VERIFIED"

**Direction and Strength Independence:**
- can_contribute=True → SUPPORTS + HIGH (with graph_coverage_validated=True)
- can_contribute=False → CONTRADICTS + HIGH (with graph_coverage_validated=True)
- Direction and strength are independent

**Unsupported Strength:**
- Unsupported evidence type → UNASSESSED
- strength_reason: "No validated strength rule exists for this evidence type."
- strength_rule_id: None

**Strength Determinism:**
- Same input produces same strength assessment
- Missing quality field is safe (doesn't crash)

**Strength Doesn't Affect Sampling:**
- Sampling scores identical before and after strength assessment
- pair_separation_score unchanged

### Wigger Regression Tests

**From backend/tests/unit/test_wigger_scientific_regression.py:**

**Site A Mapping:**
- HYRIV_ID: 20446064
- status: MATCHED
- original_coordinate != snapped_coordinate
- ValidationStatus.MATCHED = "MATCHED"

**Carraro H001 Observation:**
- target_taxon: "Fredericella sultana"
- observation_date: 2014-06-25
- station: S1, species_code: Fs, observation_index: 4
- concentration_mol_l: 1.29832198e-17
- state: DETECTED
- provenance: date_variable="Date.S1", concentration_variable="Fs.S1"

**Candidate Generation:**
- eligible_reach_count: 48
- decision_status: TIE
- All candidates have latitude, longitude (not None)
- All candidates have field_accessibility="NOT_EVALUATED"

**Topology:**
- upstream_reaches(Site A): 48
- first_common_downstream(Z2_root, Z3_root): 20449905
- All zone roots have downstream path to Site A

**Zone Exclusivity:**
- Z1, Z2, Z3 reach sets are disjoint

**Reachability Signatures:**
- Site A: [1, 1, 1]
- Site B: [0, 1, 0]
- Site C: [0, 0, 1]
- Site D: [0, 1, 1]

**Automatic Candidate Generation:**
- eligible_reach_count: 48
- Equivalence class scores: {(0,0,0): 0, (0,0,1): 2, (0,1,0): 2, (0,1,1): 2, (1,0,0): 2}
- Candidate order: [20451169, 20450127, 20446568, 20447392]
- Site A not in any equivalence class

---

## 11. Dependencies

### From backend/requirements.txt

**Relevant Libraries:**

```
# Core web framework
fastapi==0.115.0
uvicorn[standard]==0.31.0

# Data validation
pydantic==2.9.2

# Database
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
alembic==1.13.3

# Testing
pytest==8.3.3
hypothesis==6.112.1  # Property-based testing

# Data processing
pandas==2.2.3
geopandas==1.0.1     # GIS/geospatial
shapely==2.0.6       # Geometric operations
scipy==1.14.1        # Scientific computing

# Utilities
python-dotenv==1.0.1
```

**For HTTP clients, GIS, scientific work:**
- HTTP: Use `httpx` or `requests` (not currently installed, easy to add)
- GIS: geopandas, shapely already available
- Scientific: pandas, scipy already available

---

## 12. Configuration

### From backend/config.py

**Current Pattern:**

```python
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

def _configured_path(environment_name: str, default_relative: str) -> Path:
    """Resolve explicit paths or defaults from repository root."""
    configured = os.getenv(environment_name)
    if configured:
        return Path(configured).expanduser().resolve()
    return (REPOSITORY_ROOT / default_relative).resolve()

class Config:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://edna_user:edna_pass@localhost:5432/edna_investigator"
    )
    PREFLIGHT_DATA_DIR: Path = _configured_path(
        "PREFLIGHT_DATA_DIR", "data_preflight/outputs"
    )
    CARRARO_DATA_DIR: Path = _configured_path(
        "CARRARO_DATA_DIR", "data_preflight/raw/carraro"
    )
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

config = Config()
```

**To Add New API Keys/Data Sources:**
- Add environment variable with `os.getenv("NEW_API_KEY", "default")`
- Use `_configured_path()` for file/directory paths
- Follow existing pattern for type conversion (int, bool, Path)

---

## Summary

This document contains:
1. ✅ V2 final status, test counts, known limitations
2. ✅ Exact enums for evidence, validation, decisions
3. ✅ Exact domain model fields
4. ✅ Public methods/signatures for scientific engines
5. ✅ Rule IDs and versioning
6. ✅ Strength assessment model (HIGH/MEDIUM/LOW/UNASSESSED)
7. ✅ Request/response schemas for evidence, sampling
8. ✅ Public service methods
9. ✅ Existing API endpoints
10. ✅ Protected test behaviors
11. ✅ Database table fields
12. ✅ Repository CRUD methods
13. ✅ Current dependencies (GIS, HTTP, scientific)
14. ✅ Configuration pattern

**What Is NOT Included:**
- Private helper implementations
- Long test bodies
- SQLAlchemy boilerplate details
- Full hydrology algorithms
- Raw datasets
- Unrelated endpoints
