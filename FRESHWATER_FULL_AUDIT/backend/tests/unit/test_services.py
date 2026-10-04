"""
Unit tests for service layer.

Tests service orchestration with mocked repositories and engines.
Focuses on validation logic and error handling.
"""
from datetime import datetime
from unittest.mock import Mock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.case_service import CaseService
from app.services.evidence_service import EvidenceService
from app.services.hydrology_service import HydrologyService
from app.services.sampling_service import SamplingService
from app.repositories.cases import CaseNotFoundError
from app.domain.models import (
    Case,
    EvidenceItem,
    EvidenceAssessment,
    RiverReach,
    SamplingSite,
    CandidateZone,
)
from app.domain.enums import (
    CaseStatus,
    EvidenceCompatibility,
    SiteType,
    ValidationStatus,
    SamplingDecisionStatus,
)


class TestCaseService:
    """Test suite for CaseService."""
    
    def test_create_case_validates_empty_taxon(self):
        """Test that create_case rejects empty target_taxon."""
        mock_repo = Mock()
        service = CaseService(mock_repo)
        
        with pytest.raises(HTTPException) as exc_info:
            service.create_case(
                target_taxon="",
                observation_date=datetime(2024, 1, 1),
                detection_site_id=uuid4()
            )
        
        assert exc_info.value.status_code == 400
        assert "target_taxon" in str(exc_info.value.detail)
    
    def test_create_case_validates_missing_detection_site(self):
        """Test that create_case rejects missing detection_site_id."""
        mock_repo = Mock()
        service = CaseService(mock_repo)
        
        with pytest.raises(HTTPException) as exc_info:
            service.create_case(
                target_taxon="Test Species",
                observation_date=datetime(2024, 1, 1),
                detection_site_id=None
            )
        
        assert exc_info.value.status_code == 400
        assert "detection_site_id" in str(exc_info.value.detail)
    
    def test_create_case_handles_repository_error(self):
        """Test that create_case converts repository ValueError to 404."""
        mock_repo = Mock()
        mock_repo.create_case.side_effect = ValueError("Detection site with ID xyz not found")
        
        service = CaseService(mock_repo)
        
        with pytest.raises(HTTPException) as exc_info:
            service.create_case(
                target_taxon="Test Species",
                observation_date=datetime(2024, 1, 1),
                detection_site_id=uuid4()
            )
        
        assert exc_info.value.status_code == 404
    
    def test_get_case_handles_not_found(self):
        """Test that get_case converts CaseNotFoundError to HTTPException."""
        mock_repo = Mock()
        case_id = uuid4()
        mock_repo.get_case_by_id.side_effect = CaseNotFoundError(case_id)
        
        service = CaseService(mock_repo)
        
        with pytest.raises(HTTPException) as exc_info:
            service.get_case(case_id)
        
        assert exc_info.value.status_code == 404
        assert str(case_id) in str(exc_info.value.detail)
    
    def test_list_cases_delegates_to_repository(self):
        """Test that list_cases delegates to repository with correct parameters."""
        mock_repo = Mock()
        mock_repo.list_cases.return_value = []
        
        service = CaseService(mock_repo)
        
        result = service.list_cases(
            status=CaseStatus.ACTIVE,
            target_taxon="Test Species",
            limit=10,
            offset=5
        )
        
        mock_repo.list_cases.assert_called_once_with(
            status=CaseStatus.ACTIVE,
            target_taxon="Test Species",
            limit=10,
            offset=5
        )
        assert result == []
    
    def test_update_case_status_handles_not_found(self):
        """Test that update_case_status converts CaseNotFoundError to HTTPException."""
        mock_repo = Mock()
        case_id = uuid4()
        mock_repo.update_case.side_effect = CaseNotFoundError(case_id)
        
        service = CaseService(mock_repo)
        
        with pytest.raises(HTTPException) as exc_info:
            service.update_case_status(case_id, CaseStatus.COMPLETED)
        
        assert exc_info.value.status_code == 404


