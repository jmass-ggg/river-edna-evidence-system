"""
Property-based tests for JSON response schema consistency.

These tests validate that Pydantic schemas produce consistent JSON structures
with required fields present and properly typed across many generated inputs.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from app.domain.enums import (
    CaseStatus,
    EvidenceCompatibility,
    SamplingDecisionStatus,
    SiteType,
    ValidationStatus,
)
from app.schemas.cases import CaseCreateRequest, CaseResponse, CaseListResponse
from app.schemas.evidence import (
    EvidenceCreateRequest,
    EvidenceResponse,
    EvidenceAssessmentResponse,
    AssessmentSummaryResponse,
)
from app.schemas.hydrology import (
    ReachResponse,
    UpstreamQueryResponse,
    DownstreamPathResponse,
    NetworkDistanceResponse,
)
from app.schemas.sampling import (
    SamplingSiteCreateRequest,
    SamplingSiteResponse,
    CandidateZoneCreateRequest,
    CandidateZoneResponse,
    SamplingDecisionResponse,
    DecisionTraceResponse,
)


# Strategies for generating valid enum values
case_status_strategy = st.sampled_from([
    CaseStatus.ACTIVE,
    CaseStatus.UNDER_REVIEW,
    CaseStatus.COMPLETED,
    CaseStatus.ARCHIVED,
])

evidence_compatibility_strategy = st.sampled_from([
    EvidenceCompatibility.SUPPORTS,
    EvidenceCompatibility.CONTRADICTS,
    EvidenceCompatibility.NEUTRAL,
    EvidenceCompatibility.UNKNOWN,
])

sampling_decision_status_strategy = st.sampled_from([
    SamplingDecisionStatus.RECOMMEND,
    SamplingDecisionStatus.TIE,
    SamplingDecisionStatus.ABSTAIN,
    SamplingDecisionStatus.INSUFFICIENT_DATA,
])

site_type_strategy = st.sampled_from([
    SiteType.DETECTION_SITE,
    SiteType.BRANCH_SPECIFIC,
    SiteType.SHARED_TRUNK,
    SiteType.FOLLOW_UP,
])

validation_status_strategy = st.sampled_from([
    ValidationStatus.VERIFIED,
    ValidationStatus.SUPPORTED,
    ValidationStatus.ASSUMPTION,
    ValidationStatus.NOT_VERIFIED,
])

# Helper strategies for common data types
uuid_strategy = st.builds(UUID, int=st.integers(min_value=0, max_value=2**128-1))
datetime_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
)
date_strategy = st.dates(
    min_value=date(2020, 1, 1),
    max_value=date(2030, 12, 31),
)
latitude_strategy = st.floats(min_value=-90, max_value=90)
longitude_strategy = st.floats(min_value=-180, max_value=180)
hyriv_id_strategy = st.integers(min_value=1, max_value=100000000)


# Feature: edna-backend-foundation, Property 26: JSON response structure consistency
# Validates: Requirements 18.2, 18.5
@given(
    case_id=uuid_strategy,
    target_taxon=st.text(min_size=1, max_size=100),
    observation_date=date_strategy,
    detection_site_id=uuid_strategy,
    status=case_status_strategy,
    created_at=datetime_strategy,
    updated_at=datetime_strategy,
    metadata=st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.one_of(st.text(max_size=50), st.integers(), st.floats(), st.booleans()),
        max_size=5
    )
)
@settings(max_examples=100)
def test_case_response_structure_consistency(
    case_id, target_taxon, observation_date, detection_site_id,
    status, created_at, updated_at, metadata
):
    """
    Property: For any CaseResponse with valid data, the JSON representation
    should include all required fields (id, target_taxon, observation_date,
    detection_site_id, status, created_at, updated_at, metadata) and all
    timestamp fields should be present as ISO 8601 strings.
    
    This ensures consistent JSON structure across all case responses.
    
    Feature: edna-backend-foundation, Property 26: JSON response structure consistency
    Validates: Requirements 18.2, 18.5
    """
    # Create the response schema
    response = CaseResponse(
        id=case_id,
        target_taxon=target_taxon,
        observation_date=observation_date,
        detection_site_id=detection_site_id,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        metadata=metadata
    )
    
    # Serialize to JSON dict
    json_data = response.model_dump(mode='json')
    
    # Verify all required fields are present
    required_fields = {
        'id', 'target_taxon', 'observation_date', 'detection_site_id',
        'status', 'created_at', 'updated_at', 'metadata'
    }
    assert set(json_data.keys()) == required_fields, (
        f"Missing or extra fields in JSON. Expected {required_fields}, "
        f"got {set(json_data.keys())}"
    )
    
    # Verify timestamps are ISO 8601 strings
    assert isinstance(json_data['created_at'], str), "created_at should be a string"
    assert isinstance(json_data['updated_at'], str), "updated_at should be a string"
    
    # Verify date is ISO format
    assert isinstance(json_data['observation_date'], str), "observation_date should be a string"
    
    # Verify metadata is a dict
    assert isinstance(json_data['metadata'], dict), "metadata should be a dict"


# Feature: edna-backend-foundation, Property 26: JSON response structure consistency
# Validates: Requirements 18.2, 18.5
@given(
    evidence_id=uuid_strategy,
    case_id=uuid_strategy,
    evidence_type=st.text(min_size=1, max_size=50),
    source=st.text(min_size=1, max_size=50),
    value=st.one_of(
        st.text(max_size=100),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.dictionaries(
            st.text(min_size=1, max_size=10),
            st.integers(),
            max_size=3
        )
    ),
    observed_at=st.one_of(st.none(), datetime_strategy),
    quality=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
    provenance=st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.text(max_size=50),
        max_size=3
    ),
    created_at=datetime_strategy
)
@settings(max_examples=100)
def test_evidence_response_structure_consistency(
    evidence_id, case_id, evidence_type, source, value,
    observed_at, quality, provenance, created_at
):
    """
    Property: For any EvidenceResponse with valid data, the JSON representation
    should include all required fields and timestamps should be ISO 8601 strings.
    
    Feature: edna-backend-foundation, Property 26: JSON response structure consistency
    Validates: Requirements 18.2, 18.5
    """
    response = EvidenceResponse(
        id=evidence_id,
        case_id=case_id,
        evidence_type=evidence_type,
        source=source,
        value=value,
        observed_at=observed_at,
        quality=quality,
        provenance=provenance,
        created_at=created_at
    )
    
    json_data = response.model_dump(mode='json')
    
    # Verify all required fields are present
    required_fields = {
        'id', 'case_id', 'evidence_type', 'source', 'value',
        'observed_at', 'quality', 'provenance', 'created_at'
    }
    assert set(json_data.keys()) == required_fields
    
    # Verify created_at is ISO 8601 string
    assert isinstance(json_data['created_at'], str)
    
    # Verify observed_at is either None or ISO 8601 string
    if observed_at is not None:
        assert isinstance(json_data['observed_at'], str)
    
    # Verify provenance is a dict
    assert isinstance(json_data['provenance'], dict)


# Feature: edna-backend-foundation, Property 26: JSON response structure consistency
# Validates: Requirements 18.2, 18.5
@given(
    site_id=uuid_strategy,
    case_id=st.one_of(st.none(), uuid_strategy),
    label=st.text(min_size=1, max_size=50),
    latitude=latitude_strategy,
    longitude=longitude_strategy,
    hyriv_id=hyriv_id_strategy,
    site_type=site_type_strategy,
    validation_status=validation_status_strategy,
    network_latitude=st.one_of(st.none(), latitude_strategy),
    network_longitude=st.one_of(st.none(), longitude_strategy),
    snap_distance_m=st.one_of(st.none(), st.floats(min_value=0, max_value=10000)),
    role=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    metadata=st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.text(max_size=50),
        max_size=3
    )
)
@settings(max_examples=100)
def test_sampling_site_response_structure_consistency(
    site_id, case_id, label, latitude, longitude, hyriv_id,
    site_type, validation_status, network_latitude, network_longitude,
    snap_distance_m, role, metadata
):
    """
    Property: For any SamplingSiteResponse with valid data, the JSON representation
    should include all required fields with proper types.
    
    Feature: edna-backend-foundation, Property 26: JSON response structure consistency
    Validates: Requirements 18.2, 18.5
    """
    response = SamplingSiteResponse(
        id=site_id,
        case_id=case_id,
        label=label,
        latitude=latitude,
        longitude=longitude,
        hyriv_id=hyriv_id,
        site_type=site_type,
        validation_status=validation_status,
        network_latitude=network_latitude,
        network_longitude=network_longitude,
        snap_distance_m=snap_distance_m,
        role=role,
        metadata=metadata
    )
    
    json_data = response.model_dump(mode='json')
    
    # Verify all required fields are present
    required_fields = {
        'id', 'case_id', 'label', 'latitude', 'longitude', 'hyriv_id',
        'site_type', 'validation_status', 'network_latitude', 'network_longitude',
        'snap_distance_m', 'role', 'metadata'
    }
    assert set(json_data.keys()) == required_fields
    
    # Verify enum values are strings
    assert isinstance(json_data['site_type'], str)
    assert isinstance(json_data['validation_status'], str)
    
    # Verify metadata is a dict
    assert isinstance(json_data['metadata'], dict)


# Feature: edna-backend-foundation, Property 26: JSON response structure consistency
# Validates: Requirements 18.2, 18.5
@given(
    hyriv_id=hyriv_id_strategy,
    next_down=st.one_of(st.none(), hyriv_id_strategy),
    length_km=st.floats(min_value=0.01, max_value=1000),
    upland_skm=st.floats(min_value=0.01, max_value=100000),
    dis_av_cms=st.floats(min_value=0.01, max_value=10000)
)
@settings(max_examples=100)
def test_reach_response_structure_consistency(
    hyriv_id, next_down, length_km, upland_skm, dis_av_cms
):
    """
    Property: For any ReachResponse with valid data, the JSON representation
    should include all required fields with proper numeric types.
    
    Feature: edna-backend-foundation, Property 26: JSON response structure consistency
    Validates: Requirements 18.2, 18.5
    """
    response = ReachResponse(
        hyriv_id=hyriv_id,
        next_down=next_down,
        length_km=length_km,
        upland_skm=upland_skm,
        dis_av_cms=dis_av_cms
    )
    
    json_data = response.model_dump(mode='json')
    
    # Verify all required fields are present
    required_fields = {
        'hyriv_id', 'next_down', 'length_km', 'upland_skm', 'dis_av_cms'
    }
    assert set(json_data.keys()) == required_fields
    
    # Verify numeric fields maintain type
    assert isinstance(json_data['hyriv_id'], int)
    assert isinstance(json_data['length_km'], (int, float))
    assert isinstance(json_data['upland_skm'], (int, float))
    assert isinstance(json_data['dis_av_cms'], (int, float))


# Feature: edna-backend-foundation, Property 26: JSON response structure consistency
# Validates: Requirements 18.2, 18.5
@given(
    decision_id=uuid_strategy,
    case_id=uuid_strategy,
    status=sampling_decision_status_strategy,
    recommended_site_ids=st.lists(uuid_strategy, max_size=5),
    rationale=st.text(min_size=1, max_size=200),
    created_at=datetime_strategy
)
@settings(max_examples=100)
def test_sampling_decision_response_structure_consistency(
    decision_id, case_id, status, recommended_site_ids, rationale, created_at
):
    """
    Property: For any SamplingDecisionResponse with valid data, the JSON
    representation should include all required fields with proper types.
    
    Feature: edna-backend-foundation, Property 26: JSON response structure consistency
    Validates: Requirements 18.2, 18.5
    """
    response = SamplingDecisionResponse(
        id=decision_id,
        case_id=case_id,
        status=status,
        recommended_site_ids=recommended_site_ids,
        rationale=rationale,
        created_at=created_at
    )
    
    json_data = response.model_dump(mode='json')
    
    # Verify all required fields are present
    required_fields = {
        'id', 'case_id', 'status', 'recommended_site_ids', 'rationale', 'created_at'
    }
    assert set(json_data.keys()) == required_fields
    
    # Verify timestamp is ISO 8601 string
    assert isinstance(json_data['created_at'], str)
    
    # Verify status is a string (enum)
    assert isinstance(json_data['status'], str)
    
    # Verify recommended_site_ids is a list
    assert isinstance(json_data['recommended_site_ids'], list)


# Feature: edna-backend-foundation, Property 26: JSON response structure consistency
# Validates: Requirements 18.2, 18.5
@given(
    zone_id=uuid_strategy,
    zone_label=st.text(min_size=1, max_size=20),
    assessments=st.lists(
        st.builds(
            EvidenceAssessmentResponse,
            evidence_id=uuid_strategy,
            compatibility=evidence_compatibility_strategy,
            rule_id=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
            reason=st.text(min_size=1, max_size=100),
            provenance=st.just({})
        ),
        max_size=10
    )
)
@settings(max_examples=100)
def test_assessment_summary_response_structure_consistency(
    zone_id, zone_label, assessments
):
    """
    Property: For any AssessmentSummaryResponse with valid data, the JSON
    representation should include all required fields and the summary should
    contain counts for all compatibility statuses.
    
    Feature: edna-backend-foundation, Property 26: JSON response structure consistency
    Validates: Requirements 18.2, 18.5
    """
    # Build summary counts
    summary = {
        "supports": sum(1 for a in assessments if a.compatibility == EvidenceCompatibility.SUPPORTS),
        "contradicts": sum(1 for a in assessments if a.compatibility == EvidenceCompatibility.CONTRADICTS),
        "neutral": sum(1 for a in assessments if a.compatibility == EvidenceCompatibility.NEUTRAL),
        "unknown": sum(1 for a in assessments if a.compatibility == EvidenceCompatibility.UNKNOWN),
    }
    
    response = AssessmentSummaryResponse(
        zone_id=zone_id,
        zone_label=zone_label,
        assessments=assessments,
        summary=summary
    )
    
    json_data = response.model_dump(mode='json')
    
    # Verify all required fields are present
    required_fields = {'zone_id', 'zone_label', 'assessments', 'summary'}
    assert set(json_data.keys()) == required_fields
    
    # Verify summary contains all required keys
    summary_keys = {'supports', 'contradicts', 'neutral', 'unknown'}
    assert set(json_data['summary'].keys()) == summary_keys, (
        f"Summary missing required keys. Expected {summary_keys}, "
        f"got {set(json_data['summary'].keys())}"
    )
    
    # Verify assessments is a list
    assert isinstance(json_data['assessments'], list)
    
    # Verify each assessment has required structure
    for assessment in json_data['assessments']:
        assert 'evidence_id' in assessment
        assert 'compatibility' in assessment
        assert 'reason' in assessment
        assert 'provenance' in assessment
