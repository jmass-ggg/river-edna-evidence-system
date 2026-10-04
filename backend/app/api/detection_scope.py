"""Bind optional context selection to one request's database session."""
from uuid import UUID
from fastapi import Depends, Request
from app.db.session import get_db
from app.repositories.detection_contexts import selected_context, detection_scope

async def bind_detection_context(request: Request, detection_context_id: UUID | None = None, db=Depends(get_db)):
    case_id = request.path_params.get("case_id")
    if detection_context_id is None or case_id is None:
        yield
        return
    with detection_scope(db, detection_context_id):
        selected_context(db, UUID(str(case_id)))
        yield
