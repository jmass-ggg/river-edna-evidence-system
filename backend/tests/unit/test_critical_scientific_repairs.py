"""Regression tests for the five scientific trust and history repairs."""
from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.routes.demo import DEMO_KEY, load_wigger_demo, reuse_wigger_reference
from app.api.routes.sampling import get_sampling_service, register_sampling_site
from app.db.models import (
    CaseModel, CandidateZoneModel, DecisionTraceModel, EvidenceItemModel,
    InvestigationRunModel, SamplingDecisionModel, SamplingSiteModel,
)
from app.domain.enums import EvidenceCompatibility, EvidenceStrength, SiteType, ValidationStatus
from app.domain.models import EvidenceItem
from app.repositories.evidence import EvidenceRepository
from app.repositories.sampling import SamplingRepository
from app.schemas.sampling import SamplingSiteCreateRequest
from app.scientific.data_loader import CarraroHistoricalLoader, WiggerPreflightLoader
from app.scientific.evidence.engine import EvidenceCompatibilityEngineImpl
from app.services.one_health_service import OneHealthService
from tests.unit.test_investigation_runs import _service
from tests.unit.test_wigger_workflow_repairs import create


@pytest.mark.parametrize("status", ["VERIFIED", "MATCHED", "SUPPORTED", "ASSUMPTION"])
def test_manual_site_validation_and_fabricated_snap_cannot_grant_eligibility(db_session, status):
    case = create(db_session)
    reuse_wigger_reference(db_session, case.id)
    service = get_sampling_service(db_session)
    request = SamplingSiteCreateRequest(
        label="Untrusted location", latitude=0, longitude=0, hyriv_id=20450127,
        site_type="FOLLOW_UP", validation_status=status,
        network_latitude=47, network_longitude=8, snap_distance_m=0,
        metadata={"validation_status": "VERIFIED", "reference_key": "frozen-wigger-reference-v1"},
    )
    site = register_sampling_site(case.id, request, service)
    assert site.validation_status == ValidationStatus.NOT_VERIFIED
    assert site.network_latitude is None and site.snap_distance_m is None
    assert site.metadata["submitted_metadata"]["validation_status"] == status
    assert site.metadata["validation_method"] == "no_supported_reference_match"
    evaluations = service.sampling_engine.evaluate_candidates(
        case, SamplingRepository(db_session).get_zones_by_case(case.id), [site], service.hydrology_engine,
    )
    assert not evaluations[0]["scientific_state_valid"]
    assert service.sampling_engine.make_recommendation(evaluations)[0].value == "INSUFFICIENT_DATA"


def test_exact_reference_coordinates_are_matched_not_self_verified(db_session):
    case = create(db_session)
    service = get_sampling_service(db_session)
    row = WiggerPreflightLoader().load_sampling_sites().set_index("site").loc["B"]
    site = service.register_sampling_site(
        "Manual B", float(row.latitude), float(row.longitude), int(row.HYRIV_ID),
        site_type=SiteType.FOLLOW_UP,
        validation_status=ValidationStatus.VERIFIED, case_id=case.id, snap_distance_m=999,
    )
    assert site.validation_status == ValidationStatus.MATCHED
    assert site.snap_distance_m == float(row.snap_distance_m)
    assert "not independent" in site.metadata["validation_reason"]


def test_unsupported_site_reach_rejected(db_session):
    case = create(db_session)
    with pytest.raises(HTTPException) as error:
        register_sampling_site(case.id, SamplingSiteCreateRequest(
            label="Outside graph", latitude=0, longitude=0, hyriv_id=999999999,
            site_type="FOLLOW_UP", validation_status="VERIFIED",
        ), get_sampling_service(db_session))
    assert error.value.status_code == 404


