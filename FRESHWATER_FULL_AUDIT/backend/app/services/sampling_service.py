"""
Sampling service for business logic orchestration.

Coordinates SamplingRepository, SamplingDecisionEngine, and HydrologyEngine
to manage sampling sites and decision-making.
"""
from typing import Optional
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import DecisionTraceModel

from app.repositories.sampling import (
    SamplingRepository,
    SiteNotFoundError,
    DecisionNotFoundError,
)
from app.scientific.interfaces import (
    SamplingDecisionEngine,
    HydrologyEngine,
    CandidateSiteGenerator,
)
from app.domain.models import (
    Case,
    CandidateZone,
    SamplingSite,
    SamplingDecision,
    DecisionTrace,
    CandidateGenerationResult,
)
from app.domain.enums import (
    SiteType,
    ValidationStatus,
)


class SamplingService:
    """
    Service for sampling-related business logic.
    
    Orchestrates sampling operations, coordinates repository and engines,
    and enforces business rules and validation.
    """
    
    def __init__(
        self,
        sampling_repository: SamplingRepository,
        sampling_engine: SamplingDecisionEngine,
        hydrology_engine: HydrologyEngine,
        candidate_generator: CandidateSiteGenerator | None = None,
        site_a_fraction: float = 1.0,
    ):
        """
        Initialize the service with required dependencies.
        
        Args:
            sampling_repository: Repository for sampling data access
            sampling_engine: Engine for sampling decision-making
            hydrology_engine: Engine for river network analysis
        """
        self.sampling_repository = sampling_repository
        self.sampling_engine = sampling_engine
        self.hydrology_engine = hydrology_engine
        self.candidate_generator = candidate_generator
        self.site_a_fraction = site_a_fraction
    
    def register_sampling_site(
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
        Register a new sampling site.
        
        Args:
            label: Human-readable site label
            latitude: Observation latitude in decimal degrees
            longitude: Observation longitude in decimal degrees
            hyriv_id: HydroRIVERS reach ID
            site_type: Type of sampling site
            validation_status: Validation status of network match
            case_id: UUID of associated case (optional)
            network_latitude: Snapped network latitude (optional)
            network_longitude: Snapped network longitude (optional)
            snap_distance_m: Distance from observation to network (optional)
            role: Functional role in sampling strategy (optional)
            metadata: Additional site-specific metadata (optional)
            
        Returns:
            SamplingSite: Created site as domain model
            
        Raises:
            HTTPException: 400 if validation fails, 404 if case or HYRIV_ID not found
        """
        # Validate required fields
        if not label or not label.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "ValidationError",
                    "message": "label is required and cannot be empty",
                    "field": "label"
                }
            )
        
        # Validate HYRIV_ID exists in network
        try:
            self.hydrology_engine.get_reach(hyriv_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "InvalidHyrivIdError",
                    "message": f"HYRIV_ID {hyriv_id} not found in loaded network data",
                    "hyriv_id": hyriv_id
                }
            )
        
        # Attempt to create site
        try:
            site = self.sampling_repository.create_site(
                label=label.strip(),
                latitude=latitude,
                longitude=longitude,
                hyriv_id=hyriv_id,
                site_type=site_type,
                validation_status=validation_status,
                case_id=case_id,
                network_latitude=network_latitude,
                network_longitude=network_longitude,
                snap_distance_m=snap_distance_m,
                role=role,
                metadata=metadata
            )
            return site
        except ValueError as e:
            # Case not found
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "NotFoundError",
                    "message": str(e),
                    "resource_type": "Case",
                    "resource_id": str(case_id) if case_id else None
                }
            )
    
    def get_sampling_sites(self, case_id: UUID) -> list[SamplingSite]:
        """
        Retrieve all sampling sites for a case.
        
        Args:
            case_id: UUID of the case
            
        Returns:
            list[SamplingSite]: List of sampling sites as domain models
        """
        sites = self.sampling_repository.get_sites_by_case(case_id)
        return sites
    
    def evaluate_sampling_candidates(
        self,
        case: Case,
        zones: list[CandidateZone],
        candidate_sites: list[SamplingSite],
        commit: bool = True,
    ) -> tuple[SamplingDecision, DecisionTrace]:
        """
        Evaluate sampling candidates and make recommendation.
        
        Coordinates the sampling decision engine to evaluate all candidate
        sites, make a recommendation, and create an audit trail.
        
        Args:
            case: The investigation case
            zones: List of candidate zones being evaluated
            candidate_sites: List of potential sampling sites
            
        Returns:
            tuple[SamplingDecision, DecisionTrace]: Decision and trace as domain models
            
        Raises:
            HTTPException: 400 if validation fails
        """
        # Validate inputs
        if not zones:
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "ValidationError",
                    "message": "At least one candidate zone is required for evaluation",
                    "field": "zones"
                }
            )
        
        if not candidate_sites:
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "ValidationError",
                    "message": "At least one candidate site is required for evaluation",
                    "field": "candidate_sites"
                }
            )
        
        # Evaluate candidates using sampling engine
        evaluations = self.sampling_engine.evaluate_candidates(
            case=case,
            zones=zones,
            candidate_sites=candidate_sites,
            hydrology_engine=self.hydrology_engine
        )
        
        # Make recommendation
        status, recommended_site_ids, rationale = self.sampling_engine.make_recommendation(
            evaluations
        )
        
        # Save decision and trace to database
        decision, trace = self.sampling_repository.save_decision(
            case_id=case.id,
            status=status,
            recommended_site_ids=recommended_site_ids,
            rationale=rationale,
            evidence_used=[],  # Will be populated by engine's trace creation
            rules_applied=[],
            hydrology_checks=[],
            assumptions=[],
            limitations=[],
            commit=False,
        )
        
        # Create detailed trace using sampling engine
        detailed_trace = self.sampling_engine.create_decision_trace(
            case=case,
            evaluations=evaluations,
            status=status,
            recommended_site_ids=recommended_site_ids,
            decision_id=decision.id
        )

        # save_decision creates the trace atomically with the decision. Replace
        # its initial placeholders with the engine-produced audit content.
        db_trace = self.sampling_repository.db.scalar(
            select(DecisionTraceModel).where(
                DecisionTraceModel.decision_id == decision.id
            )
        )
        db_trace.evidence_used = detailed_trace.evidence_used
        db_trace.rules_applied = detailed_trace.rules_applied
        db_trace.hydrology_checks = detailed_trace.hydrology_checks
        db_trace.assumptions = detailed_trace.assumptions
        db_trace.limitations = detailed_trace.limitations
        if commit:
            self.sampling_repository.db.commit()
        else:
            self.sampling_repository.db.flush()
        
        # Return decision with detailed trace
        return decision, detailed_trace

    def generate_sampling_candidates(
        self,
        case: Case,
        zones: list[CandidateZone],
        detection_site: SamplingSite,
    ) -> tuple[CandidateGenerationResult, str, str]:
        """Generate candidates, then evaluate them with the existing engine."""
        if self.candidate_generator is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "type": "CandidateGeneratorUnavailable",
                    "message": "Automatic candidate generation is not configured.",
                },
            )
        result = self.candidate_generator.generate(
            zones=zones,
            site_a_hyriv_id=detection_site.hyriv_id,
            site_a_fraction=self.site_a_fraction,
        )
        generated_sites = [
            SamplingSite(
                id=uuid5(
                    NAMESPACE_URL,
                    f"generated-candidate:{case.id}:{candidate.hyriv_id}",
                ),
                case_id=case.id,
                label=f"Generated {candidate.equivalence_class}",
                latitude=candidate.latitude,
                longitude=candidate.longitude,
                hyriv_id=candidate.hyriv_id,
                site_type=SiteType.FOLLOW_UP,
                validation_status=candidate.validation_status,
                network_latitude=candidate.latitude,
                network_longitude=candidate.longitude,
                role="Topology equivalence-class representative",
                metadata={"status": "COUNTERFACTUAL"},
            )
            for candidate in result.candidates
        ]
        evaluations = self.sampling_engine.evaluate_candidates(
            case=case,
            zones=zones,
            candidate_sites=generated_sites,
            hydrology_engine=self.hydrology_engine,
        )
        status, _, reason = self.sampling_engine.make_recommendation(evaluations)
        return result, status.value, reason
    
    def get_decision_trace(self, decision_id: UUID) -> DecisionTrace:
        """
        Retrieve the decision trace for a sampling decision.
        
        Args:
            decision_id: UUID of the sampling decision
            
        Returns:
            DecisionTrace: The decision trace as domain model
            
        Raises:
            HTTPException: 404 if decision not found
        """
        # Note: This is a placeholder. The actual implementation would need
        # a method in SamplingRepository to retrieve traces by decision_id.
        # For now, we raise a not implemented error as this requires
        # additional repository methods not specified in the current task.
        raise HTTPException(
            status_code=501,
            detail={
                "type": "NotImplementedError",
                "message": "Decision trace retrieval not yet implemented",
                "decision_id": str(decision_id)
            }
        )
