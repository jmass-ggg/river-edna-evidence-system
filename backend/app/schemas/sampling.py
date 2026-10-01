"""
Pydantic schemas for sampling management endpoints.

These schemas define request/response structures for sampling-related API operations.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from ..domain.enums import (
    SamplingDecisionStatus,
    SiteType,
    ValidationStatus,
)


class SamplingSiteCreateRequest(BaseModel):
    """
    Request schema for registering a sampling site.
    
    Attributes:
        label: Human-readable label (e.g., "Site A", "Site B")
        latitude: Site latitude in decimal degrees
        longitude: Site longitude in decimal degrees
        hyriv_id: HydroRIVERS reach ID
        site_type: Type of sampling site
        validation_status: Validation status of network match
        network_latitude: Snapped network latitude (optional)
        network_longitude: Snapped network longitude (optional)
        snap_distance_m: Distance from observation to network in meters (optional)
        role: Functional role in sampling strategy (optional)
        metadata: Additional site-specific metadata
    """
    label: str = Field(..., min_length=1, description="Human-readable site label")
    latitude: float = Field(..., ge=-90, le=90, description="Site latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Site longitude")
    hyriv_id: int = Field(..., gt=0, description="HydroRIVERS reach ID")
    site_type: SiteType = Field(..., description="Type of sampling site")
    validation_status: ValidationStatus = Field(..., description="Validation status")
    network_latitude: float | None = Field(None, ge=-90, le=90, description="Network latitude")
    network_longitude: float | None = Field(None, ge=-180, le=180, description="Network longitude")
    snap_distance_m: float | None = Field(None, ge=0, description="Snap distance in meters")
    role: str | None = Field(None, description="Functional role")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "label": "Site B",
                "latitude": 47.2456,
                "longitude": 7.8912,
                "hyriv_id": 20450127,
                "site_type": "BRANCH_SPECIFIC",
                "validation_status": "VERIFIED",
                "network_latitude": 47.2457,
                "network_longitude": 7.8913,
                "snap_distance_m": 15.2,
                "role": "Z1_discriminator",
                "metadata": {}
            }
        }
    )


class SamplingSiteResponse(BaseModel):
    """
    Response schema for sampling site data.
    
    Attributes:
        id: Unique identifier for the site
        case_id: UUID of the associated case (nullable for shared sites)
        label: Human-readable label
        latitude: Site latitude
        longitude: Site longitude
        hyriv_id: HydroRIVERS reach ID
        site_type: Type of sampling site
        validation_status: Validation status
        network_latitude: Snapped network latitude
        network_longitude: Snapped network longitude
        snap_distance_m: Snap distance in meters
        role: Functional role
        metadata: Additional metadata
    """
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

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "case_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "label": "Site B",
                "latitude": 47.2456,
                "longitude": 7.8912,
                "hyriv_id": 20450127,
                "site_type": "BRANCH_SPECIFIC",
                "validation_status": "VERIFIED",
                "network_latitude": 47.2457,
                "network_longitude": 7.8913,
                "snap_distance_m": 15.2,
                "role": "Z1_discriminator",
                "metadata": {}
            }
        }
    )


class CandidateZoneCreateRequest(BaseModel):
    """
    Request schema for creating a candidate zone.
    
    Attributes:
        label: Human-readable label (e.g., "Z1", "Z2")
        root_hyriv_id: HYRIV_ID of the zone root reach
        reach_ids: List of HYRIV_IDs comprising the zone
        validation_status: Validation status of zone definition
        metadata: Additional zone-specific metadata
    """
    label: str = Field(..., min_length=1, description="Human-readable zone label")
    root_hyriv_id: int = Field(..., gt=0, description="Zone root reach ID")
    reach_ids: list[int] = Field(..., min_length=1, description="List of reach IDs in zone")
    validation_status: ValidationStatus = Field(..., description="Validation status")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "label": "Z1",
                "root_hyriv_id": 20450127,
                "reach_ids": [20450127, 20450128, 20450129],
                "validation_status": "VERIFIED",
                "metadata": {"area_sqkm": 125.3}
            }
        }
    )


class CandidateZoneResponse(BaseModel):
    """
    Response schema for candidate zone data.
    
    Attributes:
        id: Unique identifier for the zone
        case_id: UUID of the associated case
        label: Human-readable label
        root_hyriv_id: Zone root reach ID
        reach_ids: List of reach IDs in zone
        validation_status: Validation status
        metadata: Additional metadata
    """
    id: UUID
    case_id: UUID
    label: str
    root_hyriv_id: int
    reach_ids: list[int]
    validation_status: ValidationStatus
    metadata: dict[str, Any]

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "d4e5f6a7-b8c9-0123-def0-123456789bcd",
                "case_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "label": "Z1",
                "root_hyriv_id": 20450127,
                "reach_ids": [20450127, 20450128, 20450129],
                "validation_status": "VERIFIED",
                "metadata": {"area_sqkm": 125.3}
            }
        }
    )


class SamplingDecisionResponse(BaseModel):
    """
    Response schema for sampling decision results.
    
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

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "e5f6a7b8-c9d0-1234-ef01-23456789cdef",
                "case_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "status": "INSUFFICIENT_DATA",
                "recommended_site_ids": [],
                "rationale": "Final scientific scoring criteria are not yet defined",
                "created_at": "2024-06-15T16:00:00Z"
            }
        }
    )


class DecisionTraceResponse(BaseModel):
    """
    Response schema for decision audit trail.
    
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

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "decision_id": "e5f6a7b8-c9d0-1234-ef01-23456789cdef",
                "evidence_used": ["c3d4e5f6-a7b8-9012-cdef-123456789abc"],
                "rules_applied": [],
                "hydrology_checks": [
                    {"operation": "network_distance", "from": 20450127, "to": 20449905, "result_km": 8.3}
                ],
                "assumptions": ["Zone definitions represent realistic source regions"],
                "limitations": ["Scientific scoring criteria not yet validated"],
                "created_at": "2024-06-15T16:00:00Z"
            }
        }
    )
