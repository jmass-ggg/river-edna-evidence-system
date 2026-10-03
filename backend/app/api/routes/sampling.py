"""
Sampling management API routes.

Provides endpoints for registering sampling sites, managing candidate zones,
and evaluating sampling decisions.
"""
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.sampling import SamplingRepository, DecisionNotFoundError
from app.repositories.cases import CaseRepository, CaseNotFoundError
from app.services.sampling_service import SamplingService
from app.schemas.sampling import (
    SamplingSiteCreateRequest,
    SamplingSiteResponse,
    CandidateZoneCreateRequest,
    CandidateZoneResponse,
    SamplingDecisionResponse,
    DecisionTraceResponse,
    CandidateGenerationResponse,
    GeneratedCandidateResponse,
    InvestigationMapResponse,
)
from app.scientific.sampling.engine import ScaffoldSamplingDecisionEngine
from app.scientific.hydrology.engine import HydrologyEngine
from app.scientific.data_loader import WiggerPreflightLoader
from app.scientific.sampling.candidate_generator import CandidateSiteGenerator
from config import config


router = APIRouter(prefix="/cases", tags=["sampling"])


def _get_case(db: Session, case_id: UUID):
    try:
        return CaseRepository(db).get_case_by_id(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail={
            "type": "NotFoundError", "message": str(exc),
            "resource_type": "Case", "resource_id": str(case_id),
        }) from exc


