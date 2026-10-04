from app.schemas.detection_contexts import LocationMatchRequest
"""
Hydrology analysis API routes.

Provides endpoints for river network queries including reach metadata,
upstream analysis, downstream paths, and network distance calculations.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.hydrology_service import HydrologyService
from app.schemas.hydrology import (
    ReachResponse,
    UpstreamQueryResponse,
    DownstreamPathResponse,
    NetworkDistanceResponse,
)
from app.scientific.hydrology.engine import HydrologyEngine
from app.scientific.data_loader import WiggerPreflightLoader
from config import config


router = APIRouter(prefix="/hydrology", tags=["hydrology"])


def get_hydrology_service(db: Session = Depends(get_db)) -> HydrologyService:
    """
    Dependency injection for HydrologyService.
    
    Initializes the hydrology engine with preflight data and creates
    the service instance.
    
    Args:
        db: Database session
        
    Returns:
        HydrologyService: Initialized hydrology service
    """
    # Load preflight data
    loader = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
    reaches = loader.load_reaches()
    edges = loader.load_edges()
    
    # Create hydrology engine
    hydrology_engine = HydrologyEngine(reaches, edges)
    
    # Create and return service
    return HydrologyService(hydrology_engine)


@router.get(
    "/reaches/{hyriv_id}",
    response_model=ReachResponse,
    status_code=status.HTTP_200_OK,
    summary="Get reach metadata",
    description="Retrieve river reach metadata by HYRIV_ID"
)
def get_reach(
    hyriv_id: int,
    hydrology_service: HydrologyService = Depends(get_hydrology_service)
) -> ReachResponse:
    """
    Retrieve reach metadata by HYRIV_ID.
    
    Returns complete metadata for a river reach including downstream
    connection, length, contributing area, and average discharge.
    
    Args:
        hyriv_id: The HydroRIVERS reach identifier
        hydrology_service: Hydrology service (injected)
        
    Returns:
        ReachResponse: Reach metadata
        
    Raises:
        HTTPException: 404 if HYRIV_ID not found in loaded network
        
    **Validates: Requirements 7.1, 13.2, 18.1, 18.3**
    """
    reach = hydrology_service.get_reach(hyriv_id)
    return ReachResponse.model_validate(reach)


@router.get(
    "/upstream/{hyriv_id}",
    response_model=UpstreamQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query upstream reaches",
    description="Get all reaches that flow toward the specified reach"
)
def query_upstream(
    hyriv_id: int,
    hydrology_service: HydrologyService = Depends(get_hydrology_service)
) -> UpstreamQueryResponse:
    """
    Query all reaches upstream of the specified reach.
    
    Uses graph traversal to find all reaches that flow toward the
    target reach through the river network.
    
    Args:
        hyriv_id: The target reach identifier
        hydrology_service: Hydrology service (injected)
        
    Returns:
        UpstreamQueryResponse: Target reach, list of upstream reaches, and count
        
    Raises:
        HTTPException: 404 if HYRIV_ID not found in loaded network
        
    **Validates: Requirements 7.1, 7.3, 13.2, 18.1, 18.3**
    """
    upstream_reaches = hydrology_service.query_upstream_reaches(hyriv_id)
    
    return UpstreamQueryResponse(
        target_hyriv_id=hyriv_id,
        upstream_reach_ids=upstream_reaches,
        count=len(upstream_reaches)
    )


@router.get(
    "/downstream/{hyriv_id}",
    response_model=DownstreamPathResponse,
    status_code=status.HTTP_200_OK,
    summary="Query downstream path",
    description="Get the ordered path of reaches from start to stop (or terminus)"
)
def query_downstream(
    hyriv_id: int,
    stop_hyriv_id: Optional[int] = Query(None, description="Optional stopping reach"),
    hydrology_service: HydrologyService = Depends(get_hydrology_service)
) -> DownstreamPathResponse:
    """
    Query the downstream path from start to stop (or terminus).
    
    Follows NEXT_DOWN relationships to build an ordered path through
    the river network. If stop_hyriv_id is not provided, returns the
    complete path to the river terminus.
    
    Args:
        hyriv_id: Starting reach identifier
        stop_hyriv_id: Optional stopping reach identifier (query param)
        hydrology_service: Hydrology service (injected)
        
    Returns:
        DownstreamPathResponse: Start, stop, ordered path, and path length
        
    Raises:
        HTTPException: 404 if HYRIV_ID not found in loaded network
        HTTPException: 400 if stop is not downstream of start
        
    **Validates: Requirements 7.2, 13.2, 18.1, 18.3**
    """
    path = hydrology_service.query_downstream_path(hyriv_id, stop_hyriv_id)
    
    return DownstreamPathResponse(
        start_hyriv_id=hyriv_id,
        stop_hyriv_id=stop_hyriv_id,
        path=path,
        length=len(path)
    )


@router.get(
    "/distance",
    response_model=NetworkDistanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate network distance",
    description="Calculate network distance between two reaches using LENGTH_KM"
)
def calculate_distance(
    from_hyriv_id: int = Query(..., description="Source reach identifier"),
    to_hyriv_id: int = Query(..., description="Target reach identifier"),
    hydrology_service: HydrologyService = Depends(get_hydrology_service)
) -> NetworkDistanceResponse:
    """
    Calculate network distance between two reaches.
    
    Sums LENGTH_KM values along the downstream path from source to target.
    The from_hyriv_id must be upstream of to_hyriv_id for the calculation
    to succeed.
    
    Args:
        from_hyriv_id: Source reach identifier (query param)
        to_hyriv_id: Target reach identifier (query param)
        hydrology_service: Hydrology service (injected)
        
    Returns:
        NetworkDistanceResponse: Distance in km and the path taken
        
    Raises:
        HTTPException: 404 if either HYRIV_ID not found in loaded network
        HTTPException: 400 if reaches are not connected (from not upstream of to)
        
    **Validates: Requirements 7.5, 8.4, 13.2, 18.1, 18.3**
    """
    # Calculate distance (raises HTTPException if not connected)
    distance = hydrology_service.calculate_network_distance(from_hyriv_id, to_hyriv_id)
    
    # Get the path for the response
    path = hydrology_service.query_downstream_path(from_hyriv_id, to_hyriv_id)
    
    return NetworkDistanceResponse(
        from_hyriv_id=from_hyriv_id,
        to_hyriv_id=to_hyriv_id,
        distance_km=distance,
        path=path
    )


@router.post('/match-location')
def match_location(request: LocationMatchRequest):
    from app.services.location_matching import LocationMatchingService
    return LocationMatchingService().match(request.latitude,request.longitude)
