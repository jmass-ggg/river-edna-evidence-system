"""
Property-based tests for Sampling Decision Engine.

These tests validate universal properties across many generated inputs,
ensuring correctness for sampling decision and trace logic.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from app.domain.enums import CaseStatus, SamplingDecisionStatus, SiteType, ValidationStatus
from app.domain.models import (
    Case,
    CandidateZone,
    SamplingSite,
)
from app.scientific.sampling.engine import ScaffoldSamplingDecisionEngine
from app.scientific.hydrology.engine import HydrologyEngine
from app.scientific.sampling.candidate_generator import CandidateSiteGenerator


# Strategy for generating valid UUID objects
def uuid_strategy():
    """Generate random UUID objects."""
    return st.builds(UUID, int=st.integers(min_value=0, max_value=2**128-1))


# Strategy for generating Case objects
def case_strategy():
    """Generate random Case objects for testing."""
    return st.builds(
        Case,
        id=uuid_strategy(),
        target_taxon=st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'))),
        observation_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2026, 12, 31)),
        detection_site_id=uuid_strategy(),
        status=st.sampled_from([CaseStatus.ACTIVE, CaseStatus.UNDER_REVIEW, CaseStatus.COMPLETED]),
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2026, 12, 31)),
        updated_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2026, 12, 31)),
        metadata=st.just({})
    )


# Strategy for generating CandidateZone objects
def candidate_zone_strategy(case_id: UUID):
    """Generate random CandidateZone objects for testing."""
    return st.builds(
        CandidateZone,
        id=uuid_strategy(),
        case_id=st.just(case_id),
        label=st.text(min_size=2, max_size=10),
        root_hyriv_id=st.integers(min_value=20000000, max_value=21000000),
        reach_ids=st.lists(st.integers(min_value=20000000, max_value=21000000), min_size=1, max_size=20),
        validation_status=st.sampled_from([ValidationStatus.VERIFIED, ValidationStatus.SUPPORTED, ValidationStatus.ASSUMPTION]),
        metadata=st.just({})
    )


# Strategy for generating SamplingSite objects  
def sampling_site_strategy(case_id: UUID):
    """Generate random SamplingSite objects for testing."""
    return st.builds(
        SamplingSite,
        id=uuid_strategy(),
        case_id=st.just(case_id),
        label=st.text(min_size=1, max_size=20),
        latitude=st.floats(min_value=45.0, max_value=48.0),
        longitude=st.floats(min_value=5.0, max_value=10.0),
        hyriv_id=st.integers(min_value=20000000, max_value=21000000),
        site_type=st.sampled_from([SiteType.DETECTION_SITE, SiteType.BRANCH_SPECIFIC, SiteType.SHARED_TRUNK]),
        validation_status=st.sampled_from([ValidationStatus.VERIFIED, ValidationStatus.SUPPORTED]),
        network_latitude=st.one_of(st.none(), st.floats(min_value=45.0, max_value=48.0)),
        network_longitude=st.one_of(st.none(), st.floats(min_value=5.0, max_value=10.0)),
        snap_distance_m=st.one_of(st.none(), st.floats(min_value=0.0, max_value=500.0)),
        role=st.one_of(st.none(), st.text(min_size=5, max_size=30)),
        metadata=st.just({})
    )


@pytest.fixture
def sampling_engine():
    """Create a sampling decision engine instance."""
    return ScaffoldSamplingDecisionEngine()


@pytest.fixture
def hydrology_engine():
    """Create a hydrology engine instance with test data."""
    # Use a minimal test setup - in real tests we'd use actual preflight data
    from pathlib import Path
    from app.scientific.data_loader import WiggerPreflightLoader
    
    data_dir = Path("../data_preflight/outputs")
    
    if not data_dir.exists():
        pytest.skip("Preflight data directory not available")
    
    try:
        loader = WiggerPreflightLoader(data_dir=data_dir)
        reaches = loader.load_reaches()
        edges = loader.load_edges()
        return HydrologyEngine(reaches=reaches, edges=edges)
    except Exception as e:
        pytest.skip(f"Could not initialize hydrology engine: {e}")


# Feature: edna-backend-foundation, Property 20: Decision trace completeness
# Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5
@given(
    case=case_strategy(),
    num_zones=st.integers(min_value=1, max_value=5),
    num_sites=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_decision_trace_completeness(sampling_engine, hydrology_engine, case, num_zones, num_sites):
    """
    Property: For any decision trace, it should include lists of: evidence_used
    (UUIDs), rules_applied (strings), hydrology_checks (objects), assumptions
    (strings), and limitations (strings).
    
    This property ensures that decision traces provide complete audit information,
    allowing decisions to be reviewed and validated by scientific reviewers.
    
    Feature: edna-backend-foundation, Property 20: Decision trace completeness
    Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5
    """
    # Generate zones and sites for this case
    zones = [
        CandidateZone(
            id=uuid4(),
            case_id=case.id,
            label=f"Z{i+1}",
            root_hyriv_id=20000000 + i * 10000,
            reach_ids=[20000000 + i * 10000 + j for j in range(5)],
            validation_status=ValidationStatus.ASSUMPTION,
            metadata={}
        )
        for i in range(num_zones)
    ]
    
    candidate_sites = [
        SamplingSite(
            id=uuid4(),
            case_id=case.id,
            label=f"Site_{chr(65+i)}",  # A, B, C, etc.
            latitude=47.0 + i * 0.1,
            longitude=7.0 + i * 0.1,
            hyriv_id=20000000 + i * 5000,
            site_type=SiteType.BRANCH_SPECIFIC if i > 0 else SiteType.DETECTION_SITE,
            validation_status=ValidationStatus.SUPPORTED,
            metadata={}
        )
        for i in range(num_sites)
    ]
    
    # Perform evaluation (will return INSUFFICIENT_DATA in scaffold)
    evaluations = sampling_engine.evaluate_candidates(
        case=case,
        zones=zones,
        candidate_sites=candidate_sites,
        hydrology_engine=hydrology_engine
    )
    
    # Make recommendation
    status, recommended_site_ids, rationale = sampling_engine.make_recommendation(evaluations)
    
    # Create decision trace
    decision_id = uuid4()
    trace = sampling_engine.create_decision_trace(
        case=case,
        evaluations=evaluations,
        status=status,
        recommended_site_ids=recommended_site_ids,
        decision_id=decision_id
    )
    
    # Verify trace has all required fields (Requirements 10.1-10.5)
    assert hasattr(trace, 'decision_id'), "Trace missing decision_id"
    assert hasattr(trace, 'evidence_used'), "Trace missing evidence_used"
    assert hasattr(trace, 'rules_applied'), "Trace missing rules_applied"
    assert hasattr(trace, 'hydrology_checks'), "Trace missing hydrology_checks"
    assert hasattr(trace, 'assumptions'), "Trace missing assumptions"
    assert hasattr(trace, 'limitations'), "Trace missing limitations"
    assert hasattr(trace, 'created_at'), "Trace missing created_at"
    
    # Verify decision_id matches
    assert trace.decision_id == decision_id, (
        f"Trace decision_id {trace.decision_id} doesn't match expected {decision_id}"
    )
    
    # Verify all fields are of correct types (Requirements 10.1, 10.2, 10.3, 10.4, 10.5)
    assert isinstance(trace.evidence_used, list), (
        f"evidence_used should be a list, got {type(trace.evidence_used)}"
    )
    assert all(isinstance(eid, UUID) for eid in trace.evidence_used), (
        "All evidence_used items should be UUIDs"
    )
    
    assert isinstance(trace.rules_applied, list), (
        f"rules_applied should be a list, got {type(trace.rules_applied)}"
    )
    assert all(isinstance(rule, str) for rule in trace.rules_applied), (
        "All rules_applied items should be strings"
    )
    
    assert isinstance(trace.hydrology_checks, list), (
        f"hydrology_checks should be a list, got {type(trace.hydrology_checks)}"
    )
    assert all(isinstance(check, dict) for check in trace.hydrology_checks), (
        "All hydrology_checks items should be dictionaries"
    )
    
    assert isinstance(trace.assumptions, list), (
        f"assumptions should be a list, got {type(trace.assumptions)}"
    )
    assert all(isinstance(assumption, str) for assumption in trace.assumptions), (
        "All assumptions items should be strings"
    )
    
    assert isinstance(trace.limitations, list), (
        f"limitations should be a list, got {type(trace.limitations)}"
    )
    assert all(isinstance(limitation, str) for limitation in trace.limitations), (
        "All limitations items should be strings"
    )
    
    assert isinstance(trace.created_at, datetime), (
        f"created_at should be a datetime, got {type(trace.created_at)}"
    )
    
    # Verify that the trace contains non-empty lists for key audit fields
    # (The scaffold should document assumptions and limitations even when incomplete)
    assert len(trace.assumptions) > 0, (
        "Trace should contain at least some assumptions"
    )
    assert len(trace.limitations) > 0, (
        "Trace should contain at least some limitations"
    )
    
    # Verify hydrology_checks were captured from evaluations
    # The scaffold performs reachability checks, so we should see them in the trace
    total_checks_in_evaluations = sum(
        len(eval_rec.get("hydrology_checks", [])) 
        for eval_rec in evaluations
    )
    assert len(trace.hydrology_checks) == total_checks_in_evaluations, (
        f"Expected {total_checks_in_evaluations} hydrology checks in trace, "
        f"got {len(trace.hydrology_checks)}"
    )


class SignatureHydrology:
    def __init__(self, signatures):
        self.signatures = signatures

    def can_contribute(self, source_hyriv_id, site_hyriv_id):
        return self.signatures[(source_hyriv_id, site_hyriv_id)]


def decision_inputs(signatures, zone_status=ValidationStatus.VERIFIED):
    case_id = uuid4()
    case = Case(
        id=case_id,
        target_taxon="Test taxon",
        observation_date=date(2026, 1, 1),
        detection_site_id=uuid4(),
        status=CaseStatus.ACTIVE,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    roots = sorted({root for root, _ in signatures})
    site_reaches = sorted({site for _, site in signatures})
    zones = [
        CandidateZone(
            id=uuid4(), case_id=case_id, label=f"Z{i + 1}",
            root_hyriv_id=root, reach_ids=[root],
            validation_status=zone_status,
        )
        for i, root in enumerate(roots)
    ]
    sites = [
        SamplingSite(
            id=uuid4(), case_id=case_id, label=label,
            latitude=47.0, longitude=7.0, hyriv_id=reach,
            site_type=SiteType.FOLLOW_UP,
            validation_status=ValidationStatus.VERIFIED,
        )
        for label, reach in zip("BCDEFG", site_reaches)
    ]
    return case, zones, sites, SignatureHydrology(signatures)


def evaluate_signature_scenario(engine, signatures, zone_status=ValidationStatus.VERIFIED):
    case, zones, sites, hydrology = decision_inputs(signatures, zone_status)
    evaluations = engine.evaluate_candidates(case, zones, sites, hydrology)
    return sites, evaluations, engine.make_recommendation(evaluations)


def test_strict_win_recommends_most_informative_site(sampling_engine):
    # B separates 2x2=4 pairs; C separates 1x3=3 pairs.
    signatures = {
        (1, 10): True, (2, 10): True, (3, 10): False, (4, 10): False,
        (1, 20): True, (2, 20): False, (3, 20): False, (4, 20): False,
    }
    sites, _, (status, winners, _) = evaluate_signature_scenario(
        sampling_engine, signatures
    )
    assert status == SamplingDecisionStatus.RECOMMEND
    assert winners == [sites[0].id]


def test_equal_informative_sites_tie(sampling_engine):
    signatures = {
        (1, 10): True, (2, 10): False, (3, 10): False,
        (1, 20): False, (2, 20): True, (3, 20): False,
    }
    sites, _, (status, winners, _) = evaluate_signature_scenario(
        sampling_engine, signatures
    )
    assert status == SamplingDecisionStatus.TIE
    assert winners == [site.id for site in sites]


def test_b_can_lose(sampling_engine):
    signatures = {
        (1, 10): True, (2, 10): True, (3, 10): True,
        (1, 20): False, (2, 20): True, (3, 20): False,
    }
    sites, _, (status, winners, _) = evaluate_signature_scenario(
        sampling_engine, signatures
    )
    assert status == SamplingDecisionStatus.RECOMMEND
    assert sites[0].id not in winners
    assert winners == [sites[1].id]


def test_abstain_when_no_site_discriminates(sampling_engine):
    signatures = {
        (1, 10): True, (2, 10): True,
        (1, 20): False, (2, 20): False,
    }
    _, _, (status, winners, _) = evaluate_signature_scenario(
        sampling_engine, signatures
    )
    assert status == SamplingDecisionStatus.ABSTAIN
    assert winners == []


def test_not_verified_state_is_insufficient(sampling_engine):
    signatures = {(1, 10): True, (2, 10): False}
    _, _, (status, winners, _) = evaluate_signature_scenario(
        sampling_engine, signatures, ValidationStatus.NOT_VERIFIED
    )
    assert status == SamplingDecisionStatus.INSUFFICIENT_DATA
    assert winners == []


def test_identical_discriminating_signatures_do_not_force_choice(sampling_engine):
    signatures = {
        (1, 10): True, (2, 10): False,
        (1, 20): True, (2, 20): False,
    }
    sites, evaluations, (status, winners, _) = evaluate_signature_scenario(
        sampling_engine, signatures
    )
    assert evaluations[0]["signature"] == evaluations[1]["signature"]
    assert status == SamplingDecisionStatus.TIE
    assert winners == [site.id for site in sites]


def test_one_hypothesis_remaining_abstains(sampling_engine):
    signatures = {(1, 10): True, (1, 20): False}
    _, _, (status, winners, _) = evaluate_signature_scenario(
        sampling_engine, signatures
    )
    assert status == SamplingDecisionStatus.ABSTAIN
    assert winners == []


class GeneratorHydrology:
    def __init__(self, upstream, signatures, distances):
        self.upstream = upstream
        self.signatures = signatures
        self.distances = distances

    def get_upstream_reaches(self, site_hyriv_id):
        return list(self.upstream)

    def get_reach(self, hyriv_id):
        if hyriv_id not in self.upstream and hyriv_id != 99:
            raise ValueError("not in validated graph")
        return object()

    def can_contribute(self, root_hyriv_id, site_hyriv_id):
        return self.signatures[(root_hyriv_id, site_hyriv_id)]

    def network_distance_km(
        self, from_hyriv_id, to_hyriv_id, from_fraction=0.5, to_fraction=1.0
    ):
        return self.distances.get(from_hyriv_id)


def generator_zones(count=3):
    case_id = uuid4()
    return [
        CandidateZone(
            id=uuid4(), case_id=case_id, label=f"H{i + 1}",
            root_hyriv_id=i + 1, reach_ids=[i + 1],
            validation_status=ValidationStatus.VERIFIED,
        )
        for i in range(count)
    ]


def test_candidate_generator_groups_signatures_scores_and_is_deterministic():
    signatures = {
        (1, 10): True, (2, 10): False, (3, 10): False,
        (1, 11): True, (2, 11): False, (3, 11): False,
        (1, 12): False, (2, 12): True, (3, 12): True,
    }
    hydrology = GeneratorHydrology(
        upstream=[10, 11, 12], signatures=signatures,
        distances={10: 5.0, 11: 2.0, 12: 3.0},
    )
    generator = CandidateSiteGenerator(hydrology)
    first = generator.generate(generator_zones(), 99)
    second = generator.generate(generator_zones(), 99)
    assert first.eligible_reach_count == 3
    assert {candidate.hyriv_id for candidate in first.candidates} == {11, 12}
    assert all(candidate.pair_separation_score == 2 for candidate in first.candidates)
    grouped = next(
        candidate
        for candidate in first.candidates
        if candidate.equivalent_hyriv_ids == [10, 11]
    )
    assert grouped.hyriv_id == 11
    assert [candidate.hyriv_id for candidate in first.candidates] == [
        candidate.hyriv_id for candidate in second.candidates
    ]


def test_candidate_generator_rejects_disconnected_and_excludes_site_a():
    signatures = {(1, 10): True, (2, 10): False}
    hydrology = GeneratorHydrology([10], signatures, {10: 1.0})
    result = CandidateSiteGenerator(hydrology).generate(
        generator_zones(2), 99, candidate_hyriv_ids=[10, 50, 99]
    )
    assert result.eligible_reach_count == 1
    assert result.candidates[0].hyriv_id == 10


def test_candidate_generator_has_no_special_b_and_changes_with_topology():
    zones = generator_zones(2)
    first = GeneratorHydrology(
        [10, 20],
        {(1, 10): True, (2, 10): False, (1, 20): True, (2, 20): True},
        {10: 5.0, 20: 1.0},
    )
    changed = GeneratorHydrology(
        [10, 20],
        {(1, 10): True, (2, 10): True, (1, 20): False, (2, 20): True},
        {10: 5.0, 20: 1.0},
    )
    assert [c.hyriv_id for c in CandidateSiteGenerator(first).generate(zones, 99).candidates] == [10]
    assert [c.hyriv_id for c in CandidateSiteGenerator(changed).generate(zones, 99).candidates] == [20]


def test_candidate_generator_handles_zero_and_one_hypothesis_safely():
    hydrology = GeneratorHydrology([10], {(1, 10): True}, {10: 1.0})
    generator = CandidateSiteGenerator(hydrology)
    assert generator.generate([], 99).candidates == []
    one = generator.generate(generator_zones(1), 99)
    assert one.candidates == []
    assert one.equivalence_classes[0].pair_separation_score == 0
