"""
Unit tests for SamplingRepository.

Tests the basic CRUD operations and domain model conversions.
"""
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import CaseModel, SamplingSiteModel
from app.repositories.sampling import (
    SamplingRepository,
    SiteNotFoundError,
    ZoneNotFoundError,
)
from app.domain.enums import (
    SiteType,
    ValidationStatus,
    SamplingDecisionStatus,
    CaseStatus,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_case(db_session):
    """Create a test case with a detection site."""
    # Create detection site first
    detection_site = SamplingSiteModel(
        label="Site A",
        latitude=47.0,
        longitude=8.0,
        hyriv_id=20449905,
        site_type=SiteType.DETECTION_SITE.value,
        validation_status=ValidationStatus.VERIFIED.value,
        meta={}
    )
    db_session.add(detection_site)
    db_session.flush()
    
    # Create case
    case = CaseModel(
        target_taxon="Test Species",
        observation_date=datetime(2024, 1, 1),
        detection_site_id=detection_site.id,
        status=CaseStatus.ACTIVE.value,
        meta={}
    )
    db_session.add(case)
    db_session.commit()
    
    return case


class TestSamplingRepository:
    """Test suite for SamplingRepository."""
    
    def test_create_site_persists_to_database(self, db_session, test_case):
        """Test that create_site persists a sampling site to the database."""
        repo = SamplingRepository(db_session)
        
        # Create a site
        site = repo.create_site(
            label="Site B",
            latitude=47.1,
            longitude=8.1,
            hyriv_id=20450127,
            site_type=SiteType.BRANCH_SPECIFIC,
            validation_status=ValidationStatus.VERIFIED,
            case_id=test_case.id,
            metadata={"test": "value"}
        )
        
        # Verify site was created
        assert site.id is not None
        assert site.label == "Site B"
        assert site.latitude == 47.1
        assert site.longitude == 8.1
        assert site.hyriv_id == 20450127
        assert site.site_type == SiteType.BRANCH_SPECIFIC
        assert site.validation_status == ValidationStatus.VERIFIED
        assert site.case_id == test_case.id
        assert site.metadata == {"test": "value"}
    
    def test_get_sites_by_case_returns_all_sites(self, db_session, test_case):
        """Test that get_sites_by_case returns all sites for a case."""
        repo = SamplingRepository(db_session)
        
        # Create multiple sites
        repo.create_site(
            label="Site B",
            latitude=47.1,
            longitude=8.1,
            hyriv_id=20450127,
            site_type=SiteType.BRANCH_SPECIFIC,
            validation_status=ValidationStatus.VERIFIED,
            case_id=test_case.id
        )
        repo.create_site(
            label="Site C",
            latitude=47.2,
            longitude=8.2,
            hyriv_id=20451169,
            site_type=SiteType.BRANCH_SPECIFIC,
            validation_status=ValidationStatus.VERIFIED,
            case_id=test_case.id
        )
        
        # Retrieve sites
        sites = repo.get_sites_by_case(test_case.id)
        
        # Verify we got both sites (alphabetically ordered)
        assert len(sites) == 2
        assert sites[0].label == "Site B"
        assert sites[1].label == "Site C"
    
    def test_create_zone_persists_to_database(self, db_session, test_case):
        """Test that create_zone persists a candidate zone to the database."""
        repo = SamplingRepository(db_session)
        
        # Create a zone
        zone = repo.create_zone(
            case_id=test_case.id,
            label="Z1",
            root_hyriv_id=20450127,
            reach_ids=[20450127, 20450128, 20450129],
            validation_status=ValidationStatus.VERIFIED,
            metadata={"source": "preflight"}
        )
        
        # Verify zone was created
        assert zone.id is not None
        assert zone.case_id == test_case.id
        assert zone.label == "Z1"
        assert zone.root_hyriv_id == 20450127
        assert zone.reach_ids == [20450127, 20450128, 20450129]
        assert zone.validation_status == ValidationStatus.VERIFIED
        assert zone.metadata == {"source": "preflight"}
    
    def test_get_zones_by_case_returns_all_zones(self, db_session, test_case):
        """Test that get_zones_by_case returns all zones for a case."""
        repo = SamplingRepository(db_session)
        
        # Create multiple zones
        repo.create_zone(
            case_id=test_case.id,
            label="Z1",
            root_hyriv_id=20450127,
            reach_ids=[20450127],
            validation_status=ValidationStatus.VERIFIED
        )
        repo.create_zone(
            case_id=test_case.id,
            label="Z2",
            root_hyriv_id=20450128,
            reach_ids=[20450128],
            validation_status=ValidationStatus.VERIFIED
        )
        
        # Retrieve zones
        zones = repo.get_zones_by_case(test_case.id)
        
        # Verify we got both zones (alphabetically ordered)
        assert len(zones) == 2
        assert zones[0].label == "Z1"
        assert zones[1].label == "Z2"
    
    def test_save_decision_persists_decision_and_trace(self, db_session, test_case):
        """Test that save_decision persists both decision and trace."""
        repo = SamplingRepository(db_session)
        
        # Create some sites to recommend
        site1 = repo.create_site(
            label="Site B",
            latitude=47.1,
            longitude=8.1,
            hyriv_id=20450127,
            site_type=SiteType.BRANCH_SPECIFIC,
            validation_status=ValidationStatus.VERIFIED,
            case_id=test_case.id
        )
        
        # Save a decision
        decision, trace = repo.save_decision(
            case_id=test_case.id,
            status=SamplingDecisionStatus.RECOMMEND,
            recommended_site_ids=[site1.id],
            rationale="Site B provides best discrimination",
            evidence_used=[],
            rules_applied=["rule1", "rule2"],
            hydrology_checks=[{"check": "upstream_connectivity"}],
            assumptions=["assumption1"],
            limitations=["limitation1"]
        )
        
        # Verify decision
        assert decision.id is not None
        assert decision.case_id == test_case.id
        assert decision.status == SamplingDecisionStatus.RECOMMEND
        assert decision.recommended_site_ids == [site1.id]
        assert decision.rationale == "Site B provides best discrimination"
        
        # Verify trace
        assert trace.decision_id == decision.id
        assert trace.evidence_used == []
        assert trace.rules_applied == ["rule1", "rule2"]
        assert trace.hydrology_checks == [{"check": "upstream_connectivity"}]
        assert trace.assumptions == ["assumption1"]
        assert trace.limitations == ["limitation1"]
    
    def test_create_site_with_invalid_case_raises_error(self, db_session):
        """Test that creating a site with invalid case_id raises ValueError."""
        repo = SamplingRepository(db_session)
        
        invalid_case_id = uuid4()
        
        with pytest.raises(ValueError, match=f"Case with ID {invalid_case_id} not found"):
            repo.create_site(
                label="Site B",
                latitude=47.1,
                longitude=8.1,
                hyriv_id=20450127,
                site_type=SiteType.BRANCH_SPECIFIC,
                validation_status=ValidationStatus.VERIFIED,
                case_id=invalid_case_id
            )
    
    def test_create_zone_with_invalid_case_raises_error(self, db_session):
        """Test that creating a zone with invalid case_id raises ValueError."""
        repo = SamplingRepository(db_session)
        
        invalid_case_id = uuid4()
        
        with pytest.raises(ValueError, match=f"Case with ID {invalid_case_id} not found"):
            repo.create_zone(
                case_id=invalid_case_id,
                label="Z1",
                root_hyriv_id=20450127,
                reach_ids=[20450127],
                validation_status=ValidationStatus.VERIFIED
            )
    
    def test_save_decision_with_invalid_case_raises_error(self, db_session):
        """Test that saving a decision with invalid case_id raises ValueError."""
        repo = SamplingRepository(db_session)
        
        invalid_case_id = uuid4()
        
        with pytest.raises(ValueError, match=f"Case with ID {invalid_case_id} not found"):
            repo.save_decision(
                case_id=invalid_case_id,
                status=SamplingDecisionStatus.RECOMMEND,
                recommended_site_ids=[],
                rationale="Test",
                evidence_used=[],
                rules_applied=[],
                hydrology_checks=[],
                assumptions=[],
                limitations=[]
            )