@pytest.mark.parametrize("root,site,claim,expected", [
    (20450127, 20446064, True, "SUPPORTS"),
    (20450127, 20451169, False, "CONTRADICTS"),
    (20446064, 20450127, False, "NEUTRAL"),
    (20450127, 20451169, True, "UNKNOWN"),
    (20450127, 20446064, False, "UNKNOWN"),
    (20446064, 20450127, True, "UNKNOWN"),
    (999999999, 20446064, True, "UNKNOWN"),
    (20450127, 999999999, False, "UNKNOWN"),
    ("20450127", 20446064, True, "UNKNOWN"),
    (20450127, 20446064, "true", "UNKNOWN"),
])
def test_connectivity_is_validated_against_directed_graph(db_session, root, site, claim, expected):
    demo = load_wigger_demo(db_session)
    repository = SamplingRepository(db_session)
    from app.repositories.cases import CaseRepository
    case = CaseRepository(db_session).get_case_by_id(demo.case_id)
    zone = next(zone for zone in repository.get_zones_by_case(case.id) if zone.label == "Z2")
    evidence = EvidenceItem(
        id=uuid4(), case_id=case.id, evidence_type="directed_hydrological_connectivity",
        source="untrusted caller", value={"zone_root_hyriv_id": root, "site_hyriv_id": site,
            "can_contribute": claim, "network_validation_status": "VERIFIED", "graph_coverage_validated": True},
        observed_at=None, quality="VERIFIED", provenance={"observation_class": "DERIVED_VALIDATED_TOPOLOGY"},
        created_at=datetime.now(),
    )
    assessment = EvidenceCompatibilityEngineImpl().assess_evidence_for_zone(case, zone, [evidence], [])[0]
    assert assessment.compatibility.value == expected
    check = assessment.provenance["graph_validation"]
    assert check["method"] == "HydrologyEngine.can_contribute"
    if expected == "UNKNOWN":
        assert assessment.rule_id is None and assessment.strength == EvidenceStrength.LOW
    else:
        assert assessment.rule_id == "hydrorivers.directed_contribution.v1"
        assert check["source_graph"]["artifact_sha256"]
        assert assessment.strength == EvidenceStrength.MEDIUM


def test_forged_connectivity_assessed_unknown_after_public_evidence_storage(db_session):
    from app.api.routes.evidence import add_evidence, assess_evidence, get_evidence_service
    from app.schemas.evidence import EvidenceCreateRequest
    demo = load_wigger_demo(db_session)
    service = get_evidence_service(db_session)
    stored = add_evidence(demo.case_id, EvidenceCreateRequest(
        evidence_type="directed_hydrological_connectivity", source="caller",
        value={"zone_root_hyriv_id": 20450127, "site_hyriv_id": 20451169,
               "can_contribute": True, "network_validation_status": "VERIFIED"},
    ), service)
    assessment = next(row for row in assess_evidence(demo.case_id, db_session, service) if row.zone_label == "Z2")
    result = next(item for item in assessment.assessments if item.evidence_id == stored.id)
    assert result.compatibility == EvidenceCompatibility.UNKNOWN


@pytest.mark.parametrize("change", ["identical", "copied_provenance", "missing_provenance", "taxon", "date"])
def test_manual_or_forged_metadata_cannot_become_reference_observation(db_session, change):
    demo = load_wigger_demo(db_session)
    original = db_session.get(CaseModel, demo.case_id)
    metadata = deepcopy(original.meta)
    metadata["reference_provenance"] = deepcopy(original.reference_provenance)
    case = create(db_session, metadata=metadata)
    stored = db_session.get(CaseModel, case.id)
    if change == "missing_provenance":
        stored.meta = {"historical_observation": {"species": "Fredericella sultana", "station": "S1",
                                                  "date": "2014-06-25", "state": "DETECTED"}}
    elif change == "copied_provenance":
        for item in EvidenceRepository(db_session).get_evidence_by_case(original.id):
            EvidenceRepository(db_session).add_evidence(case.id, item.evidence_type, item.source,
                deepcopy(item.value), quality=item.quality, provenance=deepcopy(item.provenance))
    elif change == "taxon":
        stored.target_taxon = "Other taxon"
    elif change == "date":
        stored.observation_date = datetime(2014, 6, 26).date()
    db_session.commit()
    response = OneHealthService(db_session).assess(case.id)
    assert response["pathways"] == []
    assert response["observation_provenance"] == "UNVERIFIED_USER_REPORTED"
    assert stored.reference_key is None
    assert load_wigger_demo(db_session).case_id == original.id


def test_real_reference_requires_intact_sources_and_evidence(db_session, monkeypatch):
    demo = load_wigger_demo(db_session)
    response = OneHealthService(db_session).assess(demo.case_id)
    assert response["observation_provenance"] == "VERIFIED_REFERENCE"
    pathway = response["pathways"][0]
    assert pathway["monitoring_finding"]["status"].value == "OBSERVED"
    assert all(pathway[key]["status"].value == "UNKNOWN" for key in
               ("parasite_presence", "fish_disease_status", "human_health_impact"))
    def unavailable(self):
        raise ValueError("source changed")
    monkeypatch.setattr(CarraroHistoricalLoader, "validate_frozen_reference", unavailable)
    assert OneHealthService(db_session).assess(demo.case_id)["pathways"] == []


