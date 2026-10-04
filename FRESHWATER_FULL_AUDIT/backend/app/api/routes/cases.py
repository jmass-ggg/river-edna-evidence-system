"""
Case management API routes.

Provides endpoints for creating, retrieving, and listing investigation cases.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.cases import CaseRepository
from app.repositories.sampling import SamplingRepository
from app.services.case_service import CaseService
from app.schemas.cases import CaseCreateRequest, CaseResponse, CaseListResponse
from app.domain.enums import CaseStatus, SiteType, ValidationStatus
from app.api.dependencies import get_hydrology_engine
from app.scientific.hydrology.engine import HydrologyEngine


router = APIRouter(prefix="/cases", tags=["cases"])


def get_case_service(db: Session = Depends(get_db)) -> CaseService:
    """
    Dependency injection for CaseService.
    
    Args:
        db: Database session
        
    Returns:
        CaseService: Initialized case service
    """
    case_repository = CaseRepository(db)
    return CaseService(case_repository)


@router.post(
    "",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new case",
    description="Create a new eDNA detection case with detection site"
)
def create_case(
    request: CaseCreateRequest,
    db: Session = Depends(get_db),
    case_service: CaseService = Depends(get_case_service),
    hydrology_engine: HydrologyEngine = Depends(get_hydrology_engine),
) -> CaseResponse:
    """
    Create a new investigation case.
    
    Creates a case record and registers the detection site automatically.
    The detection site is created as a DETECTION_SITE type with coordinates
    and HYRIV_ID from the request.
    
    Args:
        request: Case creation request with detection site details
        db: Database session (injected)
        case_service: Case service (injected)
        
    Returns:
        CaseResponse: Created case with all metadata
        
    Raises:
        HTTPException: 400 if validation fails, 404 if HYRIV_ID not found
        
    **Validates: Requirements 1.1, 1.2, 1.3, 13.1, 13.4, 18.1, 18.3**
    """
    # The application does not implement coordinate snapping. Require the
    # caller's supplied reach to exist in the validated loaded network.
    hydrology_engine.get_reach(request.detection_site_hyriv_id)

    from app.scientific.data_loader import WiggerPreflightLoader
    from config import config
    try:
        validation = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR).detection_reference(
            request.detection_site_latitude, request.detection_site_longitude,
            request.detection_site_hyriv_id,
        )
    except (ValueError, OSError, KeyError) as exc:
        validation = {"validation_status": "NOT_VERIFIED", "metadata": {
            "validation_reason": f"Frozen location validation unavailable: {exc}"
        }}

    # Create the site first to satisfy the case foreign key, then link it back
    # to the case before committing the complete transaction.
    sampling_repository = SamplingRepository(db)
    
    try:
        detection_site = sampling_repository.create_site(
            label="Detection Site",
            latitude=request.detection_site_latitude,
            longitude=request.detection_site_longitude,
            hyriv_id=request.detection_site_hyriv_id,
            site_type=SiteType.DETECTION_SITE,
            validation_status=ValidationStatus(validation["validation_status"]),
            network_latitude=validation.get("network_latitude"),
            network_longitude=validation.get("network_longitude"),
            snap_distance_m=validation.get("snap_distance_m"),
            case_id=None,  # Will be linked after case creation
            metadata={"origin": "case_creation", "taxon": request.target_taxon, **validation["metadata"]},
            commit=False,
        )

        # Create the case with the detection site in the same transaction.
        case = case_service.create_case(
            target_taxon=request.target_taxon,
            observation_date=request.observation_date,
            detection_site_id=detection_site.id,
            status=CaseStatus.ACTIVE,
            metadata=request.metadata,
            commit=False,
        )

        # The detection site is created before the case to satisfy the case foreign
        # key. Link it back afterward so case-scoped site queries return Site A.
        from app.db.models import SamplingSiteModel
        db_site = db.get(SamplingSiteModel, detection_site.id)
        if db_site is not None:
            db_site.case_id = case.id

        from app.repositories.evidence import EvidenceRepository
        for item in request.initial_evidence:
            EvidenceRepository(db).add_evidence(case_id=case.id, **item.model_dump(), commit=False)

        response = CaseResponse.model_validate(case)
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


@router.get(
    "/{case_id}",
    response_model=CaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get case by ID",
    description="Retrieve a case by its unique identifier"
)
def get_case(
    case_id: UUID,
    case_service: CaseService = Depends(get_case_service)
) -> CaseResponse:
    """
    Retrieve a case by ID.
    
    Args:
        case_id: UUID of the case to retrieve
        case_service: Case service (injected)
        
    Returns:
        CaseResponse: The case with all metadata
        
    Raises:
        HTTPException: 404 if case not found
        
    **Validates: Requirements 1.2, 13.1, 18.1, 18.3**
    """
    case = case_service.get_case(case_id)
    return CaseResponse.model_validate(case)


@router.get(
    "",
    response_model=CaseListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all cases",
    description="Retrieve all cases with optional filtering"
)
def list_cases(
    status_filter: Optional[CaseStatus] = Query(None, alias="status", description="Filter by case status"),
    target_taxon: Optional[str] = Query(None, description="Filter by target taxon"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    case_service: CaseService = Depends(get_case_service)
) -> CaseListResponse:
    """
    List all cases with optional filtering.
    
    Args:
        status_filter: Filter by case status (optional)
        target_taxon: Filter by target taxon (optional)
        limit: Maximum number of results (optional)
        offset: Number of results to skip (default: 0)
        case_service: Case service (injected)
        
    Returns:
        CaseListResponse: List of cases and total count
        
    **Validates: Requirements 1.3, 18.1, 18.3**
    """
    cases = case_service.list_cases(
        status=status_filter,
        target_taxon=target_taxon,
        limit=limit,
        offset=offset
    )
    
    return CaseListResponse(
        cases=[CaseResponse.model_validate(case) for case in cases],
        total=len(cases)
    )
