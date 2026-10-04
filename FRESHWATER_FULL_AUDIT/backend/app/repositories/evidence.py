"""
Evidence repository for data access operations.

Hides SQLAlchemy details and returns domain models.
"""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvidenceItemModel, CaseModel
from app.domain.models import EvidenceItem


class EvidenceNotFoundError(Exception):
    """Raised when evidence is not found in the database."""
    def __init__(self, evidence_id: UUID):
        self.evidence_id = evidence_id
        super().__init__(f"Evidence with ID {evidence_id} not found")


class EvidenceRepository:
    """
    Repository for Evidence data access operations.
    
    Handles CRUD operations for evidence items and hides SQLAlchemy details
    from the service layer.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the repository with a database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def add_evidence(
        self,
        case_id: UUID,
        evidence_type: str,
        source: str,
        value: Any,
        observed_at: Optional[datetime] = None,
        quality: Optional[str] = None,
        provenance: Optional[dict] = None,
        commit: bool = True,
    ) -> EvidenceItem:
        """
        Add a new evidence item to a case and persist to database.
        
        Args:
            case_id: UUID of the case this evidence belongs to
            evidence_type: Type/category of evidence
            source: Origin of the evidence
            value: The evidence value (will be stored as JSONB)
            observed_at: When the evidence was observed (optional)
            quality: Quality indicator (optional)
            provenance: Provenance tracking metadata (optional)
            
        Returns:
            EvidenceItem: Created evidence item as domain model
            
        Raises:
            ValueError: If case_id does not exist
        """
        # Verify case exists
        case = self.db.get(CaseModel, case_id)
        if not case:
            raise ValueError(f"Case with ID {case_id} not found")
        
        # Create database model
        db_evidence = EvidenceItemModel(
            case_id=case_id,
            evidence_type=evidence_type,
            source=source,
            value=value,
            observed_at=observed_at,
            quality=quality,
            provenance=provenance or {}
        )
        
        # Persist to database
        self.db.add(db_evidence)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        self.db.refresh(db_evidence)
        
        # Convert to domain model
        return self._to_domain(db_evidence)
    
    def get_evidence_by_case(self, case_id: UUID) -> list[EvidenceItem]:
        """
        Retrieve all evidence items for a case.
        
        Args:
            case_id: UUID of the case
            
        Returns:
            list[EvidenceItem]: List of evidence items as domain models
        """
        # Build query
        query = select(EvidenceItemModel).where(
            EvidenceItemModel.case_id == case_id
        )
        
        # Order by creation date (oldest first)
        query = query.order_by(EvidenceItemModel.created_at.asc())
        
        # Execute query
        result = self.db.execute(query)
        db_evidence_items = result.scalars().all()
        
        # Convert to domain models
        return [self._to_domain(db_item) for db_item in db_evidence_items]
    
    def get_evidence_by_id(self, evidence_id: UUID) -> EvidenceItem:
        """
        Retrieve a single evidence item by its ID.
        
        Args:
            evidence_id: UUID of the evidence item to retrieve
            
        Returns:
            EvidenceItem: The evidence item as domain model
            
        Raises:
            EvidenceNotFoundError: If evidence item does not exist
        """
        db_evidence = self.db.get(EvidenceItemModel, evidence_id)
        
        if not db_evidence:
            raise EvidenceNotFoundError(evidence_id)
        
        return self._to_domain(db_evidence)
    
    def _to_domain(self, db_evidence: EvidenceItemModel) -> EvidenceItem:
        """
        Convert SQLAlchemy model to domain model.
        
        Args:
            db_evidence: SQLAlchemy evidence model
            
        Returns:
            EvidenceItem: Domain model
        """
        return EvidenceItem(
            id=db_evidence.id,
            case_id=db_evidence.case_id,
            evidence_type=db_evidence.evidence_type,
            source=db_evidence.source,
            value=db_evidence.value,
            observed_at=db_evidence.observed_at,
            quality=db_evidence.quality,
            provenance=db_evidence.provenance,
            created_at=db_evidence.created_at
        )
