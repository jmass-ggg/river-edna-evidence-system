from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import InvestigationRunStatus, InvestigationTriggerType


class ReinvestigateRequest(BaseModel):
    trigger_evidence_id: UUID | None = None
    trigger_follow_up_sample_id: UUID | None = None


class InvestigationRunSummary(BaseModel):
    investigation_run_id: UUID
    case_id: UUID
    status: InvestigationRunStatus
    trigger_type: InvestigationTriggerType
    trigger_evidence_id: UUID | None
    trigger_follow_up_sample_id: UUID | None
    previous_decision_id: UUID | None
    new_decision_id: UUID | None
    evidence_count: int
    started_at: datetime
    completed_at: datetime | None
    failure_reason: str | None
    metadata: dict[str, Any]


class InvestigationRunResponse(InvestigationRunSummary):
    hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    candidate_generation: dict[str, Any] = Field(default_factory=dict)
    sampling_decision: dict[str, Any] = Field(default_factory=dict)
    decision_trace: dict[str, Any] | None = None
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    changed: dict[str, bool]
    change_reason: str
