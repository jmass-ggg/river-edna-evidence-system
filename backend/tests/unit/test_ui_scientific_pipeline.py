"""Registered distance provenance and separate scientific status regressions."""
from dataclasses import replace
from uuid import uuid4

import pytest

from app.api.routes.demo import load_wigger_demo, reuse_wigger_reference
from app.api.routes.evidence import assess_evidence, get_evidence_service
from app.api.routes.sampling import evaluate_sampling_decision, get_latest_sampling_decision, get_sampling_service
from app.repositories.sampling import SamplingRepository
from tests.unit.test_wigger_workflow_repairs import create


def test_registered_reference_distances_persist_without_changing_tie(db_session):
    demo = load_wigger_demo(db_session)
    service = get_sampling_service(db_session)
    decision = evaluate_sampling_decision(demo.case_id, db_session, service)
    expected = {20446064: 0.0, 20450127: 19.22593905163416, 20451169: 23.935939051634158, 20448315: 10.940939051634162}
    candidates = decision.candidate_snapshot['candidates']
    for candidate in candidates:
        assert candidate['network_distance_km'] == pytest.approx(expected[candidate['hyriv_id']])
        assert candidate['network_distance_status'] == 'VALIDATED_REFERENCE'
        assert candidate['network_distance_provenance']['artifact_sha256']
        assert candidate['network_distance_provenance']['to_fraction'] == pytest.approx(0.8574012087748978)
        assert candidate['pair_separation_score'] == (0 if candidate['hyriv_id'] == 20446064 else 2)
    assert decision.status.value == 'TIE'
    db_session.expire_all()
    assert get_latest_sampling_decision(demo.case_id, db_session).candidate_snapshot == decision.candidate_snapshot
    repo = SamplingRepository(db_session)
    detection = repo.get_site_by_id(demo.detection_site_id)
    info = service.registered_candidate_distances([detection], detection)[detection.id]
    assert info['network_distance_km'] == 0
    assert detection.snap_distance_m == pytest.approx(64.81356293400535)


def test_unsupported_biology_keeps_network_and_hypothesis_status_separate(db_session):
    case = create(db_session)
    reuse_wigger_reference(db_session, case.id)
    results = assess_evidence(case.id, db_session, get_evidence_service(db_session))
    assert all(zone.validation_status.value == 'VERIFIED' for zone in SamplingRepository(db_session).get_zones_by_case(case.id))
    assert all(result.hypothesis_status.value == 'UNKNOWN' for result in results)
    for result in results:
        assert result.hypothesis_reason
        assert all(item.compatibility.value == 'UNKNOWN' and item.rule_id is None for item in result.assessments)
        assert all('No validated scientific rule applies' in item.reason for item in result.assessments)


@pytest.mark.parametrize('mode', ['estimated', 'unknown_reach', 'reverse_path', 'reference_conflict'])
def test_registered_distance_boundaries(db_session, mode, monkeypatch):
    demo = load_wigger_demo(db_session)
    service = get_sampling_service(db_session)
    repo = SamplingRepository(db_session)
    detection = repo.get_site_by_id(demo.detection_site_id)
    site = next(site for site in repo.get_sites_by_case(demo.case_id) if site.label == 'Site B')
    if mode == 'estimated':
        site = replace(site, id=uuid4(), latitude=site.latitude+0.01,
                       metadata={'fraction_along_reach':0.99})
    elif mode == 'unknown_reach':
        site = replace(site, hyriv_id=999999)
    elif mode == 'reverse_path':
        site, detection = detection, site
    else:
        monkeypatch.setattr(service.hydrology_engine, 'network_distance_km', lambda *a, **kw: 123.0)
    info = service.registered_candidate_distances([site], detection)[site.id]
    if mode == 'estimated':
        assert info['network_distance_km'] is not None
        assert info['network_distance_status'] == 'ESTIMATED'
        assert info['network_distance_provenance']['from_fraction'] == 0.5
        assert 'not a measured' in info['network_distance_reason']
    else:
        assert info['network_distance_km'] is None
        assert info['network_distance_status'] == 'UNAVAILABLE'
        assert {'unknown_reach':'not found', 'reverse_path':'No directed downstream path', 'reference_conflict':'conflicts'}[mode] in info['network_distance_reason']


def test_missing_validated_fraction_is_an_explicit_estimate(db_session, monkeypatch):
    from app.scientific.data_loader import WiggerPreflightLoader
    demo = load_wigger_demo(db_session)
    service = get_sampling_service(db_session)
    repo = SamplingRepository(db_session)
    detection = repo.get_site_by_id(demo.detection_site_id)
    site = next(site for site in repo.get_sites_by_case(demo.case_id) if site.label == 'Site B')
    def missing():
        raise KeyError('validated fraction missing')
    monkeypatch.setattr(WiggerPreflightLoader, 'load_site_a_snap_validation', lambda self: missing())
    info = service.registered_candidate_distances([site], detection)[site.id]
    assert info['network_distance_status'] == 'ESTIMATED'
    assert info['network_distance_km'] == pytest.approx(18.915)
    assert info['network_distance_provenance']['to_fraction'] == 0.5
    assert 'validated fraction missing' in info['network_distance_reason']
