"""
Property-based tests for Evidence Compatibility Engine.

These tests validate universal properties across many generated inputs,
ensuring correctness for evidence assessment logic.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from app.domain.enums import (
    CaseStatus,
    EvidenceCompatibility,
    EvidenceStrength,
    SiteType,
    ValidationStatus,
)
from app.domain.models import (
    Case,
    CandidateZone,
    EvidenceAssessment,
    EvidenceItem,
    SamplingSite,
)
from app.scientific.evidence.engine import EvidenceCompatibilityEngineImpl
from app.scientific.rules.catalog import get_rule_catalog
from app.scientific.sampling.engine import ScaffoldSamplingDecisionEngine


# Strategy for generating valid EvidenceCompatibility enum values
compatibility_strategy = st.sampled_from([
    EvidenceCompatibility.SUPPORTS,
    EvidenceCompatibility.CONTRADICTS,
    EvidenceCompatibility.NEUTRAL,
    EvidenceCompatibility.UNKNOWN
])


# Strategy for generating EvidenceAssessment objects
def evidence_assessment_strategy():
    """Generate random EvidenceAssessment objects for testing."""
    return st.builds(
        EvidenceAssessment,
        evidence_id=st.builds(UUID, int=st.integers(min_value=0, max_value=2**128-1)),
        compatibility=compatibility_strategy,
        rule_id=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
        reason=st.text(min_size=1, max_size=100),
        provenance=st.just({})
    )


@pytest.fixture
def engine():
    """Create an evidence compatibility engine instance."""
    return EvidenceCompatibilityEngineImpl()


@pytest.fixture
def case_and_zone():
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
    zone = CandidateZone(
        id=uuid4(),
        case_id=case_id,
        label="Z2",
        root_hyriv_id=200,
        reach_ids=[200],
        validation_status=ValidationStatus.VERIFIED,
    )
    return case, zone


def connectivity_evidence(case_id, root, can_contribute, status="VERIFIED"):
    return EvidenceItem(
        id=uuid4(),
        case_id=case_id,
        evidence_type="directed_hydrological_connectivity",
        source="test graph traversal",
        value={
            "zone_root_hyriv_id": root,
            "site_hyriv_id": 900,
            "can_contribute": can_contribute,
            "network_validation_status": status,
        },
        observed_at=None,
        quality="validated",
        provenance={"method": "NEXT_DOWN traversal"},
        created_at=datetime.now(),
    )


# Feature: edna-backend-foundation, Property 11: Evidence assessment summary accuracy
# Validates: Requirements 6.5
@given(assessments=st.lists(evidence_assessment_strategy(), min_size=0, max_size=50))
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_summary_accuracy(engine, assessments):
    """
    Property: For any set of evidence assessments, the summary counts for
    SUPPORTS, CONTRADICTS, NEUTRAL, and UNKNOWN should equal the sum of
    assessments with each respective status.
    
    This property ensures that the summary accurately reflects the assessment
    distribution without losing or double-counting assessments.
    
    Feature: edna-backend-foundation, Property 11: Evidence assessment summary accuracy
    Validates: Requirements 6.5
    """
    # Get the summary
    summary = engine.summarize_zone_assessment(assessments)
    
    # Manually count each compatibility status
    expected_supports = sum(
        1 for a in assessments 
        if a.compatibility == EvidenceCompatibility.SUPPORTS
    )
    expected_contradicts = sum(
        1 for a in assessments 
        if a.compatibility == EvidenceCompatibility.CONTRADICTS
    )
    expected_neutral = sum(
        1 for a in assessments 
        if a.compatibility == EvidenceCompatibility.NEUTRAL
    )
    expected_unknown = sum(
        1 for a in assessments 
        if a.compatibility == EvidenceCompatibility.UNKNOWN
    )
    
    # Verify summary matches expected counts
    assert summary["supports"] == expected_supports, (
        f"Expected {expected_supports} SUPPORTS, got {summary['supports']}"
    )
    assert summary["contradicts"] == expected_contradicts, (
        f"Expected {expected_contradicts} CONTRADICTS, got {summary['contradicts']}"
    )
    assert summary["neutral"] == expected_neutral, (
        f"Expected {expected_neutral} NEUTRAL, got {summary['neutral']}"
    )
    assert summary["unknown"] == expected_unknown, (
        f"Expected {expected_unknown} UNKNOWN, got {summary['unknown']}"
    )
    
    # Verify the sum equals total assessments
    total_in_summary = (
        summary["supports"] + 
        summary["contradicts"] + 
        summary["neutral"] + 
        summary["unknown"]
    )
    assert total_in_summary == len(assessments), (
        f"Summary total {total_in_summary} doesn't match "
        f"assessment count {len(assessments)}"
    )


@pytest.mark.parametrize(
    ("root", "can_contribute", "expected"),
    [
        (200, True, EvidenceCompatibility.SUPPORTS),
        (200, False, EvidenceCompatibility.CONTRADICTS),
        (201, True, EvidenceCompatibility.NEUTRAL),
    ],
)
def test_topology_rule_states(
    engine, case_and_zone, root, can_contribute, expected
):
    case, zone = case_and_zone
    evidence = connectivity_evidence(case.id, root, can_contribute)
    result = engine.assess_evidence_for_zone(case, zone, [evidence], [])
    assert result[0].compatibility == expected
    assert result[0].rule_id == "hydrorivers.directed_contribution.v1"
    assert result[0].provenance["rule_limitations"]


def test_unknown_for_missing_or_unsupported_evidence(engine, case_and_zone):
    case, zone = case_and_zone
    incomplete = connectivity_evidence(case.id, 200, True)
    incomplete.value.pop("can_contribute")
    unsupported = EvidenceItem(
        id=uuid4(), case_id=case.id, evidence_type="organism_abundance",
        source="unknown", value=42, observed_at=None, quality=None,
        provenance={}, created_at=datetime.now(),
    )
    results = engine.assess_evidence_for_zone(
        case, zone, [incomplete, unsupported], []
    )
    assert [r.compatibility for r in results] == [
        EvidenceCompatibility.UNKNOWN,
        EvidenceCompatibility.UNKNOWN,
    ]
    assert all(r.rule_id is None for r in results)


def test_conflicting_and_missing_evidence_are_not_collapsed(engine, case_and_zone):
    case, zone = case_and_zone
    evidence = [
        connectivity_evidence(case.id, 200, True),
        connectivity_evidence(case.id, 200, False),
    ]
    results = engine.assess_evidence_for_zone(case, zone, evidence, [])
    assert engine.summarize_zone_assessment(results) == {
        "supports": 1,
        "contradicts": 1,
        "neutral": 0,
        "unknown": 0,
    }
    assert engine.assess_evidence_for_zone(case, zone, [], []) == []


def test_rule_catalog_is_complete_and_limited():
    required = {
        "id", "version", "name", "description", "condition", "effect",
        "reason", "provenance/source", "limitations", "validation_status",
    }
    rules = get_rule_catalog()
    assert rules
    assert all(required <= rule.keys() for rule in rules)
    assert all(rule["validation_status"] == "VERIFIED" for rule in rules)


@pytest.mark.parametrize(
    ("can_contribute", "expected_direction"),
    [
        (True, EvidenceCompatibility.SUPPORTS),
        (False, EvidenceCompatibility.CONTRADICTS),
    ],
)
def test_direction_and_strength_are_independent(
    engine, case_and_zone, can_contribute, expected_direction
):
    case, zone = case_and_zone
    evidence = connectivity_evidence(case.id, 200, can_contribute)
    evidence.value["graph_coverage_validated"] = True
    result = engine.assess_evidence_for_zone(case, zone, [evidence], [])[0]
    assert result.compatibility == expected_direction
    assert result.strength == EvidenceStrength.HIGH
    assert result.strength_rule_id == "hydrorivers.directed_connectivity_strength.v1"
    assert result.strength_rule_version == "1.0.0"
    assert result.strength_criteria
    assert result.strength_reason
    assert result.strength_provenance
    assert result.strength_limitations
    assert "%" not in result.strength_reason
    assert "probability" in " ".join(result.strength_limitations).lower()


def test_unsupported_strength_is_unassessed(engine, case_and_zone):
    case, zone = case_and_zone
    evidence = EvidenceItem(
        id=uuid4(), case_id=case.id, evidence_type="organism_abundance",
        source="test", value=1, observed_at=None, quality=None,
        provenance={}, created_at=datetime.now(),
    )
    result = engine.assess_evidence_for_zone(case, zone, [evidence], [])[0]
    assert result.compatibility == EvidenceCompatibility.UNKNOWN
    assert result.strength == EvidenceStrength.UNASSESSED
    assert result.strength_reason == (
        "No validated strength rule exists for this evidence type."
    )
    assert result.strength_rule_id is None


def test_strength_is_deterministic_and_missing_quality_is_safe(
    engine, case_and_zone
):
    case, zone = case_and_zone
    evidence = connectivity_evidence(case.id, 200, True)
    evidence.quality = None
    first = engine.assess_evidence_for_zone(case, zone, [evidence], [])[0]
    second = engine.assess_evidence_for_zone(case, zone, [evidence], [])[0]
    assert first.strength == second.strength == EvidenceStrength.MEDIUM
    assert first.strength_criteria == second.strength_criteria
    assert first.strength_reason == second.strength_reason


def test_strength_metadata_does_not_change_sampling_score(engine, case_and_zone):
    case, first_zone = case_and_zone
    second_zone = CandidateZone(
        id=uuid4(), case_id=case.id, label="Z3", root_hyriv_id=201,
        reach_ids=[201], validation_status=ValidationStatus.VERIFIED,
    )
    site = SamplingSite(
        id=uuid4(), case_id=case.id, label="candidate", latitude=47.0,
        longitude=7.0, hyriv_id=900, site_type=SiteType.FOLLOW_UP,
        validation_status=ValidationStatus.VERIFIED,
    )

    class Hydrology:
        def can_contribute(self, root_hyriv_id, site_hyriv_id):
            return root_hyriv_id == 200

    sampling = ScaffoldSamplingDecisionEngine()
    before = sampling.evaluate_candidates(
        case, [first_zone, second_zone], [site], Hydrology()
    )[0]["scores"]
    evidence = connectivity_evidence(case.id, 200, True)
    evidence.value["graph_coverage_validated"] = True
    assert engine.assess_evidence_for_zone(
        case, first_zone, [evidence], []
    )[0].strength == EvidenceStrength.HIGH
    after = sampling.evaluate_candidates(
        case, [first_zone, second_zone], [site], Hydrology()
    )[0]["scores"]
    assert before == after == {
        "separated_hypothesis_pairs": 1,
        "distinct_outcomes": 2,
    }
