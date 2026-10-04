"""Append-only access to investigation runs and their snapshots."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import InvestigationRunModel
from app.domain.enums import InvestigationRunStatus, InvestigationTriggerType


class InvestigationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_running(
        self, case_id: UUID, trigger_type: InvestigationTriggerType,
        trigger_evidence_id: UUID | None, trigger_follow_up_sample_id: UUID | None,
        previous_decision_id: UUID | None,
    ) -> InvestigationRunModel:
        run = InvestigationRunModel(
            case_id=case_id, trigger_type=trigger_type.value,
            trigger_evidence_id=trigger_evidence_id,
            trigger_follow_up_sample_id=trigger_follow_up_sample_id,
            status=InvestigationRunStatus.RUNNING.value,
            previous_decision_id=previous_decision_id,
            evidence_count=0, hypothesis_snapshot={}, candidate_snapshot={},
            decision_snapshot={}, meta={"resolver": "UNKNOWN_PLACEHOLDER"},
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def mark_failed(self, run_id: UUID, reason: str) -> InvestigationRunModel:
        self.db.rollback()
        run = self.db.get(InvestigationRunModel, run_id)
        run.status = InvestigationRunStatus.FAILED.value
        run.failure_reason = reason
        run.completed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(run)
        return run

    def list_for_case(self, case_id: UUID) -> list[InvestigationRunModel]:
        return list(self.db.scalars(
            select(InvestigationRunModel)
            .where(InvestigationRunModel.case_id == case_id)
            .order_by(InvestigationRunModel.created_at.asc(), InvestigationRunModel.id.asc())
        ).all())

    def get_for_case(self, case_id: UUID, run_id: UUID) -> InvestigationRunModel | None:
        return self.db.scalar(
            select(InvestigationRunModel)
            .options(
                selectinload(InvestigationRunModel.hypothesis_states),
                selectinload(InvestigationRunModel.candidate_snapshots),
            )
            .where(InvestigationRunModel.case_id == case_id, InvestigationRunModel.id == run_id)
        )

    def latest_completed(self, case_id: UUID, exclude_run_id: UUID | None = None, before_started_at: datetime | None = None):
        query = select(InvestigationRunModel).where(
            InvestigationRunModel.case_id == case_id,
            InvestigationRunModel.status == InvestigationRunStatus.COMPLETED.value,
        )
        if exclude_run_id is not None:
            query = query.where(InvestigationRunModel.id != exclude_run_id)
        if before_started_at is not None:
            query = query.where(InvestigationRunModel.completed_at <= before_started_at)
        return self.db.scalar(query.order_by(InvestigationRunModel.completed_at.desc(), InvestigationRunModel.id.desc()).limit(1))
