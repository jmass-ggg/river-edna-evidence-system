from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import ContextProviderStatus, EvidenceCompatibility, EvidenceStrength


class ContextCollectRequest(BaseModel):
    query: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_m: int = Field(default=5000, gt=0)
    weather_window_days: int = Field(default=0, ge=0)
    urban_buffer_m: int | None = Field(default=None, gt=0)


class ContextProviderResponse(BaseModel):
    evidence_id: UUID | None
    provider: str
    evidence_type: str
    status: ContextProviderStatus
    data: dict[str, Any] | None
    provenance: dict[str, Any]
    limitations: list[str]
    error: str | None
    compatibility: EvidenceCompatibility
    strength: EvidenceStrength
