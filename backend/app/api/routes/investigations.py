from app.api.detection_scope import bind_detection_context
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.routes.sampling import get_sampling_service
from app.db.session import get_db
from app.schemas.investigations import (
    InvestigationRunResponse, InvestigationRunSummary, ReinvestigateRequest,
)
from app.scientific.evidence.engine import EvidenceCompatibilityEngineImpl
from app.scientific.hypothesis import ConservativeHypothesisStateResolver
from app.services.investigation_service import InvestigationService
from app.services.sampling_service import SamplingService


router = APIRouter(prefix="/cases", tags=["investigations"], dependencies=[Depends(bind_detection_context)])


def get_investigation_service(
    db: Session = Depends(get_db),
    sampling_service: SamplingService = Depends(get_sampling_service),
) -> InvestigationService:
    return InvestigationService(
        db=db,
        evidence_engine=EvidenceCompatibilityEngineImpl(),
        hypothesis_resolver=ConservativeHypothesisStateResolver(),
        candidate_generator=sampling_service.candidate_generator,
        sampling_engine=sampling_service.sampling_engine,
        site_a_fraction=sampling_service.site_a_fraction,
    )


@router.post(
    "/{case_id}/reinvestigate",
    response_model=InvestigationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def reinvestigate(
    case_id: UUID, request: ReinvestigateRequest,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationRunResponse:
    return InvestigationRunResponse.model_validate(service.reinvestigate(
        case_id, request.trigger_evidence_id, request.trigger_follow_up_sample_id
    ))


@router.get("/{case_id}/investigation-runs", response_model=list[InvestigationRunSummary])
def list_investigation_runs(
    case_id: UUID, service: InvestigationService = Depends(get_investigation_service),
) -> list[InvestigationRunSummary]:
    return [InvestigationRunSummary.model_validate(item) for item in service.list(case_id)]


@router.get("/{case_id}/investigation-runs/{run_id}", response_model=InvestigationRunResponse)
def get_investigation_run(
    case_id: UUID, run_id: UUID,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationRunResponse:
    return InvestigationRunResponse.model_validate(service.detail(case_id, run_id))