@pytest.mark.parametrize("change", ["missing_evidence", "other_case", "observed_at", "quality"])
def test_reference_evidence_link_is_checked(db_session, change):
    demo = load_wigger_demo(db_session)
    case = db_session.get(CaseModel, demo.case_id)
    evidence = db_session.get(EvidenceItemModel, UUID(case.reference_provenance["historical_evidence_id"]))
    if change == "missing_evidence":
        db_session.delete(evidence)
    elif change == "other_case":
        evidence.case_id = create(db_session).id
    elif change == "observed_at":
        evidence.observed_at = datetime(2020, 1, 1)
    else:
        evidence.quality = "USER_REPORTED"
    db_session.commit()
    assert OneHealthService(db_session).assess(demo.case_id)["pathways"] == []


def test_unavailable_rule_cannot_trust_submitted_strength(db_session):
    from app.repositories.cases import CaseRepository
    demo = load_wigger_demo(db_session)
    case = CaseRepository(db_session).get_case_by_id(demo.case_id)
    zone = SamplingRepository(db_session).get_zones_by_case(demo.case_id)[0]
    evidence = next(item for item in EvidenceRepository(db_session).get_evidence_by_case(demo.case_id)
                    if item.evidence_type == "directed_hydrological_connectivity")
    evidence.value = {**evidence.value, "network_validation_status": "VERIFIED", "graph_coverage_validated": True}
    result = EvidenceCompatibilityEngineImpl().assess_evidence_for_zone(
        case, zone, [evidence], [{"id": "unavailable_rule"}],
    )[0]
    assert result.compatibility == EvidenceCompatibility.UNKNOWN
    assert result.strength == EvidenceStrength.LOW


def counts(db):
    return [db.scalar(select(func.count()).select_from(model)) for model in
            (CaseModel, SamplingSiteModel, CandidateZoneModel, EvidenceItemModel)]


