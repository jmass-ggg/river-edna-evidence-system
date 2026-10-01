"""
Evidence management API routes.

Provides endpoints for adding evidence to cases and assessing evidence compatibility.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.evidence import EvidenceRepository
from app.repositories.cases import CaseRepository
from app.repositories.sampling import SamplingRepository
from app.services.evidence_service import EvidenceService
from app.services.case_service import CaseService
from app.schemas.evidence import (
    EvidenceCreateRequest,
    EvidenceResponse,
    AssessmentSummaryResponse,
    EvidenceAssessmentResponse,
)


router = APIRouter(prefix="/cases", tags=["evidence"])


def get_evidence_service(db: Session = Depends(get_db)) -> EvidenceService:
    """
    Dependency injection for EvidenceService.
    
    Args:
        db: Database session
        
    Returns:
        EvidenceService: Initialized evidence service
    """
    from app.scientific.evidence.engine import EvidenceCompatibilityEngineImpl
    
    evidence_repository = EvidenceRepository(db)
    evidence_engine = EvidenceCompatibilityEngineImpl()
    return EvidenceService(evidence_repository, evidence_engine)


@router.post(
    "/{case_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add evidence to case",
    description="Add a new evidence item to an investigation case"
)
def add_evidence(
    case_id: UUID,
    request: EvidenceCreateRequest,
    evidence_service: EvidenceService = Depends(get_evidence_service)
) -> EvidenceResponse:
    """
    Add evidence to a case.
    
    Creates a new evidence item and associates it with the specified case.
    Evidence includes type, source, value, quality indicators, and provenance.
    
    Args:
        case_id: UUID of the case to add evidence to
        request: Evidence creation request
        evidence_service: Evidence service (injected)
        
    Returns:
        EvidenceResponse: Created evidence item with all metadata
        
    Raises:
        HTTPException: 400 if validation fails, 404 if case not found
        
    **Validates: Requirements 5.1, 5.2, 13.1, 13.4, 18.1, 18.3**
    """
    evidence = evidence_service.add_evidence(
        case_id=case_id,
        evidence_type=request.evidence_type,
        source=request.source,
        value=request.value,
        observed_at=request.observed_at,
        quality=request.quality,
        provenance=request.provenance
    )
    
    return EvidenceResponse.model_validate(evidence)


@router.get(
    "/{case_id}/evidence",
    response_model=list[EvidenceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get evidence for case",
    description="Retrieve all evidence items for a case"
)
def get_evidence(
    case_id: UUID,
    evidence_service: EvidenceService = Depends(get_evidence_service)
) -> list[EvidenceResponse]:
    """
    Retrieve all evidence for a case.
    
    Args:
        case_id: UUID of the case
        evidence_service: Evidence service (injected)
        
    Returns:
        list[EvidenceResponse]: List of evidence items
        
    **Validates: Requirements 5.2, 18.1, 18.3**
    """
    evidence_items = evidence_service.get_evidence_for_case(case_id)
    
    return [EvidenceResponse.model_validate(item) for item in evidence_items]


@router.get(
    "/{case_id}/evidence-assessment",
    response_model=list[AssessmentSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Assess evidence compatibility",
    description="Assess how evidence relates to candidate zone hypotheses"
)
def assess_evidence(
    case_id: UUID,
    db: Session = Depends(get_db),
    evidence_service: EvidenceService = Depends(get_evidence_service)
) -> list[AssessmentSummaryResponse]:
    """
    Assess evidence compatibility for all candidate zones.
    
    Evaluates each evidence item against zone hypotheses using the evidence
    compatibility engine. Returns structured assessments showing which evidence
    supports, contradicts, or is neutral/unknown for each zone.
    
    Args:
        case_id: UUID of the case
        db: Database session (injected)
        evidence_service: Evidence service (injected)
        
    Returns:
        list[AssessmentSummaryResponse]: Assessments for each zone
        
    Raises:
        HTTPException: 404 if case not found
        
    **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 13.1, 13.4, 18.1, 18.3**
    """
    # Get the case
    case_repository = CaseRepository(db)
    case = case_repository.get_case_by_id(case_id)
    
    # Get the candidate zones
    sampling_repository = SamplingRepository(db)
    zones = sampling_repository.get_zones_by_case(case_id)
    
    # Assess evidence for all zones
    results = evidence_service.assess_evidence_for_zones(
        case=case,
        zones=zones,
        scientific_rules=None  # No validated rules yet
    )
    
    # Convert to response format
    responses = []
    for zone_label, zone_results in results.items():
        responses.append(
            AssessmentSummaryResponse(
                zone_id=zone_results["zone_id"],
                zone_label=zone_label,
                assessments=[
                    EvidenceAssessmentResponse.model_validate(assessment)
                    for assessment in zone_results["assessments"]
                ],
                summary=zone_results["summary"]
            )
        )
    
    return responses
