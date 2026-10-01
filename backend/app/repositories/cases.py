"""
Case repository for data access operations.

Hides SQLAlchemy details and returns domain models.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import CaseModel, SamplingSiteModel
from app.domain.models import Case
from app.domain.enums import CaseStatus


class CaseNotFoundError(Exception):
    """Raised when a case is not found in the database."""
    def __init__(self, case_id: UUID):
        self.case_id = case_id
        super().__init__(f"Case with ID {case_id} not found")


class CaseRepository:
    """
    Repository for Case data access operations.
    
    Handles CRUD operations for cases and hides SQLAlchemy details
    from the service layer.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the repository with a database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def create_case(
        self,
        target_taxon: str,
        observation_date: datetime,
        detection_site_id: UUID,
        status: CaseStatus = CaseStatus.ACTIVE,
        metadata: Optional[dict] = None
    ) -> Case:
        """
        Create a new case and persist to database.
        
        Args:
            target_taxon: Scientific name of the taxon detected
            observation_date: Date when the eDNA was detected
            detection_site_id: UUID of the detection site
            status: Initial case status (default: ACTIVE)
            metadata: Additional case-specific metadata
            
        Returns:
            Case: Created case as domain model
            
        Raises:
            ValueError: If detection_site_id does not exist
        """
        # Verify detection site exists
        site = self.db.get(SamplingSiteModel, detection_site_id)
        if not site:
            raise ValueError(f"Detection site with ID {detection_site_id} not found")
        
        # Create database model
        db_case = CaseModel(
            target_taxon=target_taxon,
            observation_date=observation_date,
            detection_site_id=detection_site_id,
            status=status.value,
            meta=metadata or {}
        )
        
        # Persist to database
        self.db.add(db_case)
        self.db.commit()
        self.db.refresh(db_case)
        
        # Convert to domain model
        return self._to_domain(db_case)
    
    def get_case_by_id(self, case_id: UUID) -> Case:
        """
        Retrieve a case by its ID.
        
        Args:
            case_id: UUID of the case to retrieve
            
        Returns:
            Case: The case as domain model
            
        Raises:
            CaseNotFoundError: If case does not exist
        """
        db_case = self.db.get(CaseModel, case_id)
        
        if not db_case:
            raise CaseNotFoundError(case_id)
        
        return self._to_domain(db_case)
    
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
        # Build query
        query = select(CaseModel)
        
        # Apply filters
        if status:
            query = query.where(CaseModel.status == status.value)
        if target_taxon:
            query = query.where(CaseModel.target_taxon == target_taxon)
        
        # Apply pagination
        query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        
        # Order by creation date (newest first)
        query = query.order_by(CaseModel.created_at.desc())
        
        # Execute query
        result = self.db.execute(query)
        db_cases = result.scalars().all()
        
        # Convert to domain models
        return [self._to_domain(db_case) for db_case in db_cases]
    
    def update_case(
        self,
        case_id: UUID,
        status: Optional[CaseStatus] = None,
        metadata: Optional[dict] = None
    ) -> Case:
        """
        Update a case.
        
        Args:
            case_id: UUID of the case to update
            status: New status (optional)
            metadata: New or updated metadata (optional)
            
        Returns:
            Case: Updated case as domain model
            
        Raises:
            CaseNotFoundError: If case does not exist
        """
        db_case = self.db.get(CaseModel, case_id)
        
        if not db_case:
            raise CaseNotFoundError(case_id)
        
        # Update fields
        if status:
            db_case.status = status.value
        if metadata is not None:
            db_case.meta = metadata
        
        # Update timestamp
        db_case.updated_at = datetime.utcnow()
        
        # Persist changes
        self.db.commit()
        self.db.refresh(db_case)
        
        # Convert to domain model
        return self._to_domain(db_case)
    
    def _to_domain(self, db_case: CaseModel) -> Case:
        """
        Convert SQLAlchemy model to domain model.
        
        Args:
            db_case: SQLAlchemy case model
            
        Returns:
            Case: Domain model
        """
        return Case(
            id=db_case.id,
            target_taxon=db_case.target_taxon,
            observation_date=db_case.observation_date,
            detection_site_id=db_case.detection_site_id,
            status=CaseStatus(db_case.status),
            created_at=db_case.created_at,
            updated_at=db_case.updated_at,
            metadata=db_case.meta
        )
