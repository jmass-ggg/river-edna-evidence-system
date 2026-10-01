"""
Evidence service for business logic orchestration.

Coordinates EvidenceRepository and EvidenceCompatibilityEngine to manage
evidence collection and assessment.
"""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException

from app.repositories.evidence import EvidenceRepository, EvidenceNotFoundError
from app.scientific.interfaces import EvidenceCompatibilityEngine
from app.domain.models import (
    Case,
    CandidateZone,
    EvidenceItem,
    EvidenceAssessment,
)


class EvidenceService:
    """
    Service for evidence-related business logic.
    
    Orchestrates evidence operations, coordinates repository access
    and evidence compatibility engine, and enforces business rules.
    """
    
    def __init__(
        self,
        evidence_repository: EvidenceRepository,
        evidence_engine: EvidenceCompatibilityEngine
    ):
        """
        Initialize the service with required dependencies.
        
        Args:
            evidence_repository: Repository for evidence data access
            evidence_engine: Engine for evidence compatibility assessment
        """
        self.evidence_repository = evidence_repository
        self.evidence_engine = evidence_engine
    
    def add_evidence(
        self,
        case_id: UUID,
        evidence_type: str,
        source: str,
        value: Any,
        observed_at: Optional[datetime] = None,
        quality: Optional[str] = None,
        provenance: Optional[dict] = None
    ) -> EvidenceItem:
        """
        Add a new evidence item to a case.
        
        Args:
            case_id: UUID of the case this evidence belongs to
            evidence_type: Type/category of evidence
            source: Origin of the evidence
            value: The evidence value
            observed_at: When the evidence was observed (optional)
            quality: Quality indicator (optional)
            provenance: Provenance tracking metadata (optional)
            
        Returns:
            EvidenceItem: Created evidence item as domain model
            
        Raises:
            HTTPException: 400 if validation fails, 404 if case not found
        """
        # Validate required fields
        if not evidence_type or not evidence_type.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "ValidationError",
                    "message": "evidence_type is required and cannot be empty",
                    "field": "evidence_type"
                }
            )
        
        if not source or not source.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "ValidationError",
                    "message": "source is required and cannot be empty",
                    "field": "source"
                }
            )
        
        if value is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "ValidationError",
                    "message": "value is required",
                    "field": "value"
                }
            )
        
        # Attempt to add evidence
        try:
            evidence = self.evidence_repository.add_evidence(
                case_id=case_id,
                evidence_type=evidence_type.strip(),
                source=source.strip(),
                value=value,
                observed_at=observed_at,
                quality=quality,
                provenance=provenance
            )
            return evidence
        except ValueError as e:
            # Case not found
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "NotFoundError",
                    "message": str(e),
                    "resource_type": "Case",
                    "resource_id": str(case_id)
                }
            )
    
    def get_evidence_for_case(self, case_id: UUID) -> list[EvidenceItem]:
        """
        Retrieve all evidence items for a case.
        
        Args:
            case_id: UUID of the case
            
        Returns:
            list[EvidenceItem]: List of evidence items as domain models
        """
        evidence_items = self.evidence_repository.get_evidence_by_case(case_id)
        return evidence_items
    
    def assess_evidence_for_zones(
        self,
        case: Case,
        zones: list[CandidateZone],
        scientific_rules: Optional[list[dict[str, Any]]] = None
    ) -> dict[str, dict[str, Any]]:
        """
        Assess evidence compatibility for all candidate zones.
        
        Retrieves evidence for the case and evaluates each zone hypothesis
        against all evidence items using the evidence compatibility engine.
        
        Args:
            case: The investigation case
            zones: List of candidate zones to assess
            scientific_rules: List of validated scientific rules (optional)
            
        Returns:
            Dictionary mapping zone labels to assessment results:
            {
                "Z1": {
                    "zone_id": UUID,
                    "assessments": [EvidenceAssessment, ...],
                    "summary": {"supports": N, "contradicts": M, ...}
                },
                ...
            }
        """
        # Retrieve evidence for the case
        evidence_items = self.evidence_repository.get_evidence_by_case(case.id)
        
        # Use empty list if no rules provided
        rules = scientific_rules or []
        
        # Assess each zone
        results = {}
        for zone in zones:
            # Get assessments from engine
            assessments = self.evidence_engine.assess_evidence_for_zone(
                case=case,
                zone=zone,
                evidence_items=evidence_items,
                scientific_rules=rules
            )
            
            # Get summary from engine
            summary = self.evidence_engine.summarize_zone_assessment(assessments)
            
            # Store results
            results[zone.label] = {
                "zone_id": zone.id,
                "assessments": assessments,
                "summary": summary
            }
        
        return results
