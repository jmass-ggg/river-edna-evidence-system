"""Regression coverage for frozen-location validation and complete investigations."""
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.routes.cases import create_case
from app.api.routes.demo import reuse_wigger_reference
from app.api.routes.sampling import (
    evaluate_sampling_decision, generate_sampling_candidates, get_decision_trace,
    get_latest_sampling_decision, get_sampling_service, persist_sampling_candidates,
)
from app.db.models import SamplingSiteModel, SamplingDecisionModel, DecisionTraceModel
from app.repositories.cases import CaseRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.sampling import SamplingRepository
from app.schemas.cases import CaseCreateRequest
from app.services.case_service import CaseService
from app.scientific.data_loader import WiggerPreflightLoader
from tests.unit.test_case_creation_integration import _hydrology
from tests.unit.test_investigation_runs import _service
from config import config


def create(db, **changes):
    payload = dict(target_taxon="Fredericella sultana", observation_date=date(2014, 6, 25),
                   detection_site_latitude=47.3140004, detection_site_longitude=7.8954007,
                   detection_site_hyriv_id=20446064, metadata={"additional_metadata": ""},
                   initial_evidence=[{"evidence_type": "edna_observation", "source": "test user record",
                                      "value": {"replicate_results": ["Positive", "Positive", "Negative"]},
                                      "provenance": {"entry_method": "manual"}}])
    payload.update(changes)
    return create_case(CaseCreateRequest(**payload), db, CaseService(CaseRepository(db)), _hydrology())


def test_complete_new_wigger_workflow_preserves_evidence_and_case_ownership(db_session):
    case = create(db_session)
    repo = SamplingRepository(db_session)
    site = repo.get_site_by_id(case.detection_site_id)
    assert site.validation_status.value == "MATCHED"
    assert site.latitude == 47.3140004 and site.longitude == 7.8954007
    assert site.snap_distance_m == pytest.approx(64.81356293400535)
    assert site.metadata["artifact_sha256"] == WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR).validate_frozen_reference()
    before = EvidenceRepository(db_session).get_evidence_by_case(case.id)
    reuse_wigger_reference(db_session, case.id)
    reuse_wigger_reference(db_session, case.id)
    assert len(repo.get_sites_by_case(case.id)) == 4
    assert [z.label for z in repo.get_zones_by_case(case.id)] == ["Z1", "Z2", "Z3"]
    preview = generate_sampling_candidates(case.id, db_session, get_sampling_service(db_session))
    persisted = persist_sampling_candidates(case.id, db_session, get_sampling_service(db_session))
    assert preview.candidates and [c.site_id for c in preview.candidates] == [c.site_id for c in persisted.candidates]
    assert all(repo.get_site_by_id(c.site_id).case_id == case.id for c in persisted.candidates)
    decision = evaluate_sampling_decision(case.id, db_session, get_sampling_service(db_session))
    assert decision.status.value == "TIE"
    assert [repo.get_site_by_id(i).label for i in decision.recommended_site_ids] == ["Site B", "Site C", "Site D"]
    assert get_latest_sampling_decision(case.id, db_session).id == decision.id
    trace = get_decision_trace(case.id, db_session, decision.id)
    assert trace.decision_id == decision.id
    assert trace.evidence_used == [item.id for item in before]
    assessment = next(c for c in trace.hydrology_checks if c.get("check") == "evidence_assessment")
    assert all(a["compatibility"] == "UNKNOWN" for a in assessment["assessments"])
    after = EvidenceRepository(db_session).get_evidence_by_case(case.id)
    assert [(e.id, e.value, e.provenance) for e in before] == [(e.id, e.value, e.provenance) for e in after]
    other = create(db_session)
    assert repo.get_zones_by_case(other.id) == []
    assert all(repo.get_site_by_id(c.site_id).case_id != other.id for c in persisted.candidates)


@pytest.mark.parametrize("changes", [
    {"detection_site_latitude": 47.314},
    {"detection_site_latitude": 47.32},
    {"detection_site_hyriv_id": 20450127},
])
def test_same_reach_does_not_verify_different_coordinates(db_session, changes):
    case = create(db_session, **changes)
    repo = SamplingRepository(db_session)
    assert repo.get_site_by_id(case.detection_site_id).validation_status.value == "NOT_VERIFIED"
    with pytest.raises(HTTPException) as error:
        reuse_wigger_reference(db_session, case.id)
    assert error.value.status_code == 422
    assert repo.get_zones_by_case(case.id) == []
    for operation in (lambda: evaluate_sampling_decision(case.id, db_session, get_sampling_service(db_session)),
                      lambda: _service(db_session).reinvestigate(case.id)):
        with pytest.raises(HTTPException) as error:
            operation()
        assert error.value.status_code == 422
    assert get_latest_sampling_decision(case.id, db_session) is None