class TestEvidenceService:
    """Test suite for EvidenceService."""
    
    def test_add_evidence_validates_empty_type(self):
        """Test that add_evidence rejects empty evidence_type."""
        mock_repo = Mock()
        mock_engine = Mock()
        service = EvidenceService(mock_repo, mock_engine)
        
        with pytest.raises(HTTPException) as exc_info:
            service.add_evidence(
                case_id=uuid4(),
                evidence_type="",
                source="test source",
                value="test value"
            )
        
        assert exc_info.value.status_code == 400
        assert "evidence_type" in str(exc_info.value.detail)
    
    def test_add_evidence_validates_empty_source(self):
        """Test that add_evidence rejects empty source."""
        mock_repo = Mock()
        mock_engine = Mock()
        service = EvidenceService(mock_repo, mock_engine)
        
        with pytest.raises(HTTPException) as exc_info:
            service.add_evidence(
                case_id=uuid4(),
                evidence_type="test type",
                source="",
                value="test value"
            )
        
        assert exc_info.value.status_code == 400
        assert "source" in str(exc_info.value.detail)
    
    def test_add_evidence_validates_none_value(self):
        """Test that add_evidence rejects None value."""
        mock_repo = Mock()
        mock_engine = Mock()
        service = EvidenceService(mock_repo, mock_engine)
        
        with pytest.raises(HTTPException) as exc_info:
            service.add_evidence(
                case_id=uuid4(),
                evidence_type="test type",
                source="test source",
                value=None
            )
        
        assert exc_info.value.status_code == 400
        assert "value" in str(exc_info.value.detail)
    
    def test_get_evidence_for_case_delegates_to_repository(self):
        """Test that get_evidence_for_case delegates to repository."""
        mock_repo = Mock()
        mock_engine = Mock()
        case_id = uuid4()
        mock_repo.get_evidence_by_case.return_value = []
        
        service = EvidenceService(mock_repo, mock_engine)
        result = service.get_evidence_for_case(case_id)
        
        mock_repo.get_evidence_by_case.assert_called_once_with(case_id)
        assert result == []
    
    def test_assess_evidence_for_zones_coordinates_engine(self):
        """Test that assess_evidence_for_zones coordinates repository and engine."""
        mock_repo = Mock()
        mock_engine = Mock()
        
        case = Mock(id=uuid4())
        zone1 = Mock(label="Z1", id=uuid4())
        zone2 = Mock(label="Z2", id=uuid4())
        
        evidence = [Mock(spec=EvidenceItem)]
        assessments = [Mock(spec=EvidenceAssessment)]
        
        mock_repo.get_evidence_by_case.return_value = evidence
        mock_engine.assess_evidence_for_zone.return_value = assessments
        mock_engine.summarize_zone_assessment.return_value = {
            "supports": 1,
            "contradicts": 0,
            "neutral": 0,
            "unknown": 0
        }
        
        service = EvidenceService(mock_repo, mock_engine)
        result = service.assess_evidence_for_zones(case, [zone1, zone2])
        
        # Verify repository was called
        mock_repo.get_evidence_by_case.assert_called_once_with(case.id)
        
        # Verify engine was called for each zone
        assert mock_engine.assess_evidence_for_zone.call_count == 2
        assert mock_engine.summarize_zone_assessment.call_count == 2
        
        # Verify result structure
        assert "Z1" in result
        assert "Z2" in result
        assert result["Z1"]["zone_id"] == zone1.id
        assert result["Z1"]["assessments"] == assessments


class TestHydrologyService:
    """Test suite for HydrologyService."""
    
    def test_query_upstream_reaches_handles_invalid_hyriv_id(self):
        """Test that query_upstream_reaches converts ValueError to 404."""
        mock_engine = Mock()
        mock_engine.get_upstream_reaches.side_effect = ValueError("HYRIV_ID not found")
        
        service = HydrologyService(mock_engine)
        
        with pytest.raises(HTTPException) as exc_info:
            service.query_upstream_reaches(99999)
        
        assert exc_info.value.status_code == 404
        assert "99999" in str(exc_info.value.detail)
    
    def test_query_downstream_path_distinguishes_errors(self):
        """Test that query_downstream_path distinguishes not found from invalid path."""
        mock_engine = Mock()
        service = HydrologyService(mock_engine)
        
        # Test not found error
        mock_engine.get_downstream_path.side_effect = ValueError("HYRIV_ID 123 not found")
        
        with pytest.raises(HTTPException) as exc_info:
            service.query_downstream_path(123, 456)
        
        assert exc_info.value.status_code == 404
        
        # Test invalid path error
        mock_engine.get_downstream_path.side_effect = ValueError("456 is not downstream of 123")
        
        with pytest.raises(HTTPException) as exc_info:
            service.query_downstream_path(123, 456)
        
        assert exc_info.value.status_code == 400
    
    def test_calculate_network_distance_handles_none_result(self):
        """Test that calculate_network_distance raises 400 when distance is None."""
        mock_engine = Mock()
        mock_engine.network_distance_km.return_value = None
        
        service = HydrologyService(mock_engine)
        
        with pytest.raises(HTTPException) as exc_info:
            service.calculate_network_distance(123, 456)
        
        assert exc_info.value.status_code == 400
        assert "not upstream" in str(exc_info.value.detail)
    
    def test_get_reach_handles_invalid_hyriv_id(self):
        """Test that get_reach converts ValueError to 404."""
        mock_engine = Mock()
        mock_engine.get_reach.side_effect = ValueError("HYRIV_ID not found")
        
        service = HydrologyService(mock_engine)
        
        with pytest.raises(HTTPException) as exc_info:
            service.get_reach(99999)
        
        assert exc_info.value.status_code == 404


