"""Validation and evidence linkage for newly returned field samples."""
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException

from app.db.models import CaseModel, EvidenceItemModel, FollowUpSampleModel, SamplingSiteModel
from app.repositories.follow_up_samples import FollowUpSampleRepository


class FollowUpSampleService:
    def __init__(self, repository: FollowUpSampleRepository, hydrology_engine):
        self.repository = repository
        self.db = repository.db
        self.hydrology_engine = hydrology_engine

    def create(self, case_id: UUID, **values):
        case = self.db.get(CaseModel, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        site_id = values.get("sampling_site_id")
        candidate_reference = values.get("candidate_reference")
        if (site_id is None) == (not candidate_reference):
            raise HTTPException(
                status_code=400,
                detail="Provide exactly one of sampling_site_id or candidate_reference",
            )
        replicate_count = values["replicate_count"]
        positive_replicates = values["positive_replicates"]
        if replicate_count <= 0 or not 0 <= positive_replicates <= replicate_count:
            raise HTTPException(status_code=400, detail="Invalid replicate counts")
        concentration = values.get("concentration")
        if concentration is not None:
            if concentration < 0:
                raise HTTPException(status_code=400, detail="Concentration cannot be negative")
            if not values.get("concentration_unit"):
                raise HTTPException(
                    status_code=400,
                    detail="concentration_unit is required when concentration is supplied",
                )
        if site_id is not None:
            site = self.db.get(SamplingSiteModel, site_id)
            if site is None or (
                site.case_id != case_id and case.detection_site_id != site_id
            ):
                raise HTTPException(status_code=400, detail="Sampling site does not belong to case")
            if site.hyriv_id != values["hyriv_id"]:
                raise HTTPException(status_code=400, detail="HYRIV_ID does not match sampling site")
        try:
            self.hydrology_engine.get_reach(values["hyriv_id"])
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

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
            raise HTTPException(status_code=404, detail="Case not found")
        return self.repository.list_for_case(case_id)

    def get(self, case_id: UUID, sample_id: UUID):
        sample = self.repository.get_for_case(case_id, sample_id)
        if sample is None:
            raise HTTPException(status_code=404, detail="Follow-up sample not found")
        return sample
