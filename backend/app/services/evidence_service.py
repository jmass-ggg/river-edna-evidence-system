from app.repositories.detection_contexts import belongs, selected_context
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

    @staticmethod
    def qualifying_observation(item) -> bool:
        """Recognize recorded biological observations, without verifying biology."""
        if not item.source or not item.source.strip() or not item.provenance or not isinstance(item.value, dict):
            return False
        value = item.value
        if item.evidence_type == "edna_observation":
            replicates = value.get("replicate_results")
            return bool(isinstance(replicates, list) and replicates
                        and all(result in ("Positive", "Negative", "Invalid") for result in replicates)
                        and any(result != "Invalid" for result in replicates))
        if item.evidence_type == "historical_edna_measurement":
            from math import isfinite
            concentration = value.get("concentration_mol_l")
            return bool(value.get("species") and value.get("date") and value.get("station")
                        and value.get("state") in ("DETECTED", "NOT_DETECTED")
                        and type(concentration) in (int, float) and isfinite(concentration) and concentration >= 0)
        if item.evidence_type == "follow_up_edna_sample":
            count, positive = value.get("replicate_count"), value.get("positive_replicates")
            return bool(type(count) is int and count > 0 and type(positive) is int
                        and 0 <= positive <= count and value.get("assay") and value.get("controls_status")
                        and value.get("sampled_at"))
        return False

    @staticmethod
    def require_observation(evidence_items):
        if not any(EvidenceService.qualifying_observation(item) for item in evidence_items):
            raise HTTPException(status_code=422, detail={
                "type": "IncompleteScientificPrerequisites",
                "message": "A recorded biological observation with source and provenance is required; context and topology alone do not qualify.",
            })
    
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

        if evidence_type == "sampling_field_plan":
            value = self._validate_field_plan(case_id, value)
            if not provenance:
                raise HTTPException(status_code=422, detail={"type": "ValidationError", "message": "Researcher provenance is required"})
        
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

    def _validate_field_plan(self, case_id, value):
        from app.db.models import SamplingDecisionModel, SamplingSiteModel
        if not isinstance(value, dict):
            raise HTTPException(status_code=422, detail={"type": "ValidationError", "message": "Field plan must be an object"})
        try:
            decision_id, site_id = UUID(str(value["decision_id"])), UUID(str(value["site_id"]))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=422, detail={"type": "ValidationError", "message": "Decision and candidate identities are required"}) from exc
        db = self.evidence_repository.db
        decision, site = db.get(SamplingDecisionModel, decision_id), db.get(SamplingSiteModel, site_id)
        if not belongs(db, decision, case_id) or not belongs(db, site, case_id, physical_site=True):
            raise HTTPException(status_code=404, detail={"type": "NotFoundError", "message": "Decision or candidate is unavailable in this investigation"})
        if site.id not in decision.recommended_site_ids:
            raise HTTPException(status_code=409, detail={"type": "ConflictError", "message": "Candidate is not an alternative under the referenced decision"})
        if type(value.get("researcher_selected")) is not bool:
            raise HTTPException(status_code=422, detail={"type": "ValidationError", "message": "researcher_selected must be boolean"})
        notes = {key: value.get(key, "") for key in ("accessibility", "field_restrictions", "practical_observations")}
        if any(not isinstance(note, str) for note in notes.values()) or not any(note.strip() for note in notes.values()):
            raise HTTPException(status_code=422, detail={"type": "ValidationError", "message": "Record at least one practical field observation"})
        return {"decision_id": str(decision.id), "site_id": str(site.id), "hyriv_id": site.hyriv_id,
                "decision_status": decision.status, "candidate_scope": decision.candidate_scope,
                "researcher_selected": value["researcher_selected"], **notes,
                "classification": "RESEARCHER_FIELD_CHOICE_NOT_SCIENTIFIC_RANKING"}
    
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
        self.require_observation(evidence_items)
        
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
            from app.scientific.hypothesis import ConservativeHypothesisStateResolver
            hypothesis_status, hypothesis_reason = ConservativeHypothesisStateResolver().resolve(
                zone, assessments, summary
            )
            
            # Store results
            results[zone.label] = {
                "zone_id": zone.id,
                "assessments": assessments,
                "summary": summary,
                "hypothesis_status": hypothesis_status,
                "hypothesis_reason": hypothesis_reason,
            }
        
        return results
