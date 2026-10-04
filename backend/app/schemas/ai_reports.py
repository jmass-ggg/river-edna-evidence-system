"""Strict provider output and public, credential-free report contracts."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SECTION_NAMES = ("scientific_summary", "uncertainty_explanation", "sampling_decision_explanation", "one_health_summary")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class NarrativeStatement(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    source_references: list[str] = Field(min_length=1, max_length=20)


class NarrativeSection(StrictModel):
    statements: list[NarrativeStatement] = Field(min_length=1, max_length=100)


class AINarrative(StrictModel):
    species: str = Field(min_length=1, max_length=200)
    observation_date: str = Field(min_length=10, max_length=10)
    decision_status: Literal["TIE", "RECOMMEND", "ABSTAIN", "INSUFFICIENT_DATA"]
    scientific_summary: NarrativeSection
    uncertainty_explanation: NarrativeSection
    sampling_decision_explanation: NarrativeSection
    one_health_summary: NarrativeSection


class AIReportAction(StrictModel):
    """No scientific data, ownership or classifications accepted from clients."""


class AIReportResponse(StrictModel):
    id: UUID
    case_id: UUID
    detection_context_id: UUID
    decision_id: UUID
    investigation_run_id: UUID | None
    input_fingerprint: str
    prompt_version: str
    model_identifier: str
    generated_at: datetime
    reviewed_at: datetime | None
    validation_status: Literal["VALIDATED"]
    review_status: Literal["DRAFT", "APPROVED"]
    current: bool
    stale: bool
    exportable: bool
    narrative: AINarrative
    sources: dict[str, dict]


class AIReportLatest(StrictModel):
    enabled: bool
    available: bool
    report: AIReportResponse | None
