"""
Sampling repository for data access operations.

Hides SQLAlchemy details and returns domain models.
"""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    SamplingSiteModel,
    CandidateZoneModel,
    SamplingDecisionModel,
    DecisionTraceModel,
    CaseModel,
)
from app.domain.models import (
    SamplingSite,
    CandidateZone,
    SamplingDecision,
    DecisionTrace,
)
from app.domain.enums import (
    SiteType,
    ValidationStatus,
    SamplingDecisionStatus,
)


class SiteNotFoundError(Exception):
    """Raised when a sampling site is not found in the database."""
    def __init__(self, site_id: UUID):
        self.site_id = site_id
        super().__init__(f"Sampling site with ID {site_id} not found")


class ZoneNotFoundError(Exception):
    """Raised when a candidate zone is not found in the database."""
    def __init__(self, zone_id: UUID):
        self.zone_id = zone_id
        super().__init__(f"Candidate zone with ID {zone_id} not found")


class DecisionNotFoundError(Exception):
    """Raised when a sampling decision is not found in the database."""
    def __init__(self, decision_id: UUID):
        self.decision_id = decision_id
        super().__init__(f"Sampling decision with ID {decision_id} not found")


class SamplingRepository:
    """
    Repository for Sampling-related data access operations.
    
    Handles CRUD operations for sampling sites, candidate zones, and
    sampling decisions. Hides SQLAlchemy details from the service layer.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the repository with a database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def create_site(
        self,
        label: str,
        latitude: float,
        longitude: float,
        hyriv_id: int,
        site_type: SiteType,
        validation_status: ValidationStatus,
        case_id: Optional[UUID] = None,
        network_latitude: Optional[float] = None,
        network_longitude: Optional[float] = None,
        snap_distance_m: Optional[float] = None,
        role: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> SamplingSite:
        """
        Create a new sampling site and persist to database.
        
        Args:
            label: Human-readable site label (e.g., "Site A")
            latitude: Observation latitude in decimal degrees
            longitude: Observation longitude in decimal degrees
            hyriv_id: HydroRIVERS reach ID
            site_type: Type of sampling site
            validation_status: Validation status of network match
            case_id: UUID of associated case (optional, for shared sites)
            network_latitude: Snapped network latitude (optional)
            network_longitude: Snapped network longitude (optional)
            snap_distance_m: Distance from observation to network in meters (optional)
            role: Functional role in sampling strategy (optional)
            metadata: Additional site-specific metadata (optional)
            
        Returns:
            SamplingSite: Created site as domain model
            
        Raises:
            ValueError: If case_id is provided but does not exist
        """
        # Verify case exists if provided
        if case_id is not None:
            case = self.db.get(CaseModel, case_id)
            if not case:
                raise ValueError(f"Case with ID {case_id} not found")
        
        # Create database model
        db_site = SamplingSiteModel(
            case_id=case_id,
            label=label,
            latitude=latitude,
            longitude=longitude,
            hyriv_id=hyriv_id,
            site_type=site_type.value,
            validation_status=validation_status.value,
            network_latitude=network_latitude,
            network_longitude=network_longitude,
            snap_distance_m=snap_distance_m,
            role=role,
            meta=metadata or {}
        )
        
        # Persist to database
        self.db.add(db_site)
        self.db.commit()
        self.db.refresh(db_site)
        
        # Convert to domain model
        return self._site_to_domain(db_site)
    
    def get_sites_by_case(self, case_id: UUID) -> list[SamplingSite]:
        """
        Retrieve all sampling sites for a case.
        
        Args:
            case_id: UUID of the case
            
        Returns:
            list[SamplingSite]: List of sampling sites as domain models
        """
        # Build query
        query = select(SamplingSiteModel).where(
            SamplingSiteModel.case_id == case_id
        )
        
        # Order by label (alphabetical)
        query = query.order_by(SamplingSiteModel.label.asc())
        
        # Execute query
        result = self.db.execute(query)
        db_sites = result.scalars().all()
        
        # Convert to domain models
        return [self._site_to_domain(db_site) for db_site in db_sites]

    def get_site_by_id(self, site_id: UUID) -> SamplingSite:
        """Retrieve one sampling site or raise SiteNotFoundError."""
        db_site = self.db.get(SamplingSiteModel, site_id)
        if db_site is None:
            raise SiteNotFoundError(site_id)
        return self._site_to_domain(db_site)
    
    def create_zone(
        self,
        case_id: UUID,
        label: str,
        root_hyriv_id: int,
        reach_ids: list[int],
        validation_status: ValidationStatus,
        metadata: Optional[dict] = None
    ) -> CandidateZone:
        """
        Create a new candidate zone and persist to database.
        
        Args:
            case_id: UUID of the associated case
            label: Human-readable zone label (e.g., "Z1")
            root_hyriv_id: HYRIV_ID of the zone root reach
            reach_ids: List of HYRIV_IDs comprising the zone
            validation_status: Validation status of zone definition
            metadata: Additional zone-specific metadata (optional)
            
        Returns:
            CandidateZone: Created zone as domain model
            
        Raises:
            ValueError: If case_id does not exist
        """
        # Verify case exists
        case = self.db.get(CaseModel, case_id)
        if not case:
            raise ValueError(f"Case with ID {case_id} not found")
        
        # Create database model
        db_zone = CandidateZoneModel(
            case_id=case_id,
            label=label,
            root_hyriv_id=root_hyriv_id,
            reach_ids=reach_ids,
            validation_status=validation_status.value,
            meta=metadata or {}
        )
        
        # Persist to database
        self.db.add(db_zone)
        self.db.commit()
        self.db.refresh(db_zone)
        
        # Convert to domain model
        return self._zone_to_domain(db_zone)
    
    def get_zones_by_case(self, case_id: UUID) -> list[CandidateZone]:
        """
        Retrieve all candidate zones for a case.
        
        Args:
            case_id: UUID of the case
            
        Returns:
            list[CandidateZone]: List of candidate zones as domain models
        """
        # Build query
        query = select(CandidateZoneModel).where(
            CandidateZoneModel.case_id == case_id
        )
        
        # Order by label (alphabetical)
        query = query.order_by(CandidateZoneModel.label.asc())
        
        # Execute query
        result = self.db.execute(query)
        db_zones = result.scalars().all()
        
        # Convert to domain models
        return [self._zone_to_domain(db_zone) for db_zone in db_zones]
    
    def save_decision(
        self,
        case_id: UUID,
        status: SamplingDecisionStatus,
        recommended_site_ids: list[UUID],
        rationale: str,
        evidence_used: list[UUID],
        rules_applied: list[str],
        hydrology_checks: list[dict[str, Any]],
        assumptions: list[str],
        limitations: list[str]
    ) -> tuple[SamplingDecision, DecisionTrace]:
        """
        Save a sampling decision with its decision trace to database.
        
        This method persists both the decision and its audit trail in a single
        transaction to ensure consistency.
        
        Args:
            case_id: UUID of the associated case
            status: Decision status
            recommended_site_ids: List of recommended site UUIDs
            rationale: Explanation for the decision
            evidence_used: List of evidence item UUIDs used in decision
            rules_applied: List of scientific rule IDs applied
            hydrology_checks: List of hydrology operations performed
            assumptions: List of assumptions made
            limitations: List of known limitations
            
        Returns:
            tuple[SamplingDecision, DecisionTrace]: Created decision and trace as domain models
            
        Raises:
            ValueError: If case_id does not exist
        """
        # Verify case exists
        case = self.db.get(CaseModel, case_id)
        if not case:
            raise ValueError(f"Case with ID {case_id} not found")
        
        # Create decision model
        db_decision = SamplingDecisionModel(
            case_id=case_id,
            status=status.value,
            recommended_site_ids=recommended_site_ids,
            rationale=rationale
        )
        
        # Persist decision
        self.db.add(db_decision)
        self.db.flush()  # Flush to get the decision ID without committing
        
        # Create trace model
        db_trace = DecisionTraceModel(
            decision_id=db_decision.id,
            evidence_used=evidence_used,
            rules_applied=rules_applied,
            hydrology_checks=hydrology_checks,
            assumptions=assumptions,
            limitations=limitations
        )
        
        # Persist trace
        self.db.add(db_trace)
        
        # Commit transaction
        self.db.commit()
        self.db.refresh(db_decision)
        self.db.refresh(db_trace)
        
        # Convert to domain models
        decision_domain = self._decision_to_domain(db_decision)
        trace_domain = self._trace_to_domain(db_trace)
        
        return decision_domain, trace_domain
    
    def _site_to_domain(self, db_site: SamplingSiteModel) -> SamplingSite:
        """
        Convert SQLAlchemy site model to domain model.
        
        Args:
            db_site: SQLAlchemy site model
            
        Returns:
            SamplingSite: Domain model
        """
        return SamplingSite(
            id=db_site.id,
            case_id=db_site.case_id,
            label=db_site.label,
            latitude=db_site.latitude,
            longitude=db_site.longitude,
            hyriv_id=db_site.hyriv_id,
            site_type=SiteType(db_site.site_type),
            validation_status=ValidationStatus(db_site.validation_status),
            network_latitude=db_site.network_latitude,
            network_longitude=db_site.network_longitude,
            snap_distance_m=db_site.snap_distance_m,
            role=db_site.role,
            metadata=db_site.meta
        )
    
    def _zone_to_domain(self, db_zone: CandidateZoneModel) -> CandidateZone:
        """
        Convert SQLAlchemy zone model to domain model.
        
        Args:
            db_zone: SQLAlchemy zone model
            
        Returns:
            CandidateZone: Domain model
        """
        return CandidateZone(
            id=db_zone.id,
            case_id=db_zone.case_id,
            label=db_zone.label,
            root_hyriv_id=db_zone.root_hyriv_id,
            reach_ids=db_zone.reach_ids,
            validation_status=ValidationStatus(db_zone.validation_status),
            metadata=db_zone.meta
        )
    
    def _decision_to_domain(self, db_decision: SamplingDecisionModel) -> SamplingDecision:
        """
        Convert SQLAlchemy decision model to domain model.
        
        Args:
            db_decision: SQLAlchemy decision model
            
        Returns:
            SamplingDecision: Domain model
        """
        return SamplingDecision(
            id=db_decision.id,
            case_id=db_decision.case_id,
            status=SamplingDecisionStatus(db_decision.status),
            recommended_site_ids=db_decision.recommended_site_ids,
            rationale=db_decision.rationale,
            created_at=db_decision.created_at
        )
    
    def get_decision_by_id(self, decision_id: UUID) -> SamplingDecision:
        """
        Retrieve a sampling decision by its ID.
        
        Args:
            decision_id: UUID of the sampling decision
            
        Returns:
            SamplingDecision: The decision as domain model
            
        Raises:
            DecisionNotFoundError: If decision not found
        """
        db_decision = self.db.get(SamplingDecisionModel, decision_id)
        if not db_decision:
            raise DecisionNotFoundError(decision_id)
        
        return self._decision_to_domain(db_decision)
    
    def get_trace_by_decision_id(self, decision_id: UUID) -> DecisionTrace:
        """
        Retrieve the decision trace for a sampling decision.
        
        Args:
            decision_id: UUID of the sampling decision
            
        Returns:
            DecisionTrace: The decision trace as domain model
            
        Raises:
            DecisionNotFoundError: If trace not found
        """
        # Query for trace by decision_id
        query = select(DecisionTraceModel).where(
            DecisionTraceModel.decision_id == decision_id
        )
        
        result = self.db.execute(query)
        db_trace = result.scalar_one_or_none()
        
        if not db_trace:
            raise DecisionNotFoundError(decision_id)
        
        return self._trace_to_domain(db_trace)
    
    def _site_to_domain(self, db_site: SamplingSiteModel) -> SamplingSite:
        """
        Convert SQLAlchemy site model to domain model.
        
        Args:
            db_site: SQLAlchemy site model
            
        Returns:
            SamplingSite: Domain model
        """
        return SamplingSite(
            id=db_site.id,
            case_id=db_site.case_id,
            label=db_site.label,
            latitude=db_site.latitude,
            longitude=db_site.longitude,
            hyriv_id=db_site.hyriv_id,
            site_type=SiteType(db_site.site_type),
            validation_status=ValidationStatus(db_site.validation_status),
            network_latitude=db_site.network_latitude,
            network_longitude=db_site.network_longitude,
            snap_distance_m=db_site.snap_distance_m,
            role=db_site.role,
            metadata=db_site.meta
        )
    
    def _zone_to_domain(self, db_zone: CandidateZoneModel) -> CandidateZone:
        """
        Convert SQLAlchemy zone model to domain model.
        
        Args:
            db_zone: SQLAlchemy zone model
            
        Returns:
            CandidateZone: Domain model
        """
        return CandidateZone(
            id=db_zone.id,
            case_id=db_zone.case_id,
            label=db_zone.label,
            root_hyriv_id=db_zone.root_hyriv_id,
            reach_ids=db_zone.reach_ids,
            validation_status=ValidationStatus(db_zone.validation_status),
            metadata=db_zone.meta
        )
    
    def _decision_to_domain(self, db_decision: SamplingDecisionModel) -> SamplingDecision:
        """
        Convert SQLAlchemy decision model to domain model.
        
        Args:
            db_decision: SQLAlchemy decision model
            
        Returns:
            SamplingDecision: Domain model
        """
        return SamplingDecision(
            id=db_decision.id,
            case_id=db_decision.case_id,
            status=SamplingDecisionStatus(db_decision.status),
            recommended_site_ids=db_decision.recommended_site_ids,
            rationale=db_decision.rationale,
            created_at=db_decision.created_at
        )
    
    def _trace_to_domain(self, db_trace: DecisionTraceModel) -> DecisionTrace:
        """
        Convert SQLAlchemy trace model to domain model.
        
        Args:
            db_trace: SQLAlchemy trace model
            
        Returns:
            DecisionTrace: Domain model
        """
        return DecisionTrace(
            decision_id=db_trace.decision_id,
            evidence_used=db_trace.evidence_used,
            rules_applied=db_trace.rules_applied,
            hydrology_checks=db_trace.hydrology_checks,
            assumptions=db_trace.assumptions,
            limitations=db_trace.limitations,
            created_at=db_trace.created_at
        )
