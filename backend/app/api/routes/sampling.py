"""
Sampling management API routes.

Provides endpoints for registering sampling sites, managing candidate zones,
and evaluating sampling decisions.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.sampling import SamplingRepository, DecisionNotFoundError
from app.repositories.cases import CaseRepository
from app.services.sampling_service import SamplingService
from app.schemas.sampling import (
    SamplingSiteCreateRequest,
    SamplingSiteResponse,
    CandidateZoneCreateRequest,
    CandidateZoneResponse,
    SamplingDecisionResponse,
    DecisionTraceResponse,
    CandidateGenerationResponse,
)
from app.scientific.sampling.engine import ScaffoldSamplingDecisionEngine
from app.scientific.hydrology.engine import HydrologyEngine
from app.scientific.data_loader import WiggerPreflightLoader
from app.scientific.sampling.candidate_generator import CandidateSiteGenerator
from config import config


router = APIRouter(prefix="/cases", tags=["sampling"])


def get_sampling_service(db: Session = Depends(get_db)) -> SamplingService:
    """
    Dependency injection for SamplingService.
    
    Initializes the sampling engine and hydrology engine with preflight data,
    then creates the service instance.
    
    Args:
        db: Database session
        
    Returns:
        SamplingService: Initialized sampling service
    """
    # Load preflight data for hydrology engine
    loader = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
    reaches = loader.load_reaches()
    edges = loader.load_edges()
    
    # Create engines
    hydrology_engine = HydrologyEngine(reaches, edges)
    sampling_engine = ScaffoldSamplingDecisionEngine()
    reach_coordinates = {}
    for _, row in loader.load_reach_geometries().iterrows():
        midpoint = row.geometry.interpolate(0.5, normalized=True)
        reach_coordinates[int(row["HYRIV_ID"])] = (midpoint.y, midpoint.x)
    candidate_generator = CandidateSiteGenerator(
        hydrology_engine, reach_coordinates=reach_coordinates
    )
    snap = loader.load_site_a_snap_validation()
    site_a_fraction = float(
        snap["snapped_coordinate"]["fraction_along_reach"]
    )
    
    # Create repository and service
    sampling_repository = SamplingRepository(db)
    
    return SamplingService(
        sampling_repository=sampling_repository,
        sampling_engine=sampling_engine,
        hydrology_engine=hydrology_engine,
        candidate_generator=candidate_generator,
        site_a_fraction=site_a_fraction,
    )


@router.get(
    "/{case_id}/generated-candidates",
    response_model=CandidateGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate topology-based follow-up candidates",
)
def generate_sampling_candidates(
    case_id: UUID,
    db: Session = Depends(get_db),
    sampling_service: SamplingService = Depends(get_sampling_service),
) -> CandidateGenerationResponse:
    """Generate counterfactual candidates from all validated upstream reaches."""
    case = CaseRepository(db).get_case_by_id(case_id)
    repository = SamplingRepository(db)
    zones = repository.get_zones_by_case(case_id)
    detection_site = repository.get_site_by_id(case.detection_site_id)
    result, decision_status, decision_reason = (
        sampling_service.generate_sampling_candidates(
            case=case,
            zones=zones,
            detection_site=detection_site,
        )
    )
    return CandidateGenerationResponse(
        site_a_hyriv_id=result.site_a_hyriv_id,
        hypothesis_labels=result.hypothesis_labels,
        eligible_reach_count=result.eligible_reach_count,
        equivalence_classes=result.equivalence_classes,
        candidates=result.candidates,
        decision_status=decision_status,
        decision_reason=decision_reason,
        limitation=result.limitation,
    )


@router.post(
    "/{case_id}/sites",
    response_model=SamplingSiteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a sampling site",
    description="Register a new sampling site for a case"
)
def register_sampling_site(
    case_id: UUID,
    request: SamplingSiteCreateRequest,
    sampling_service: SamplingService = Depends(get_sampling_service)
) -> SamplingSiteResponse:
    """
    Register a sampling site for a case.
    
    Creates a new sampling site record with coordinates, HYRIV_ID mapping,
    site type, and validation status. Sites can be detection sites,
    branch-specific sites, shared trunk sites, or follow-up sites.
    
    Args:
        case_id: UUID of the case
        request: Sampling site creation request
        sampling_service: Sampling service (injected)
        
    Returns:
        SamplingSiteResponse: Created sampling site with all metadata
        
    Raises:
        HTTPException: 400 if validation fails, 404 if case or HYRIV_ID not found
        
    **Validates: Requirements 2.1, 8.1, 13.1, 13.4, 18.1, 18.3**
    """
    site = sampling_service.register_sampling_site(
        label=request.label,
        latitude=request.latitude,
        longitude=request.longitude,
        hyriv_id=request.hyriv_id,
        site_type=request.site_type,
        validation_status=request.validation_status,
        case_id=case_id,
        network_latitude=request.network_latitude,
        network_longitude=request.network_longitude,
        snap_distance_m=request.snap_distance_m,
        role=request.role,
        metadata=request.metadata
    )
    
    return SamplingSiteResponse.model_validate(site)


@router.get(
    "/{case_id}/sites",
    response_model=list[SamplingSiteResponse],
    status_code=status.HTTP_200_OK,
    summary="Get sampling sites",
    description="Retrieve all sampling sites for a case"
)
def get_sampling_sites(
    case_id: UUID,
    sampling_service: SamplingService = Depends(get_sampling_service)
) -> list[SamplingSiteResponse]:
    """
    Retrieve all sampling sites for a case.
    
    Returns all registered sampling sites including detection sites and
    candidate sampling locations.
    
    Args:
        case_id: UUID of the case
        sampling_service: Sampling service (injected)
        
    Returns:
        list[SamplingSiteResponse]: List of sampling sites
        
    **Validates: Requirements 8.2, 18.1, 18.3**
    """
    sites = sampling_service.get_sampling_sites(case_id)
    
    return [SamplingSiteResponse.model_validate(site) for site in sites]


@router.post(
    "/{case_id}/zones",
    response_model=CandidateZoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a candidate zone",
    description="Create a new candidate zone representing a potential source region"
)
def create_candidate_zone(
    case_id: UUID,
    request: CandidateZoneCreateRequest,
    db: Session = Depends(get_db),
    sampling_service: SamplingService = Depends(get_sampling_service)
) -> CandidateZoneResponse:
    """
    Create a candidate zone for a case.
    
    Candidate zones represent hypothetical source regions in the river network.
    Each zone has a root reach and a set of member reaches that comprise
    the potential source area.
    
    Args:
        case_id: UUID of the case
        request: Candidate zone creation request
        db: Database session (injected)
        sampling_service: Sampling service (injected)
        
    Returns:
        CandidateZoneResponse: Created candidate zone with all metadata
        
    Raises:
        HTTPException: 400 if validation fails, 404 if case or root HYRIV_ID not found
        
    **Validates: Requirements 4.1, 4.2, 13.1, 13.4, 18.1, 18.3**
    """
    # Validate root HYRIV_ID exists in network
    try:
        sampling_service.hydrology_engine.get_reach(request.root_hyriv_id)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail={
                "type": "InvalidHyrivIdError",
                "message": f"Root HYRIV_ID {request.root_hyriv_id} not found in loaded network data",
                "hyriv_id": request.root_hyriv_id
            }
        )
    
    # Create zone using repository directly (no service method for this yet)
    sampling_repository = SamplingRepository(db)
    
    try:
        zone = sampling_repository.create_zone(
            case_id=case_id,
            label=request.label,
            root_hyriv_id=request.root_hyriv_id,
            reach_ids=request.reach_ids,
            validation_status=request.validation_status,
            metadata=request.metadata
        )
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail={
                "type": "NotFoundError",
                "message": str(e),
                "resource_type": "Case",
                "resource_id": str(case_id)
            }
        )
    
    return CandidateZoneResponse.model_validate(zone)


@router.get(
    "/{case_id}/zones",
    response_model=list[CandidateZoneResponse],
    status_code=status.HTTP_200_OK,
    summary="Get candidate zones",
    description="Retrieve all candidate zones for a case"
)
def get_candidate_zones(
    case_id: UUID,
    db: Session = Depends(get_db)
) -> list[CandidateZoneResponse]:
    """
    Retrieve all candidate zones for a case.
    
    Returns all defined candidate zones representing potential source regions
    in the river network.
    
    Args:
        case_id: UUID of the case
        db: Database session (injected)
        
    Returns:
        list[CandidateZoneResponse]: List of candidate zones
        
    **Validates: Requirements 4.2, 18.1, 18.3**
    """
    sampling_repository = SamplingRepository(db)
    zones = sampling_repository.get_zones_by_case(case_id)
    
    return [CandidateZoneResponse.model_validate(zone) for zone in zones]


@router.post(
    "/{case_id}/sampling-decision",
    response_model=SamplingDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate sampling candidates",
    description="Evaluate candidate sites and make sampling recommendation"
)
def evaluate_sampling_decision(
    case_id: UUID,
    db: Session = Depends(get_db),
    sampling_service: SamplingService = Depends(get_sampling_service)
) -> SamplingDecisionResponse:
    """
    Evaluate sampling candidates and make recommendation.
    
    Analyzes all candidate zones and sampling sites for the case, evaluates
    their discrimination power, and recommends prioritized sampling sites.
    Creates an audit trail showing evidence, rules, hydrology checks, and
    assumptions used in the decision.
    
    The system returns INSUFFICIENT_DATA when scientific scoring criteria
    are not yet validated, rather than inventing recommendations.
    
    Args:
        case_id: UUID of the case
        db: Database session (injected)
        sampling_service: Sampling service (injected)
        
    Returns:
        SamplingDecisionResponse: Decision with status and recommendations
        
    Raises:
        HTTPException: 400 if validation fails, 404 if case not found
        
    **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4, 10.5, 13.1, 13.4, 18.1, 18.3**
    """
    # Get the case
    case_repository = CaseRepository(db)
    case = case_repository.get_case_by_id(case_id)
    
    # Get zones and candidate sites
    sampling_repository = SamplingRepository(db)
    zones = sampling_repository.get_zones_by_case(case_id)
    candidate_sites = sampling_repository.get_sites_by_case(case_id)
    
    # Evaluate candidates and make decision
    decision, trace = sampling_service.evaluate_sampling_candidates(
        case=case,
        zones=zones,
        candidate_sites=candidate_sites
    )
    
    return SamplingDecisionResponse.model_validate(decision)


@router.get(
    "/{case_id}/decision-trace",
    response_model=DecisionTraceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get decision trace",
    description="Retrieve the audit trail for a sampling decision"
)
def get_decision_trace(
    case_id: UUID,
    db: Session = Depends(get_db)
) -> DecisionTraceResponse:
    """
    Retrieve the decision trace for the most recent sampling decision.
    
    Returns the complete audit trail showing which evidence items, scientific
    rules, hydrology checks, assumptions, and limitations were involved in
    making the sampling decision.
    
    Args:
        case_id: UUID of the case
        db: Database session (injected)
        
    Returns:
        DecisionTraceResponse: Decision audit trail
        
    Raises:
        HTTPException: 404 if no decision found for case
        
    **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 13.1, 18.1, 18.3**
    """
    from fastapi import HTTPException
    
    # Get the most recent decision for this case
    sampling_repository = SamplingRepository(db)
    
    # Query for decisions by case (we need to get the most recent one)
    from sqlalchemy import select, desc
    from app.db.models import SamplingDecisionModel
    
    query = select(SamplingDecisionModel).where(
        SamplingDecisionModel.case_id == case_id
    ).order_by(desc(SamplingDecisionModel.created_at)).limit(1)
    
    result = db.execute(query)
    db_decision = result.scalar_one_or_none()
    
    if not db_decision:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "NotFoundError",
                "message": f"No sampling decision found for case {case_id}",
                "resource_type": "SamplingDecision",
                "resource_id": str(case_id)
            }
        )
    
    # Get the trace for this decision
    try:
        trace = sampling_repository.get_trace_by_decision_id(db_decision.id)
    except DecisionNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "NotFoundError",
                "message": f"No decision trace found for decision {db_decision.id}",
                "resource_type": "DecisionTrace",
                "resource_id": str(db_decision.id)
            }
        )
    
    return DecisionTraceResponse.model_validate(trace)
