"""AI explanations are separate, context-scoped drafts with explicit review."""
from uuid import UUID
from fastapi import APIRouter, Depends
from app.api.detection_scope import bind_detection_context
from app.db.session import get_db
from app.schemas.ai_reports import AIReportAction, AIReportResponse, AIReportLatest
from app.services.ai_report_service import AIReportService

router = APIRouter(prefix='/cases', tags=['AI reports'], dependencies=[Depends(bind_detection_context)])


def get_ai_report_service(db=Depends(get_db)):
    return AIReportService(db)


@router.post('/{case_id}/ai-report', response_model=AIReportResponse, status_code=201)
def generate_ai_report(case_id: UUID, request: AIReportAction, service=Depends(get_ai_report_service)):
    return service.generate(case_id)


@router.get('/{case_id}/ai-report', response_model=AIReportLatest)
def latest_ai_report(case_id: UUID, service=Depends(get_ai_report_service)):
    return service.latest(case_id)


@router.post('/{case_id}/ai-report/{report_id}/approve', response_model=AIReportResponse)
def approve_ai_report(case_id: UUID, report_id: UUID, request: AIReportAction, service=Depends(get_ai_report_service)):
    return service.approve(case_id, report_id)
