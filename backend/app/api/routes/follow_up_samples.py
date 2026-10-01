from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_hydrology_engine
from app.db.session import get_db
from app.repositories.follow_up_samples import FollowUpSampleRepository
from app.schemas.follow_up_samples import FollowUpSampleCreateRequest, FollowUpSampleResponse
from app.services.follow_up_sample_service import FollowUpSampleService


router = APIRouter(prefix="/cases", tags=["follow-up samples"])


def get_follow_up_service(
    db: Session = Depends(get_db), hydrology_engine=Depends(get_hydrology_engine)
) -> FollowUpSampleService:
    return FollowUpSampleService(FollowUpSampleRepository(db), hydrology_engine)


@router.post(
    "/{case_id}/follow-up-samples",
    response_model=FollowUpSampleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_follow_up_sample(
    case_id: UUID,
    request: FollowUpSampleCreateRequest,
    service: FollowUpSampleService = Depends(get_follow_up_service),
) -> FollowUpSampleResponse:
    sample = service.create(case_id, **request.model_dump())
    return FollowUpSampleResponse.model_validate(sample)


@router.get("/{case_id}/follow-up-samples", response_model=list[FollowUpSampleResponse])
def list_follow_up_samples(
    case_id: UUID, service: FollowUpSampleService = Depends(get_follow_up_service)
) -> list[FollowUpSampleResponse]:
    return [FollowUpSampleResponse.model_validate(item) for item in service.list(case_id)]


@router.get("/{case_id}/follow-up-samples/{sample_id}", response_model=FollowUpSampleResponse)
def get_follow_up_sample(
    case_id: UUID,
    sample_id: UUID,
    service: FollowUpSampleService = Depends(get_follow_up_service),
) -> FollowUpSampleResponse:
    return FollowUpSampleResponse.model_validate(service.get(case_id, sample_id))