class TestSamplingService:
    """Test suite for SamplingService."""
    
    def test_register_sampling_site_validates_empty_label(self):
        """Test that register_sampling_site rejects empty label."""
        mock_repo = Mock()
        mock_sampling_engine = Mock()
        mock_hydrology_engine = Mock()
        
        service = SamplingService(mock_repo, mock_sampling_engine, mock_hydrology_engine)
        
        with pytest.raises(HTTPException) as exc_info:
            service.register_sampling_site(
                label="",
                latitude=47.0,
                longitude=8.0,
                hyriv_id=123,
                site_type=SiteType.BRANCH_SPECIFIC,
                validation_status=ValidationStatus.VERIFIED
            )
        
        assert exc_info.value.status_code == 400
        assert "label" in str(exc_info.value.detail)
    
    def test_register_sampling_site_validates_hyriv_id(self):
        """Test that register_sampling_site validates HYRIV_ID exists."""
        mock_repo = Mock()
        mock_sampling_engine = Mock()
        mock_hydrology_engine = Mock()
        mock_hydrology_engine.get_reach.side_effect = ValueError("HYRIV_ID not found")
        
        service = SamplingService(mock_repo, mock_sampling_engine, mock_hydrology_engine)
        
        with pytest.raises(HTTPException) as exc_info:
            service.register_sampling_site(
                label="Site B",
                latitude=47.0,
                longitude=8.0,
                hyriv_id=99999,
                site_type=SiteType.BRANCH_SPECIFIC,
                validation_status=ValidationStatus.VERIFIED
            )
        
        assert exc_info.value.status_code == 404
        assert "99999" in str(exc_info.value.detail)
    
    def test_get_sampling_sites_delegates_to_repository(self):
        """Test that get_sampling_sites delegates to repository."""
        mock_repo = Mock()
        mock_sampling_engine = Mock()
        mock_hydrology_engine = Mock()
        case_id = uuid4()
        mock_repo.get_sites_by_case.return_value = []
        
        service = SamplingService(mock_repo, mock_sampling_engine, mock_hydrology_engine)
        result = service.get_sampling_sites(case_id)
        
        mock_repo.get_sites_by_case.assert_called_once_with(case_id)
        assert result == []
    
    def test_evaluate_sampling_candidates_validates_empty_zones(self):
        """Test that evaluate_sampling_candidates rejects empty zones list."""
        mock_repo = Mock()
        mock_sampling_engine = Mock()
        mock_hydrology_engine = Mock()
        
        service = SamplingService(mock_repo, mock_sampling_engine, mock_hydrology_engine)
        
        case = Mock()
        candidate_sites = [Mock()]
        
        with pytest.raises(HTTPException) as exc_info:
            service.evaluate_sampling_candidates(case, [], candidate_sites)
        
        assert exc_info.value.status_code == 400
        assert "zone" in str(exc_info.value.detail).lower()
    
    def test_evaluate_sampling_candidates_validates_empty_sites(self):
        """Test that evaluate_sampling_candidates rejects empty sites list."""
        mock_repo = Mock()
        mock_sampling_engine = Mock()
        mock_hydrology_engine = Mock()
        
        service = SamplingService(mock_repo, mock_sampling_engine, mock_hydrology_engine)
        
        case = Mock()
        zones = [Mock()]
        
        with pytest.raises(HTTPException) as exc_info:
            service.evaluate_sampling_candidates(case, zones, [])
        
        assert exc_info.value.status_code == 400
        assert "site" in str(exc_info.value.detail).lower()
    
    def test_evaluate_sampling_candidates_coordinates_engines(self):
        """Test that evaluate_sampling_candidates coordinates engines and repository."""
        mock_repo = Mock()
        mock_sampling_engine = Mock()
        mock_hydrology_engine = Mock()
        
        case = Mock(id=uuid4())
        zones = [Mock(spec=CandidateZone)]
        sites = [Mock(spec=SamplingSite, id=uuid4())]
        
        evaluations = [{"site_id": sites[0].id, "score": 0.8}]
        decision_mock = Mock(id=uuid4())
        trace_mock = Mock()
        
        mock_sampling_engine.evaluate_candidates.return_value = evaluations
        mock_sampling_engine.make_recommendation.return_value = (
            SamplingDecisionStatus.RECOMMEND,
            [sites[0].id],
            "Test rationale"
        )
        mock_sampling_engine.create_decision_trace.return_value = trace_mock
        mock_repo.save_decision.return_value = (decision_mock, trace_mock)
        
        service = SamplingService(mock_repo, mock_sampling_engine, mock_hydrology_engine)
        decision, trace = service.evaluate_sampling_candidates(case, zones, sites)
        
        # Verify engine was called
        mock_sampling_engine.evaluate_candidates.assert_called_once()
        mock_sampling_engine.make_recommendation.assert_called_once_with(evaluations)
        mock_sampling_engine.create_decision_trace.assert_called_once()
        
        # Verify repository was called
        mock_repo.save_decision.assert_called_once()
        
        assert decision == decision_mock
