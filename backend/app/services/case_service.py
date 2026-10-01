"""
Case service for business logic orchestration.

Coordinates CaseRepository and provides validation and error handling.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import HTTPException

from app.repositories.cases import CaseRepository, CaseNotFoundError
from app.domain.models import Case
from app.domain.enums import CaseStatus


class CaseService:
    """
    Service for case-related business logic.
    
    Orchestrates case operations, coordinates repository access,
    and enforces business rules and validation.
    """
    
    def __init__(self, case_repository: CaseRepository):
        """
        Initialize the service with required repository.
        
        Args:
            case_repository: Repository for case data access
        """
        self.case_repository = case_repository
    
    def create_case(
        self,
        target_taxon: str,
        observation_date: datetime,
        detection_site_id: UUID,
        status: CaseStatus = CaseStatus.ACTIVE,
        metadata: Optional[dict] = None
    ) -> Case:
        """
        Create a new case with validation.
        
        Args:
            target_taxon: Scientific name of the taxon detected
            observation_date: Date when the eDNA was detected
            detection_site_id: UUID of the detection site
            status: Initial case status (default: ACTIVE)
            metadata: Additional case-specific metadata
            
        Returns:
            Case: Created case as domain model
            
        Raises:
            HTTPException: 400 if validation fails, 404 if detection site not found
        """
        # Validate required fields
        if not target_taxon or not target_taxon.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "ValidationError",
                    "message": "target_taxon is required and cannot be empty",
                    "field": "target_taxon"
                }
            )
        
        if not detection_site_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "ValidationError",
                    "message": "detection_site_id is required",
                    "field": "detection_site_id"
                }
            )
        
        # Attempt to create case
        try:
            case = self.case_repository.create_case(
                target_taxon=target_taxon.strip(),
                observation_date=observation_date,
                detection_site_id=detection_site_id,
                status=status,
                metadata=metadata
            )
            return case
        except ValueError as e:
            # Detection site not found
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "NotFoundError",
                    "message": str(e),
                    "resource_type": "SamplingSite",
                    "resource_id": str(detection_site_id)
                }
            )
    
    def get_case(self, case_id: UUID) -> Case:
        """
        Retrieve a case by ID with 404 handling.
        
        Args:
            case_id: UUID of the case to retrieve
            
        Returns:
            Case: The case as domain model
            
        Raises:
            HTTPException: 404 if case not found
        """
        try:
            case = self.case_repository.get_case_by_id(case_id)
            return case
        except CaseNotFoundError as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "NotFoundError",
                    "message": f"Case with ID {case_id} not found",
                    "resource_type": "Case",
                    "resource_id": str(case_id)
                }
            )
    
    def list_cases(
        self,
        status: Optional[CaseStatus] = None,
        target_taxon: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> list[Case]:
        """
        List cases with optional filtering.
        
        Args:
            status: Filter by case status (optional)
            target_taxon: Filter by target taxon (optional)
            limit: Maximum number of results (optional)
            offset: Number of results to skip (default: 0)
            
        Returns:
            list[Case]: List of cases as domain models
        """
        cases = self.case_repository.list_cases(
            status=status,
            target_taxon=target_taxon,
            limit=limit,
            offset=offset
        )
        return cases
    
    def update_case_status(
        self,
        case_id: UUID,
        status: CaseStatus
    ) -> Case:
        """
        Update the status of a case.
        
        Args:
            case_id: UUID of the case to update
            status: New status value
            
        Returns:
            Case: Updated case as domain model
            
        Raises:
            HTTPException: 404 if case not found
        """
        try:
            case = self.case_repository.update_case(
                case_id=case_id,
                status=status
            )
            return case
        except CaseNotFoundError as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "NotFoundError",
                    "message": f"Case with ID {case_id} not found",
                    "resource_type": "Case",
                    "resource_id": str(case_id)
                }
            )
