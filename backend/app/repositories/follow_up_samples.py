from app.repositories.detection_contexts import scope_clause, belongs
"""Persistence operations for follow-up samples."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FollowUpSampleModel
from app.domain.models import FollowUpSample


class FollowUpSampleRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, model: FollowUpSampleModel) -> FollowUpSampleModel:
        self.db.add(model)
        self.db.flush()
        return model

    def list_for_case(self, case_id: UUID) -> list[FollowUpSample]:
        rows = self.db.scalars(
            select(FollowUpSampleModel)
            .where(FollowUpSampleModel.case_id == case_id, scope_clause(self.db, FollowUpSampleModel, case_id))
            .order_by(FollowUpSampleModel.created_at.asc())
        ).all()
        return [self._to_domain(row) for row in rows]

    def get_for_case(self, case_id: UUID, sample_id: UUID) -> FollowUpSample | None:
        row = self.db.scalar(
            select(FollowUpSampleModel).where(
                FollowUpSampleModel.id == sample_id,
                FollowUpSampleModel.case_id == case_id, scope_clause(self.db, FollowUpSampleModel, case_id),
            )
        )
        return self._to_domain(row) if row else None

    @staticmethod
    def _to_domain(row: FollowUpSampleModel) -> FollowUpSample:
        return FollowUpSample(
            id=row.id,
            case_id=row.case_id,
            sampling_site_id=row.sampling_site_id,
            candidate_reference=row.candidate_reference,
            hyriv_id=row.hyriv_id,
            sampled_at=row.sampled_at,
            replicate_count=row.replicate_count,
            positive_replicates=row.positive_replicates,
            concentration=row.concentration,
            concentration_unit=row.concentration_unit,
            assay=row.assay,
            controls_status=row.controls_status,
            collector_source=row.collector_source,
            provenance=row.provenance,
            notes=row.notes,
            evidence_id=row.evidence_id,
            created_at=row.created_at,
        )
