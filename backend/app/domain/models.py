"""
Domain models for the eDNA Evidence Investigator system.

These are clean domain objects independent of database and HTTP concerns.
They represent the core business entities and concepts.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID

from .enums import (
    CaseStatus,
    EvidenceCompatibility,
    SamplingDecisionStatus,
    SiteType,
    ValidationStatus,
)


@dataclass
class Case:
    """
    An investigation of an eDNA detection at a specific site for a specific taxon.
    
    Attributes:
        id: Unique identifier for the case
        target_taxon: Scientific name of the taxon detected
        observation_date: Date when the eDNA was detected
        detection_site_id: UUID of the detection site
        status: Current case status
        created_at: Timestamp when case was created
        updated_at: Timestamp when case was last updated
        metadata: Additional case-specific metadata
    """
    id: UUID
    target_taxon: str
    observation_date: date
    detection_site_id: UUID
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SamplingSite:
    """
    A location proposed for sampling or where detection occurred.
    
    Attributes:
        id: Unique identifier for the site
        case_id: UUID of the associated case (nullable for shared sites)
        label: Human-readable label (e.g., "Site A", "Site B")
        latitude: Observation latitude in decimal degrees
        longitude: Observation longitude in decimal degrees
        hyriv_id: HydroRIVERS reach ID
        site_type: Type of sampling site
        validation_status: Validation status of network match
        network_latitude: Snapped network latitude (nullable)
        network_longitude: Snapped network longitude (nullable)
        snap_distance_m: Distance from observation to network in meters (nullable)
        role: Functional role in sampling strategy (nullable)
        metadata: Additional site-specific metadata
    """
    id: UUID
    case_id: UUID | None
    label: str
    latitude: float
    longitude: float
    hyriv_id: int
    site_type: SiteType
    validation_status: ValidationStatus
    network_latitude: float | None = None
    network_longitude: float | None = None
    snap_distance_m: float | None = None
    role: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiverReach:
    """
    A segment in the HydroRIVERS network.
    
    Attributes:
        hyriv_id: Unique HydroRIVERS reach identifier
        next_down: HYRIV_ID of the downstream reach (None if terminal)
        length_km: Reach length in kilometers
        upland_skm: Upstream contributing area in square kilometers
        dis_av_cms: Average discharge in cubic meters per second
        geometry: Shapely geometry if needed (nullable)
    """
    hyriv_id: int
    next_down: int | None
    length_km: float
    upland_skm: float
    dis_av_cms: float
    geometry: Any | None = None


@dataclass
class CandidateZone:
    """
    A hypothetical source region in the river network.
    
    Attributes:
        id: Unique identifier for the zone
        case_id: UUID of the associated case
        label: Human-readable label (e.g., "Z1", "Z2", "Z3")
        root_hyriv_id: HYRIV_ID of the zone root reach
        reach_ids: List of HYRIV_IDs comprising the zone
        validation_status: Validation status of zone definition
        metadata: Additional zone-specific metadata
    """
    id: UUID
    case_id: UUID
    label: str
    root_hyriv_id: int
    reach_ids: list[int]
    validation_status: ValidationStatus
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceItem:
    """
    A piece of data that supports, contradicts, or is neutral regarding a hypothesis.
    
    Attributes:
        id: Unique identifier for the evidence item
        case_id: UUID of the associated case
        evidence_type: Type/category of evidence
        source: Origin of the evidence
        value: The evidence value (flexible type)
        observed_at: When the evidence was observed (nullable)
        quality: Quality indicator (nullable)
        provenance: Provenance tracking metadata
        created_at: Timestamp when evidence was recorded
    """
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
    """
    Assessment of how an evidence item relates to a hypothesis.
    
    Attributes:
        evidence_id: UUID of the evidence item being assessed
        compatibility: Compatibility status with hypothesis
        rule_id: ID of the scientific rule applied (None if no rule applies)
        reason: Explanation of the assessment
        provenance: Provenance tracking metadata
    """
    evidence_id: UUID
    compatibility: EvidenceCompatibility
    rule_id: str | None
    reason: str
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class SamplingDecision:
    """
    A decision about which sampling sites to prioritize.
    
    Attributes:
        id: Unique identifier for the decision
        case_id: UUID of the associated case
        status: Decision status
        recommended_site_ids: List of recommended site UUIDs
        rationale: Explanation for the decision
        created_at: Timestamp when decision was made
    """
    id: UUID
    case_id: UUID
    status: SamplingDecisionStatus
    recommended_site_ids: list[UUID]
    rationale: str
    created_at: datetime


@dataclass
class DecisionTrace:
    """
    Audit trail showing how a decision was made.
    
    Attributes:
        decision_id: UUID of the decision being traced
        evidence_used: List of evidence item UUIDs used
        rules_applied: List of scientific rule IDs applied
        hydrology_checks: List of hydrology operations performed
        assumptions: List of assumptions made
        limitations: List of known limitations
        created_at: Timestamp when trace was created
    """
    decision_id: UUID
    evidence_used: list[UUID]
    rules_applied: list[str]
    hydrology_checks: list[dict[str, Any]]
    assumptions: list[str]
    limitations: list[str]
    created_at: datetime