@pytest.mark.parametrize("method", ["create_site", "create_zone", "add_evidence"])
def test_demo_failures_roll_back_all_entities(db_session, monkeypatch, method):
    repository = EvidenceRepository if method == "add_evidence" else SamplingRepository
    with monkeypatch.context() as patch:
        original = getattr(repository, method)
        calls = 0
        def fail(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected reference failure")
            return original(*args, **kwargs)
        patch.setattr(repository, method, fail)
        with pytest.raises(RuntimeError, match="injected reference failure"):
            load_wigger_demo(db_session)
    assert counts(db_session) == [0, 0, 0, 0]
    first = load_wigger_demo(db_session)
    second = load_wigger_demo(db_session)
    assert first.case_id == second.case_id and counts(db_session) == [1, 4, 3, 4]


def test_demo_recovers_missing_children_without_changing_unrelated_evidence(db_session):
    demo = load_wigger_demo(db_session)
    extra = EvidenceRepository(db_session).add_evidence(demo.case_id, "field_note", "investigator", "retain")
    db_session.delete(db_session.scalar(select(SamplingSiteModel).where(SamplingSiteModel.label == "Site B")))
    db_session.delete(db_session.scalar(select(CandidateZoneModel).where(CandidateZoneModel.label == "Z3")))
    db_session.delete(db_session.scalar(select(EvidenceItemModel).where(EvidenceItemModel.evidence_type == "historical_edna_measurement")))
    detection = db_session.get(SamplingSiteModel, demo.detection_site_id)
    detection.case_id = None
    db_session.commit()
    restored = load_wigger_demo(db_session)
    assert restored.case_id == demo.case_id and counts(db_session) == [1, 4, 3, 5]
    assert db_session.get(EvidenceItemModel, extra.id).value == "retain"
    assert detection.case_id == demo.case_id
    assert OneHealthService(db_session).assess(demo.case_id)["pathways"]


@pytest.mark.parametrize("entity", ["site", "zone", "evidence", "observation", "detection", "evidence_date", "duplicate_zone", "duplicate_site"])
def test_demo_conflicts_are_not_silently_overwritten(db_session, entity):
    demo = load_wigger_demo(db_session)
    if entity == "site":
        db_session.scalar(select(SamplingSiteModel).where(SamplingSiteModel.label == "Site B")).latitude = 0
    elif entity == "zone":
        db_session.scalar(select(CandidateZoneModel).where(CandidateZoneModel.label == "Z1")).root_hyriv_id = 20450127
    elif entity == "evidence":
        db_session.scalar(select(EvidenceItemModel).where(EvidenceItemModel.evidence_type == "historical_edna_measurement")).value = {"state": "forged"}
    elif entity == "observation":
        case = db_session.get(CaseModel, demo.case_id)
        case.meta = {**case.meta, "historical_observation": {"state": "forged"}}
    elif entity == "evidence_date":
        db_session.scalar(select(EvidenceItemModel).where(EvidenceItemModel.evidence_type == "historical_edna_measurement")).observed_at = datetime(2020, 1, 1)
    elif entity == "duplicate_zone":
        zone = SamplingRepository(db_session).get_zones_by_case(demo.case_id)[0]
        SamplingRepository(db_session).create_zone(demo.case_id, zone.label, zone.root_hyriv_id,
                                                  zone.reach_ids, zone.validation_status, zone.metadata)
    elif entity == "duplicate_site":
        site = next(site for site in SamplingRepository(db_session).get_sites_by_case(demo.case_id) if site.label == "Site B")
        SamplingRepository(db_session).create_site(site.label, site.latitude, site.longitude, site.hyriv_id,
            site.site_type, site.validation_status, case_id=demo.case_id, metadata=site.metadata,
            network_latitude=site.network_latitude, network_longitude=site.network_longitude,
            snap_distance_m=site.snap_distance_m, role=site.role)
    else:
        db_session.get(SamplingSiteModel, demo.detection_site_id).latitude = 0
    db_session.commit()
    before = counts(db_session)
    with pytest.raises(HTTPException) as error:
        load_wigger_demo(db_session)
    assert error.value.status_code == 409 and counts(db_session) == before


@pytest.mark.parametrize("legacy", ["missing_id", "missing_snapshot", "missing_trace", "other_case", "wrong_reach", "missing_score"])
def test_legacy_runs_report_availability_without_mutating_history(db_session, legacy):
    demo = load_wigger_demo(db_session)
    service = _service(db_session)
    result = service.reinvestigate(demo.case_id)
    assert result["compatibility"]["status"] == "COMPLETE"
    run = db_session.get(InvestigationRunModel, result["investigation_run_id"])
    decision = db_session.get(SamplingDecisionModel, result["new_decision_id"])
    candidate_snapshot = deepcopy(run.candidate_snapshot)
    if legacy == "missing_id":
        candidate_snapshot["candidates"][0].pop("site_id")
    elif legacy == "missing_snapshot":
        candidate_snapshot = {}
        decision.candidate_snapshot = {}
    elif legacy == "missing_trace":
        db_session.delete(db_session.scalar(select(DecisionTraceModel).where(DecisionTraceModel.decision_id == decision.id)))
    elif legacy == "other_case":
        other = create(db_session)
        candidate_snapshot["candidates"][0]["site_id"] = str(other.detection_site_id)
    elif legacy == "missing_score":
        candidate_snapshot["candidates"][0]["pair_separation_score"] = None
    else:
        candidate_snapshot["candidates"][0]["hyriv_id"] = 20446064
    run.candidate_snapshot = candidate_snapshot
    db_session.commit()
    originals = deepcopy((run.candidate_snapshot, run.decision_snapshot, decision.recommended_site_ids, decision.candidate_snapshot))
    read = service.detail(demo.case_id, run.id)
    assert read["compatibility"]["status"] == "PARTIAL"
    if legacy == "missing_snapshot":
        assert read["candidate_generation"] == {}
        assert not read["compatibility"]["candidate_comparison_available"]
    if legacy == "missing_trace":
        assert read["decision_trace"] is None
    if legacy == "other_case":
        assert read["compatibility"]["candidate_references"][0]["status"] == "OTHER_CASE"
    db_session.expire_all()
    assert originals == (run.candidate_snapshot, run.decision_snapshot, decision.recommended_site_ids, decision.candidate_snapshot)
    current = service.reinvestigate(demo.case_id)
    assert current["compatibility"]["status"] == "COMPLETE"
    assert service.detail(demo.case_id, run.id)["compatibility"]["status"] == "PARTIAL"


def test_trace_from_another_case_is_not_returned(db_session):
    demo = load_wigger_demo(db_session)
    service = _service(db_session)
    result = service.reinvestigate(demo.case_id)
    other = create(db_session)
    assert service._trace(result["new_decision_id"], other.id) is None


def test_registered_legacy_decision_exposes_missing_comparison_and_trace(db_session):
    from app.api.routes.sampling import get_latest_sampling_decision
    demo = load_wigger_demo(db_session)
    row = SamplingDecisionModel(case_id=demo.case_id, status="TIE", recommended_site_ids=[uuid4()],
        rationale="Historical result", candidate_scope="GENERATED_REPRESENTATIVES", candidate_snapshot={})
    db_session.add(row)
    db_session.commit()
    result = get_latest_sampling_decision(demo.case_id, db_session)
    assert result.candidate_snapshot == {} and result.rationale == "Historical result"
    assert result.compatibility["status"] == "PARTIAL"
    assert not result.compatibility["decision_trace_available"]
    assert result.compatibility["recommended_references"][0]["status"] == "MISSING_RECORD"
