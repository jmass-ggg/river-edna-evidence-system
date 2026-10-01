"""
Pydantic schemas for case management endpoints.

These schemas define request/response structures for case-related API operations.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from ..domain.enums import CaseStatus


class CaseCreateRequest(BaseModel):
    """
    Request schema for creating a new case.
    
    Attributes:
        target_taxon: Scientific name of the taxon detected
        observation_date: Date when the eDNA was detected
        detection_site_latitude: Latitude of detection site in decimal degrees
        detection_site_longitude: Longitude of detection site in decimal degrees
        detection_site_hyriv_id: HydroRIVERS reach ID for detection site
        metadata: Optional additional case-specific metadata
    """
    target_taxon: str = Field(..., min_length=1, description="Scientific name of the taxon detected")
    observation_date: date = Field(..., description="Date when the eDNA was detected")
    detection_site_latitude: float = Field(..., ge=-90, le=90, description="Detection site latitude")
    detection_site_longitude: float = Field(..., ge=-180, le=180, description="Detection site longitude")
    detection_site_hyriv_id: int = Field(..., gt=0, description="HydroRIVERS reach ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_taxon": "Salmo trutta",
                "observation_date": "2024-06-15",
                "detection_site_latitude": 47.2345,
                "detection_site_longitude": 7.8901,
                "detection_site_hyriv_id": 20449905,
                "metadata": {"collector": "Field Team A", "sample_id": "WT-001"}
            }
        }
    )


class CaseResponse(BaseModel):
    """
    Response schema for case data.
    
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
    metadata: dict[str, Any]

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "target_taxon": "Salmo trutta",
                "observation_date": "2024-06-15",
                "detection_site_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "status": "ACTIVE",
                "created_at": "2024-06-15T10:30:00Z",
                "updated_at": "2024-06-15T10:30:00Z",
                "metadata": {"collector": "Field Team A", "sample_id": "WT-001"}
            }
        }
    )


class CaseListResponse(BaseModel):
    """
    Response schema for listing multiple cases.
    
    Attributes:
        cases: List of case responses
        total: Total number of cases
    """
    cases: list[CaseResponse]
    total: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cases": [
                    {
                        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "target_taxon": "Salmo trutta",
                        "observation_date": "2024-06-15",
                        "detection_site_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                        "status": "ACTIVE",
                        "created_at": "2024-06-15T10:30:00Z",
                        "updated_at": "2024-06-15T10:30:00Z",
                        "metadata": {}
                    }
                ],
                "total": 1
            }
        }
    )
