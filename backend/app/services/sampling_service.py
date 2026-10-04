"""
Sampling service for business logic orchestration.

Coordinates SamplingRepository, SamplingDecisionEngine, and HydrologyEngine
to manage sampling sites and decision-making.
"""
from typing import Optional
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import DecisionTraceModel

from app.repositories.sampling import (
    SamplingRepository,
    SiteNotFoundError,
    DecisionNotFoundError,
)
from app.scientific.interfaces import (
    SamplingDecisionEngine,
    HydrologyEngine,
    CandidateSiteGenerator,
)
from app.domain.models import (
    Case,
    CandidateZone,
    SamplingSite,
    SamplingDecision,
    DecisionTrace,
    CandidateGenerationResult,
)
from app.domain.enums import (
    SiteType,
    ValidationStatus,
)


def detection_fraction(site, frozen_fraction):
    if site.hyriv_id == 20446064 and site.metadata.get("network_source", "").endswith("site_a.json"):
        return frozen_fraction
    selected = site.metadata.get("selected_match", {})
    fraction = selected.get("fraction_along_reach")
    if site.metadata.get("review_confirmed") and isinstance(fraction, (float, int)) and 0 <= fraction <= 1:
        return float(fraction)
    return 0.5  # Explicit representative assumption, never a measured location.


