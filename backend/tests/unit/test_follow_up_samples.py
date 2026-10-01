from datetime import date, datetime

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select

from app.db.models import (
    CaseModel, EvidenceItemModel, SamplingDecisionModel, SamplingSiteModel,
)
from app.domain.enums import CaseStatus, SiteType, ValidationStatus
from app.repositories.follow_up_samples import FollowUpSampleRepository
from app.schemas.follow_up_samples import FollowUpSampleCreateRequest
from app.services.follow_up_sample_service import FollowUpSampleService


class FakeHydrology:
    def get_reach(self, hyriv_id):
        if hyriv_id != 20446064:
            raise ValueError(f"HYRIV_ID {hyriv_id} not found in loaded network")
        return object()


@pytest.fixture
def case_and_site(db_session):
    detection = SamplingSiteModel(
        label="A", latitude=47.0, longitude=8.0, hyriv_id=20446064,
        site_type=SiteType.DETECTION_SITE.value,
        validation_status=ValidationStatus.VERIFIED.value, meta={},
    )
    db_session.add(detection)
    db_session.flush()
    case = CaseModel(
        target_taxon="Test taxon", observation_date=date(2024, 1, 1),
        detection_site_id=detection.id, status=CaseStatus.ACTIVE.value, meta={},
    )
    db_session.add(case)
    db_session.flush()
    follow_up = SamplingSiteModel(
        case_id=case.id, label="B", latitude=47.1, longitude=8.1,
        hyriv_id=20446064, site_type=SiteType.FOLLOW_UP.value,
        validation_status=ValidationStatus.VERIFIED.value, meta={},
    )
    db_session.add(follow_up)
    db_session.commit()
    return case, follow_up


def _payload(site_id):
    return dict(
        sampling_site_id=site_id, candidate_reference=None, hyriv_id=20446064,
        sampled_at=datetime(2024, 2, 1, 10), replicate_count=3,
        positive_replicates=1, concentration=1e-12,
        concentration_unit="mol/L", assay="qPCR", controls_status="PASS",
        collector_source="field team", provenance={"form": "F-1"}, notes="sample",
    )


def test_follow_up_persists_links_evidence_without_decision(db_session, case_and_site):
    case, site = case_and_site
    service = FollowUpSampleService(FollowUpSampleRepository(db_session), FakeHydrology())
    decisions_before = db_session.scalar(select(func.count()).select_from(SamplingDecisionModel))

    sample = service.create(case.id, **_payload(site.id))

    evidence = db_session.get(EvidenceItemModel, sample.evidence_id)
    assert service.get(case.id, sample.id).id == sample.id
    assert len(service.list(case.id)) == 1
    assert evidence.evidence_type == "follow_up_edna_sample"
    assert evidence.value["sample_id"] == str(sample.id)
    assert evidence.value["positive_replicates"] == 1
    assert db_session.scalar(select(func.count()).select_from(SamplingDecisionModel)) == decisions_before


@pytest.mark.parametrize("changes", [
    {"replicate_count": 0},
    {"positive_replicates": 4},
    {"concentration": -1},
    {"concentration_unit": None},
])
def test_follow_up_schema_rejects_invalid_measurements(changes):
    payload = _payload(None)
    payload["candidate_reference"] = "candidate-B"
    payload.update(changes)
    with pytest.raises(ValidationError):
        FollowUpSampleCreateRequest(**payload)


def test_wrong_case_site_and_invalid_hyriv_rejected(db_session, case_and_site):
    case, site = case_and_site
    other_detection = SamplingSiteModel(
        label="other A", latitude=0, longitude=0, hyriv_id=20446064,
        site_type=SiteType.DETECTION_SITE.value,
        validation_status=ValidationStatus.VERIFIED.value, meta={},
    )
    db_session.add(other_detection)
    db_session.flush()
    other_case = CaseModel(
        target_taxon="Other", observation_date=date(2024, 1, 1),
        detection_site_id=other_detection.id, status=CaseStatus.ACTIVE.value, meta={},
    )
    db_session.add(other_case)
    db_session.commit()
    service = FollowUpSampleService(FollowUpSampleRepository(db_session), FakeHydrology())

    with pytest.raises(HTTPException, match="does not belong"):
        service.create(other_case.id, **_payload(site.id))
    invalid = _payload(site.id)
    invalid["sampling_site_id"] = None
    invalid["candidate_reference"] = "generated-candidate"
    invalid["hyriv_id"] = 999
    with pytest.raises(HTTPException) as exc:
        service.create(case.id, **invalid)
    assert exc.value.status_code == 404
