from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.one_health import OneHealthAssessmentSchema
from app.services.one_health_service import OneHealthService


router = APIRouter(prefix="/cases", tags=["one health"])


@router.get("/{case_id}/one-health", response_model=OneHealthAssessmentSchema)
def get_one_health_structure(
    case_id: UUID, db: Session = Depends(get_db)
) -> OneHealthAssessmentSchema:
    result = OneHealthService(db).assess(case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return OneHealthAssessmentSchema.model_validate(result)
