"""Assign context identity to writes; reject cross-context relationships."""
from sqlalchemy import event
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.db import models as m

SCOPED = (m.EvidenceItemModel,m.CandidateZoneModel,m.SamplingDecisionModel,
          m.InvestigationRunModel,m.FollowUpSampleModel,m.HypothesisStateModel,
          m.GeneratedCandidateSnapshotModel,m.ContextExecutionModel)

@event.listens_for(Session, "before_flush")
def assign_detection_context(session, flush_context, instances):
    from app.repositories.detection_contexts import context_id
    for row in list(session.new):
        if isinstance(row, SCOPED) or (isinstance(row,m.SamplingSiteModel) and row.case_id is not None and row.site_type != "DETECTION_SITE"):
            if row.detection_context_id is None:
                row.detection_context_id = context_id(session,row.case_id)
            elif row.detection_context_id != context_id(session,row.case_id):
                raise HTTPException(409,detail={"type":"ConflictError","message":"Write belongs to another detection context"})