def test_reference_button_validates_legacy_site_without_changing_historical_values(db_session):
    case = create(db_session, observation_date=date(2014, 6, 16),
                  metadata={"additional_metadata": "Leave empty if you don't have the original records."})
    stored = db_session.get(SamplingSiteModel, case.detection_site_id)
    stored.validation_status = "NOT_VERIFIED"
    stored.meta = {"origin": "case_creation"}
    db_session.commit()
    reuse_wigger_reference(db_session, case.id)
    assert SamplingRepository(db_session).get_site_by_id(stored.id).validation_status.value == "MATCHED"
    latest_case = CaseRepository(db_session).get_case_by_id(case.id)
    assert latest_case.observation_date == date(2014, 6, 16)
    assert latest_case.metadata == case.metadata


def test_missing_evidence_cannot_produce_a_decision(db_session):
    case = create(db_session, initial_evidence=[])
    reuse_wigger_reference(db_session, case.id)
    with pytest.raises(HTTPException) as error:
        evaluate_sampling_decision(case.id, db_session, get_sampling_service(db_session))
    assert "biological observation evidence" in error.value.detail["message"]
    assert get_latest_sampling_decision(case.id, db_session) is None


def test_failed_assessment_rolls_back_decision_and_trace(db_session, monkeypatch):
    from app.scientific.evidence.engine import EvidenceCompatibilityEngineImpl
    case = create(db_session)
    reuse_wigger_reference(db_session, case.id)
    def fail(*args, **kwargs):
        raise RuntimeError("assessment failure")
    monkeypatch.setattr(EvidenceCompatibilityEngineImpl, "assess_evidence_for_zone", fail)
    with pytest.raises(RuntimeError, match="assessment failure"):
        evaluate_sampling_decision(case.id, db_session, get_sampling_service(db_session))
    assert db_session.scalar(select(SamplingDecisionModel)) is None
    assert db_session.scalar(select(DecisionTraceModel)) is None


def test_unavailable_frozen_provenance_cannot_verify_a_new_location(db_session, monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("Frozen Wigger provenance mismatch")
    monkeypatch.setattr(WiggerPreflightLoader, "validate_frozen_reference", fail)
    case = create(db_session)
    site = SamplingRepository(db_session).get_site_by_id(case.detection_site_id)
    assert site.validation_status.value == "NOT_VERIFIED"
    assert "provenance mismatch" in site.metadata["validation_reason"]


def test_changed_registered_configuration_does_not_force_a_tie(db_session):
    case = create(db_session)
    reuse_wigger_reference(db_session, case.id)
    # Change candidate scope only in this disposable SQLite fixture.
    for site in db_session.scalars(select(SamplingSiteModel).where(SamplingSiteModel.case_id == case.id)).all():
        if site.label in ("Site C", "Site D"):
            db_session.delete(site)
    db_session.commit()
    decision = evaluate_sampling_decision(case.id, db_session, get_sampling_service(db_session))
    assert decision.status.value == "RECOMMEND"
    assert [SamplingRepository(db_session).get_site_by_id(i).label for i in decision.recommended_site_ids] == ["Site B"]


def test_original_demo_reference_button_preserves_original_provenance_and_tie(db_session):
    from app.api.routes.demo import load_wigger_demo
    case = load_wigger_demo(db_session)
    repo = SamplingRepository(db_session)
    zones_before = [(z.id, z.metadata, z.validation_status) for z in repo.get_zones_by_case(case.case_id)]
    reuse_wigger_reference(db_session, case.case_id)
    reuse_wigger_reference(db_session, case.case_id)
    assert [(z.id, z.metadata, z.validation_status) for z in repo.get_zones_by_case(case.case_id)] == zones_before
    assert len(repo.get_sites_by_case(case.case_id)) == 4
    decision = evaluate_sampling_decision(case.case_id, db_session, get_sampling_service(db_session))
    assert decision.status.value == "TIE"