class SamplingService:
    """
    Service for sampling-related business logic.
    
    Orchestrates sampling operations, coordinates repository and engines,
    and enforces business rules and validation.
    """
    
    def __init__(
        self,
        sampling_repository: SamplingRepository,
        sampling_engine: SamplingDecisionEngine,
        hydrology_engine: HydrologyEngine,
        candidate_generator: CandidateSiteGenerator | None = None,
        site_a_fraction: float = 1.0,
    ):
        """
        Initialize the service with required dependencies.
        
        Args:
            sampling_repository: Repository for sampling data access
            sampling_engine: Engine for sampling decision-making
            hydrology_engine: Engine for river network analysis
        """
        self.sampling_repository = sampling_repository
        self.sampling_engine = sampling_engine
        self.hydrology_engine = hydrology_engine
        self.candidate_generator = candidate_generator
        self.site_a_fraction = site_a_fraction
    
    def register_sampling_site(
        self,
        label: str,
        latitude: float,
        longitude: float,
        hyriv_id: int,
        site_type: SiteType,
        validation_status: ValidationStatus,
        case_id: Optional[UUID] = None,
        network_latitude: Optional[float] = None,
        network_longitude: Optional[float] = None,
        snap_distance_m: Optional[float] = None,
        role: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> SamplingSite:
        """
        Register a new sampling site.
        
        Args:
            label: Human-readable site label
            latitude: Observation latitude in decimal degrees
            longitude: Observation longitude in decimal degrees
            hyriv_id: HydroRIVERS reach ID
            site_type: Type of sampling site
            validation_status: Validation status of network match
            case_id: UUID of associated case (optional)
            network_latitude: Snapped network latitude (optional)
            network_longitude: Snapped network longitude (optional)
            snap_distance_m: Distance from observation to network (optional)
            role: Functional role in sampling strategy (optional)
            metadata: Additional site-specific metadata (optional)
            
        Returns:
            SamplingSite: Created site as domain model
            
        Raises:
            HTTPException: 400 if validation fails, 404 if case or HYRIV_ID not found
        """
        # Validate required fields
        if not label or not label.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "ValidationError",
                    "message": "label is required and cannot be empty",
                    "field": "label"
                }
            )
        
        # Validate HYRIV_ID exists in network
        try:
            self.hydrology_engine.get_reach(hyriv_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "InvalidHyrivIdError",
                    "message": f"HYRIV_ID {hyriv_id} not found in loaded network data",
                    "hyriv_id": hyriv_id
                }
            )
        
        # Attempt to create site
        from app.scientific.data_loader import WiggerPreflightLoader
        from config import config
        submitted = {
            "validation_status": validation_status.value,
            "network_latitude": network_latitude, "network_longitude": network_longitude,
            "snap_distance_m": snap_distance_m, "metadata": metadata or {},
        }
        try:
            validation = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR).sampling_site_reference(
                latitude, longitude, hyriv_id,
            )
        except (ValueError, OSError, KeyError) as exc:
            validation = {"validation_status": "NOT_VERIFIED", "metadata": {
                "validation_method": "reference_validation_unavailable",
                "validation_reason": f"Trusted reference validation unavailable: {exc}",
            }}
        if role == "GENERATED_REPRESENTATIVE":
            raise HTTPException(status_code=422, detail="Generated representative roles are server-controlled")
        try:
            site = self.sampling_repository.create_site(
                label=label.strip(),
                latitude=latitude,
                longitude=longitude,
                hyriv_id=hyriv_id,
                site_type=site_type,
                validation_status=ValidationStatus(validation["validation_status"]),
                case_id=case_id,
                network_latitude=validation.get("network_latitude"),
                network_longitude=validation.get("network_longitude"),
                snap_distance_m=validation.get("snap_distance_m"),
                role=role,
                metadata={"submitted_metadata": submitted, **validation["metadata"]}
            )
            return site
        except ValueError as e:
            # Case not found
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "NotFoundError",
                    "message": str(e),
                    "resource_type": "Case",
                    "resource_id": str(case_id) if case_id else None
                }
            )
    
    def get_sampling_sites(self, case_id: UUID) -> list[SamplingSite]:
        """
        Retrieve all sampling sites for a case.
        
        Args:
            case_id: UUID of the case
            
        Returns:
            list[SamplingSite]: List of sampling sites as domain models
        """
        sites = self.sampling_repository.get_sites_by_case(case_id)
        return sites
    
    def evaluate_sampling_candidates(
        self,
        case: Case,
        zones: list[CandidateZone],
        candidate_sites: list[SamplingSite],
        commit: bool = True,
    ) -> tuple[SamplingDecision, DecisionTrace]:
        """
        Evaluate sampling candidates and make recommendation.
        
        Coordinates the sampling decision engine to evaluate all candidate
        sites, make a recommendation, and create an audit trail.
        
        Args:
            case: The investigation case
            zones: List of candidate zones being evaluated
            candidate_sites: List of potential sampling sites
            
        Returns:
            tuple[SamplingDecision, DecisionTrace]: Decision and trace as domain models
            
        Raises:
            HTTPException: 400 if validation fails
        """
        # Validate inputs
        if not zones:
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "ValidationError",
                    "message": "At least one candidate zone is required for evaluation",
                    "field": "zones"
                }
            )
        
        if not candidate_sites:
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "ValidationError",
                    "message": "At least one candidate site is required for evaluation",
                    "field": "candidate_sites"
                }
            )
        
        # Evaluate candidates using sampling engine
        evaluations = self.sampling_engine.evaluate_candidates(
            case=case,
            zones=zones,
            candidate_sites=candidate_sites,
            hydrology_engine=self.hydrology_engine
        )
        
        # Make recommendation
        status, recommended_site_ids, rationale = self.sampling_engine.make_recommendation(
            evaluations
        )
        
        # Save decision and trace to database
        decision, trace = self.sampling_repository.save_decision(
            case_id=case.id,
            status=status,
            recommended_site_ids=recommended_site_ids,
            rationale=rationale,
            evidence_used=[],  # Will be populated by engine's trace creation
            rules_applied=[],
            hydrology_checks=[],
            assumptions=[],
            limitations=[],
            commit=False,
        )
        
        # Create detailed trace using sampling engine
        detailed_trace = self.sampling_engine.create_decision_trace(
            case=case,
            evaluations=evaluations,
            status=status,
            recommended_site_ids=recommended_site_ids,
            decision_id=decision.id
        )

        # save_decision creates the trace atomically with the decision. Replace
        # its initial placeholders with the engine-produced audit content.
        db_trace = self.sampling_repository.db.scalar(
            select(DecisionTraceModel).where(
                DecisionTraceModel.decision_id == decision.id
            )
        )
        db_trace.evidence_used = detailed_trace.evidence_used
        db_trace.rules_applied = detailed_trace.rules_applied
        db_trace.hydrology_checks = detailed_trace.hydrology_checks
        db_trace.assumptions = detailed_trace.assumptions
        db_trace.limitations = detailed_trace.limitations
        if commit:
            self.sampling_repository.db.commit()
        else:
            self.sampling_repository.db.flush()
        
        # Return decision with detailed trace
        return decision, detailed_trace

    def registered_candidate_distances(self, candidate_sites, detection_site):
        """Describe directed LENGTH_KM distances, without altering candidate scores.

        Frozen coordinates identify documented reference positions. Other
        registered locations use an explicitly labelled reach-midpoint estimate;
        arbitrary submitted fractions are not validated positions.
        """
        from math import isclose
        from app.scientific.data_loader import WiggerPreflightLoader
        from config import config

        reference_rows, provenance, reference_error = [], {}, None
        target_fraction = 0.5
        try:
            loader = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
            hashes = loader.validate_frozen_reference()
            reference_rows = loader.load_sampling_sites().to_dict(orient="records")
            target_fraction = float(loader.load_site_a_snap_validation()["snapped_coordinate"]["fraction_along_reach"])
            if not 0 <= target_fraction <= 1:
                raise ValueError("Frozen Site A reach fraction is invalid")
            provenance = {"source": str(loader.data_dir / "candidate_sampling_sites.csv"),
                          "site_a_position_source": str(loader.data_dir / "site_a_snap_validation.json"),
                          "method_source": "data_preflight/scripts/generate_candidate_sites.py",
                          "artifact_sha256": hashes}
        except (ValueError, OSError, KeyError) as exc:
            reference_rows = []
            reference_error = f"Frozen distance reference unavailable: {exc}"

        def match(site):
            return next((row for row in reference_rows
                         if int(row["HYRIV_ID"]) == site.hyriv_id
                         and abs(float(row["latitude"]) - site.latitude) <= 1e-7
                         and abs(float(row["longitude"]) - site.longitude) <= 1e-7), None)

        target = match(detection_site)
        target_is_a = target is not None and target["site"] == "A"
        result = {}
        for site in candidate_sites:
            source = match(site)
            from_fraction = target_fraction if source is not None and source["site"] == "A" else 0.5
            to_fraction = target_fraction if target_is_a else 0.5
            validated = source is not None and target_is_a
            def reviewed_fraction(location):
                selected = location.metadata.get("selected_match", {})
                fraction = selected.get("fraction_along_reach")
                return (float(fraction) if location.metadata.get("review_confirmed")
                        and selected.get("hyriv_id") == location.hyriv_id
                        and type(fraction) in (int, float) and 0 <= fraction <= 1 else None)
            source_fraction, destination_fraction = reviewed_fraction(site), reviewed_fraction(detection_site)
            if source is None and source_fraction is not None:
                from_fraction = source_fraction
            if not target_is_a and destination_fraction is not None:
                to_fraction = destination_fraction
            geometry_derived = not validated and (source is not None or source_fraction is not None) and (target_is_a or destination_fraction is not None)
            method = ("Directed HydroRIVERS LENGTH_KM; frozen reference position to validated Site A snap fraction"
                      if validated else "Estimated directed HydroRIVERS LENGTH_KM; unvalidated positions represented by assumed reach midpoint (fraction 0.5)")
            if geometry_derived:
                method = "Directed HydroRIVERS LENGTH_KM using reviewed, direction-aware geometry fractions; geographic positions are not surveyed chainage."
            info = {"network_distance_km": None, "network_distance_status": "UNAVAILABLE",
                    "network_distance_method": method,
                    "network_distance_provenance": {**provenance, "from_fraction": from_fraction,
                                                    "to_fraction": to_fraction},
                    "network_distance_reason": reference_error}
            if geometry_derived:
                info["network_distance_provenance"] = {"from_fraction": from_fraction, "to_fraction": to_fraction,
                    "candidate_position": site.metadata.get("location_match", {}).get("provenance", provenance if source else {}),
                    "detection_position": detection_site.metadata.get("location_match", {}).get("provenance", provenance if target_is_a else {})}
            try:
                distance = self.hydrology_engine.network_distance_km(
                    site.hyriv_id, detection_site.hyriv_id,
                    from_fraction=from_fraction, to_fraction=to_fraction)
                if distance is None:
                    info["network_distance_reason"] = "No directed downstream path from candidate position to detection position in the loaded network."
                elif validated and not isclose(distance, float(source["network_distance_to_site_a_km"]), abs_tol=1e-8):
                    info["network_distance_reason"] = "Calculated distance conflicts with the frozen reference; reference distance was not overwritten."
                else:
                    info.update(network_distance_km=float(source["network_distance_to_site_a_km"]) if validated else distance,
                                network_distance_status="VALIDATED_REFERENCE" if validated else "GEOMETRY_DERIVED" if geometry_derived else "ESTIMATED",
                                network_distance_reason=None if validated else
                                "Precise validated reach fractions are unavailable for one or both positions; this is a topology estimate, not a measured field distance."
                                + (f" {reference_error}" if reference_error else ""))
                    if geometry_derived:
                        info["network_distance_reason"] = "Reviewed geographic fractions were used; no surveyed field distance or biological origin is implied."
            except (ValueError, KeyError) as exc:
                info["network_distance_reason"] = str(exc)
            result[site.id] = info
        return result

    def generate_sampling_candidates(
        self,
        case: Case,
        zones: list[CandidateZone],
        detection_site: SamplingSite,
    ) -> tuple[CandidateGenerationResult, str, str]:
        """Generate candidates, then evaluate them with the existing engine."""
        if self.candidate_generator is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "type": "CandidateGeneratorUnavailable",
                    "message": "Automatic candidate generation is not configured.",
                },
            )
        result = self.candidate_generator.generate(
            zones=zones,
            site_a_hyriv_id=detection_site.hyriv_id,
            site_a_fraction=detection_fraction(detection_site, self.site_a_fraction),
        )
        generated_sites = [
            SamplingSite(
                id=uuid5(
                    NAMESPACE_URL,
                    f"generated-candidate:{case.id}:{candidate.hyriv_id}",
                ),
                case_id=case.id,
                label=f"Generated {candidate.equivalence_class}",
                latitude=candidate.latitude,
                longitude=candidate.longitude,
                hyriv_id=candidate.hyriv_id,
                site_type=SiteType.FOLLOW_UP,
                validation_status=candidate.validation_status,
                network_latitude=candidate.latitude,
                network_longitude=candidate.longitude,
                role="Topology equivalence-class representative",
                metadata={"status": "COUNTERFACTUAL"},
            )
            for candidate in result.candidates
        ]
        evaluations = self.sampling_engine.evaluate_candidates(
            case=case,
            zones=zones,
            candidate_sites=generated_sites,
            hydrology_engine=self.hydrology_engine,
        )
        status, _, reason = self.sampling_engine.make_recommendation(evaluations)
        return result, status.value, reason
    
    def get_decision_trace(self, decision_id: UUID) -> DecisionTrace:
        """
        Retrieve the decision trace for a sampling decision.
        
        Args:
            decision_id: UUID of the sampling decision
            
        Returns:
            DecisionTrace: The decision trace as domain model
            
        Raises:
            HTTPException: 404 if decision not found
        """
        # Note: This is a placeholder. The actual implementation would need
        # a method in SamplingRepository to retrieve traces by decision_id.
        # For now, we raise a not implemented error as this requires
        # additional repository methods not specified in the current task.
        raise HTTPException(
            status_code=501,
            detail={
                "type": "NotImplementedError",
                "message": "Decision trace retrieval not yet implemented",
                "decision_id": str(decision_id)
            }
        )
