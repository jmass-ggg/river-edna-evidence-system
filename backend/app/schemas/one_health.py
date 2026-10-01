from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import OneHealthClaimStatus


class OneHealthClaimSchema(BaseModel):
    status: OneHealthClaimStatus
    statement: str
    evidence_references: list[str] = Field(default_factory=list)


class OneHealthPathwaySchema(BaseModel):
    pathway_id: str
    triggering_evidence: list[str] = Field(default_factory=list)
    monitoring_finding: OneHealthClaimSchema
    ecological_relevance: OneHealthClaimSchema
    animal_health_relevance: OneHealthClaimSchema
    community_management_relevance: OneHealthClaimSchema
    possible_monitoring_action: OneHealthClaimSchema
    parasite_presence: OneHealthClaimSchema
    fish_disease_status: OneHealthClaimSchema
    human_health_impact: OneHealthClaimSchema
    contextual_evidence: list[OneHealthClaimSchema] = Field(default_factory=list)
    scientific_sources: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class OneHealthAssessmentSchema(BaseModel):
    case_id: UUID
    pathways: list[OneHealthPathwaySchema] = Field(default_factory=list)
    framework: list[str] = Field(default_factory=list)
    scientific_logic_implemented: bool = True
