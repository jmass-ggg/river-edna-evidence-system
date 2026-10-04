"""
Pydantic schemas for evidence management endpoints.

These schemas define request/response structures for evidence-related API operations.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, model_validator

from ..domain.enums import EvidenceCompatibility, EvidenceStrength


class EvidenceCreateRequest(BaseModel):
    """
    Request schema for adding evidence to a case.
    
    Attributes:
        evidence_type: Type/category of evidence
        source: Origin of the evidence
        value: The evidence value (flexible type)
        observed_at: When the evidence was observed (optional)
        quality: Quality indicator (optional)
        provenance: Provenance tracking metadata
    """
    evidence_type: str = Field(..., min_length=1, description="Type/category of evidence")
    source: str = Field(..., min_length=1, description="Origin of the evidence")
    value: Any = Field(..., description="The evidence value")
    observed_at: datetime | None = Field(None, description="When the evidence was observed")
    quality: str | None = Field(None, description="Quality indicator")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Provenance tracking metadata")

    @model_validator(mode="after")
    def validate_recorded_replicates(self):
        if self.evidence_type == "edna_observation" and isinstance(self.value, dict) and "replicate_results" in self.value:
            results = self.value["replicate_results"]
            if not isinstance(results, list) or not results or any(result not in ("Positive", "Negative", "Invalid") for result in results):
                raise ValueError("Provide recorded Positive, Negative or Invalid replicate results")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "evidence_type": "water_temperature",
                "source": "sensor_station_A",
                "value": 18.5,
                "observed_at": "2024-06-15T14:30:00Z",
                "quality": "high",
                "provenance": {"sensor_id": "TS-001", "calibration_date": "2024-06-01"}
            }
        }
    )


class EvidenceResponse(BaseModel):
    """
    Response schema for evidence data.
    
    Attributes:
        id: Unique identifier for the evidence item
        case_id: UUID of the associated case
        evidence_type: Type/category of evidence
        source: Origin of the evidence
        value: The evidence value
        observed_at: When the evidence was observed
        quality: Quality indicator
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

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "c3d4e5f6-a7b8-9012-cdef-123456789abc",
                "case_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "evidence_type": "water_temperature",
                "source": "sensor_station_A",
                "value": 18.5,
                "observed_at": "2024-06-15T14:30:00Z",
                "quality": "high",
                "provenance": {"sensor_id": "TS-001"},
                "created_at": "2024-06-15T15:00:00Z"
            }
        }
    )


class EvidenceAssessmentResponse(BaseModel):
    """
    Response schema for evidence compatibility assessment.
    
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
    provenance: dict[str, Any]
    strength: EvidenceStrength = EvidenceStrength.UNASSESSED
    strength_criteria: list[dict[str, Any]] = Field(default_factory=list)
    strength_reason: str = (
        "No validated strength rule exists for this evidence type."
    )
    strength_rule_id: str | None = None
    strength_rule_version: str | None = None
    strength_provenance: dict[str, Any] = Field(default_factory=dict)
    strength_limitations: list[str] = Field(default_factory=list)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "evidence_id": "c3d4e5f6-a7b8-9012-cdef-123456789abc",
                "compatibility": "UNKNOWN",
                "rule_id": None,
                "reason": "No validated scientific rule applies to this evidence type",
                "provenance": {"engine_status": "incomplete_ruleset"}
            }
        }
    )


class AssessmentSummaryResponse(BaseModel):
    """
    Response schema for summarizing evidence assessments.
    
    Attributes:
        zone_id: UUID of the candidate zone being assessed
        zone_label: Human-readable label for the zone
        assessments: List of individual evidence assessments
        summary: Count of assessments by compatibility status
    """
    zone_id: UUID
    zone_label: str
    assessments: list[EvidenceAssessmentResponse]
    summary: dict[str, int] = Field(
        ...,
        description="Counts by status: supports, contradicts, neutral, unknown"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": "d4e5f6a7-b8c9-0123-def0-123456789bcd",
                "zone_label": "Z1",
                "assessments": [
                    {
                        "evidence_id": "c3d4e5f6-a7b8-9012-cdef-123456789abc",
                        "compatibility": "UNKNOWN",
                        "rule_id": None,
                        "reason": "No validated scientific rule applies",
                        "provenance": {}
                    }
                ],
                "summary": {
                    "supports": 0,
                    "contradicts": 0,
                    "neutral": 0,
                    "unknown": 1
                }
            }
        }
    )