def _feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


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
    "/{case_id}/map",
    response_model=InvestigationMapResponse,
    summary="Get case-specific verified geographical data",
)
def get_investigation_map(
    case_id: UUID,
    db: Session = Depends(get_db),
    sampling_service: SamplingService = Depends(get_sampling_service),
) -> InvestigationMapResponse:
    """Return verified reach geometry plus only this case's persisted overlays."""
    case = _get_case(db, case_id)
    repository = SamplingRepository(db)
    detection_site = repository.get_site_by_id(case.detection_site_id)
    sites = repository.get_sites_by_case(case_id)
    if all(site.id != case.detection_site_id for site in sites):
        sites = [detection_site, *sites]
    zones = repository.get_zones_by_case(case_id)

    reach_ids = {
        case_site.hyriv_id for case_site in sites
    } | {
        reach_id for zone in zones for reach_id in zone.reach_ids
    }
    reach_ids.update(
        sampling_service.hydrology_engine.get_upstream_reaches(
            detection_site.hyriv_id
        )
    )
    reach_ids.add(detection_site.hyriv_id)

    geometries = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR).load_reach_geometries()
    geometries = geometries[geometries["HYRIV_ID"].astype(int).isin(reach_ids)]
    river_network = json.loads(geometries.to_json())
    geometry_by_id = {
        int(row["HYRIV_ID"]): row.geometry.__geo_interface__
        for _, row in geometries.iterrows()
    }
    zone_features = [
        {
            "type": "Feature",
            "geometry": geometry_by_id[reach_id],
            "properties": {"zone": zone.label, "HYRIV_ID": reach_id},
        }
        for zone in zones
        for reach_id in zone.reach_ids
        if reach_id in geometry_by_id
    ]
    available = bool(river_network["features"])
    return InvestigationMapResponse(
        crs="EPSG:4326",
        available=available,
        unavailable_reason=(
            None
            if available
            else "No verified HydroRIVERS geometry exists for this case."
        ),
        river_network=river_network,
        source_zones=_feature_collection(zone_features),
        sites=[SamplingSiteResponse.model_validate(site) for site in sites],
        provenance={
            "river_network": str(config.PREFLIGHT_DATA_DIR / "upstream_reaches_real.geojson"),
            "status": "validated HydroRIVERS geometry with case-persisted overlays",
        },
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
    case = _get_case(db, case_id)
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
    candidates = []
    for candidate in result.candidates:
        pairs = [
            [result.hypothesis_labels[left], result.hypothesis_labels[right]]
            for left in range(len(candidate.signature))
            for right in range(left + 1, len(candidate.signature))
            if candidate.signature[left] != candidate.signature[right]
        ]
        candidates.append(
            GeneratedCandidateResponse.model_validate(candidate).model_copy(
                update={"distinguished_hypothesis_pairs": pairs,
                        "site_id": repository.persist_generated_site(case_id, candidate).id}
            )
        )
    db.commit()
    return CandidateGenerationResponse(
        site_a_hyriv_id=result.site_a_hyriv_id,
        hypothesis_labels=result.hypothesis_labels,
        eligible_reach_count=result.eligible_reach_count,
        equivalence_classes=result.equivalence_classes,
        candidates=candidates,
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
    _get_case(db, case_id)
    engine = sampling_service.hydrology_engine
    for reach_id in request.reach_ids:
        try:
            engine.get_reach(reach_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail={
                "type": "InvalidHyrivIdError", "message": str(exc), "hyriv_id": reach_id,
            }) from exc
    members = set(request.reach_ids)
    for reach_id in request.reach_ids:
        if reach_id == request.root_hyriv_id:
            continue
        try:
            path = engine.get_downstream_path(reach_id, request.root_hyriv_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={
                "type": "InvalidSourceZone", "message": str(exc),
            }) from exc
        if not set(path).issubset(members):
            raise HTTPException(status_code=422, detail={
                "type": "InvalidSourceZone",
                "message": f"Source zone omits connecting reaches between {reach_id} and root {request.root_hyriv_id}",
            })

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
    _get_case(db, case_id)
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
    case = _get_case(db, case_id)
    
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
    
    from app.db.models import SamplingDecisionModel
    evaluations = sampling_service.sampling_engine.evaluate_candidates(
        case, zones, candidate_sites, sampling_service.hydrology_engine
    )
    stored = db.get(SamplingDecisionModel, decision.id)
    stored.candidate_snapshot = {"candidates": [{
        "site_id": str(item["site_id"]), "label": item["site_label"],
        "hyriv_id": item["site_hyriv_id"], "signature": item["signature"],
        "pair_separation_score": item["scores"]["separated_hypothesis_pairs"],
        "validation_status": next(site.validation_status.value for site in candidate_sites if site.id == item["site_id"]),
        "distinguished_hypothesis_pairs": [
            [item["remaining_hypotheses"][left], item["remaining_hypotheses"][right]]
            for left in range(len(item["signature"])) for right in range(left + 1, len(item["signature"]))
            if item["signature"][left] != item["signature"][right]
        ],
    } for item in evaluations]}
    db.commit()
    decision.candidate_snapshot = stored.candidate_snapshot
    return SamplingDecisionResponse.model_validate(decision)


@router.get(
    "/{case_id}/sampling-decision",
    response_model=SamplingDecisionResponse | None,
    status_code=status.HTTP_200_OK,
    summary="Get the latest sampling decision",
)
def get_latest_sampling_decision(
    case_id: UUID,
    db: Session = Depends(get_db),
) -> SamplingDecisionResponse | None:
    """Return null when the case has not been scientifically evaluated."""
    _get_case(db, case_id)
    decision = SamplingRepository(db).get_latest_decision_for_case(case_id)
    return (
        SamplingDecisionResponse.model_validate(decision)
        if decision is not None
        else None
    )


@router.get(
    "/{case_id}/decision-trace",
    response_model=DecisionTraceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get decision trace",
    description="Retrieve the audit trail for a sampling decision"
)
def get_decision_trace(
    case_id: UUID,
    db: Session = Depends(get_db),
    decision_id: UUID | None = None,
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
    
    _get_case(db, case_id)
    query = select(SamplingDecisionModel).where(SamplingDecisionModel.case_id == case_id)
    if decision_id is not None:
        query = query.where(SamplingDecisionModel.id == decision_id)
    query = query.order_by(desc(SamplingDecisionModel.created_at), desc(SamplingDecisionModel.id)).limit(1)
    
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
