from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FollowUpSampleCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)
    sampling_site_id: UUID | None = None
    candidate_reference: str | None = None
    hyriv_id: int = Field(gt=0, strict=True)
    sampled_at: datetime
    replicate_count: int = Field(gt=0)
    positive_replicates: int = Field(ge=0)
    concentration: float | None = Field(default=None, ge=0)
    concentration_unit: str | None = None
    assay: str = Field(min_length=1)
    controls_status: str = Field(min_length=1)
    collector_source: str = Field(min_length=1)
    provenance: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_sample(self):
        if self.candidate_reference is not None and not self.candidate_reference:
            raise ValueError("candidate_reference cannot be blank")
        if (self.sampling_site_id is None) == (not self.candidate_reference):
            raise ValueError("provide exactly one of sampling_site_id or candidate_reference")
        if self.positive_replicates > self.replicate_count:
            raise ValueError("positive_replicates cannot exceed replicate_count")
        if self.concentration is not None and not self.concentration_unit:
            raise ValueError("concentration_unit is required when concentration is supplied")
        if not self.provenance:
            raise ValueError("sample provenance is required")
        return self


class FollowUpSampleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    sampling_site_id: UUID | None
    candidate_reference: str | None
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
    evidence_id: UUID | None
    created_at: datetime
    reanalysis_required: bool = True
