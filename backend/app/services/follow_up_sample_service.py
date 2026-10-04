from app.repositories.detection_contexts import belongs, selected_context
"""Validation and evidence linkage for newly returned field samples."""
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException

from app.db.models import CaseModel, EvidenceItemModel, FollowUpSampleModel, SamplingSiteModel
from app.repositories.follow_up_samples import FollowUpSampleRepository
from app.repositories.sampling import SamplingRepository
from app.schemas.follow_up_samples import FollowUpSampleCreateRequest
from pydantic import ValidationError


class FollowUpSampleService:
    def __init__(self, repository: FollowUpSampleRepository, hydrology_engine):
        self.repository = repository
        self.db = repository.db
        self.hydrology_engine = hydrology_engine

    def create(self, case_id: UUID, **values):
        case = self.db.get(CaseModel, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail={"type": "NotFoundError", "message": "Case not found"})
        try:
            values = FollowUpSampleCreateRequest(**values).model_dump()
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail={"type": "ValidationError", "message": str(exc)}) from exc
        site_id = values.get("sampling_site_id")
        candidate_reference = values.get("candidate_reference")
        try:
            self.hydrology_engine.get_reach(values["hyriv_id"])
        except ValueError as exc:
            raise HTTPException(status_code=404, detail={"type": "InvalidHyrivIdError", "message": str(exc)}) from exc
        if candidate_reference:
            if candidate_reference.startswith("HYRIV_ID:"):
                try:
                    candidate_reach = int(candidate_reference.removeprefix("HYRIV_ID:"))
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail={"type": "ValidationError", "message": "Invalid candidate reference"}) from exc
                context = selected_context(self.db, case_id)
                scope = context.id if context and not context.is_primary else case_id
                candidate_id = SamplingRepository.generated_site_id(scope, candidate_reach)
            else:
                try:
                    candidate_id = UUID(candidate_reference)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail={"type": "ValidationError", "message": "Use a persisted candidate UUID or HYRIV_ID:<reach>"}) from exc
            candidate = self.db.get(SamplingSiteModel, candidate_id)
            if not belongs(self.db, candidate, case_id) or candidate.role != "GENERATED_REPRESENTATIVE":
                raise HTTPException(status_code=404, detail={"type": "NotFoundError", "message": "Generated candidate does not belong to this investigation or has not been persisted"})
            if candidate.hyriv_id != values["hyriv_id"]:
                raise HTTPException(status_code=409, detail={"type": "ConflictError", "message": "HYRIV_ID does not match generated candidate"})
            values["candidate_reference"] = str(candidate.id)
        if site_id is not None:
            site = self.db.get(SamplingSiteModel, site_id)
            if not belongs(self.db, site, case_id, physical_site=True):
                raise HTTPException(status_code=404, detail={"type": "NotFoundError", "message": "Sampling site does not belong to case"})
            if site.hyriv_id != values["hyriv_id"]:
                raise HTTPException(status_code=409, detail={"type": "ConflictError", "message": "HYRIV_ID does not match sampling site"})

        try:
            row = self.repository.add(FollowUpSampleModel(case_id=case_id, **values))
            evidence_value = {
                "sample_id": str(row.id),
                "hyriv_id": row.hyriv_id,
                "replicate_count": row.replicate_count,
                "positive_replicates": row.positive_replicates,
                "concentration": row.concentration,
                "unit": row.concentration_unit,
                "assay": row.assay,
                "controls_status": row.controls_status,
                "sampled_at": row.sampled_at.isoformat(),
                "provenance": row.provenance,
                "sampling_site_id": str(row.sampling_site_id) if row.sampling_site_id else None,
                "candidate_reference": row.candidate_reference,
            }
            evidence = EvidenceItemModel(
                case_id=case_id,
                evidence_type="follow_up_edna_sample",
                source=row.collector_source,
                value=evidence_value,
                observed_at=row.sampled_at,
                provenance=row.provenance,
            )
            self.db.add(evidence)
            self.db.flush()
            row.evidence_id = evidence.id
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return self.repository._to_domain(row)

    def list(self, case_id: UUID):
        if self.db.get(CaseModel, case_id) is None:
            raise HTTPException(status_code=404, detail={"type": "NotFoundError", "message": "Case not found"})
        return self.repository.list_for_case(case_id)

    def get(self, case_id: UUID, sample_id: UUID):
        sample = self.repository.get_for_case(case_id, sample_id)
        if sample is None:
            raise HTTPException(status_code=404, detail={"type": "NotFoundError", "message": "Follow-up sample not found"})
        return sample
