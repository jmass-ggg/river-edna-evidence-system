"""
Scientific engine protocol interfaces.

These define the contracts for scientific engines without implementing
the final scientific algorithms. Implementations should return UNKNOWN
or INSUFFICIENT_DATA when validated logic is not yet available.
"""

from typing import Protocol, Any
from uuid import UUID

from app.domain.models import (
    RiverReach,
    Case,
    CandidateZone,
    EvidenceItem,
    EvidenceAssessment,
    SamplingSite,
    DecisionTrace,
    CandidateGenerationResult,
)
from app.domain.enums import SamplingDecisionStatus


class HydrologyEngine(Protocol):
    """
    Performs river network analysis using HydroRIVERS data.
    
    Provides deterministic graph operations. Distance calculations
    and reachability checks use validated preflight artifacts.
    
    All methods should raise appropriate exceptions for invalid HYRIV_IDs
    or when operations cannot be completed.
    """
    
    def get_reach(self, hyriv_id: int) -> RiverReach:
        """
        Retrieve reach metadata by HYRIV_ID.
        
        Args:
            hyriv_id: The HydroRIVERS reach identifier
            
        Returns:
            RiverReach with all metadata (next_down, length_km, upland_skm, dis_av_cms)
            
        Raises:
            ValueError: If HYRIV_ID does not exist in loaded network
        """
        ...
    
    def get_upstream_reaches(self, hyriv_id: int) -> list[int]:
        """
        Return all reach IDs that flow toward the specified reach.
        
        Args:
            hyriv_id: The target reach identifier
            
        Returns:
            List of HYRIV_IDs that are upstream of the target (may be empty)
            
        Raises:
            ValueError: If HYRIV_ID does not exist in loaded network
        """
        ...
    
    def get_downstream_path(
        self,
        start_hyriv_id: int,
        stop_hyriv_id: int | None = None
    ) -> list[int]:
        """
        Return ordered reach IDs from start to stop (or terminus).
        
        Follows NEXT_DOWN relationships to build the path.
        
        Args:
            start_hyriv_id: Starting reach identifier
            stop_hyriv_id: Optional stopping reach identifier (if None, goes to terminus)
            
        Returns:
            Ordered list of HYRIV_IDs from start to stop/terminus (includes both endpoints)
            
        Raises:
            ValueError: If start or stop HYRIV_ID does not exist in loaded network
            ValueError: If stop is not downstream of start
        """
        ...
    
    def is_upstream(self, source_hyriv_id: int, target_hyriv_id: int) -> bool:
        """
        Check if source reach flows toward target reach.
        
        Args:
            source_hyriv_id: Potential upstream reach
            target_hyriv_id: Potential downstream reach
            
        Returns:
            True if source is upstream of target, False otherwise
            
        Raises:
            ValueError: If either HYRIV_ID does not exist in loaded network
        """
        ...
    
    def first_common_downstream(
        self,
        hyriv_id_a: int,
        hyriv_id_b: int
    ) -> int | None:
        """
        Find where two branches converge.
        
        Returns the first reach that is downstream of both input reaches.
        
        Args:
            hyriv_id_a: First reach identifier
            hyriv_id_b: Second reach identifier
            
        Returns:
            HYRIV_ID of convergence point, or None if branches never converge
            
        Raises:
            ValueError: If either HYRIV_ID does not exist in loaded network
        """
        ...
    
    def network_distance_km(
        self,
        from_hyriv_id: int,
        to_hyriv_id: int
    ) -> float | None:
        """
        Calculate network distance using LENGTH_KM.
        
        IMPORTANT: This uses validated methodology from preflight artifacts.
        Sums LENGTH_KM along the downstream path from source to target.
        
        Args:
            from_hyriv_id: Source reach identifier
            to_hyriv_id: Target reach identifier
            
        Returns:
            Distance in kilometers, or None if reaches are not connected
            (i.e., from is not upstream of to)
            
        Raises:
            ValueError: If either HYRIV_ID does not exist in loaded network
        """
        ...
    
    def zone_can_contribute_to_site(
        self,
        zone_reaches: list[int],
        site_hyriv_id: int
    ) -> bool:
        """
        Check if any reach in zone flows to site.
        
        Args:
            zone_reaches: List of HYRIV_IDs comprising the zone
            site_hyriv_id: The site reach identifier
            
        Returns:
            True if at least one zone reach is upstream of site, False otherwise
            
        Raises:
            ValueError: If site_hyriv_id does not exist in loaded network
            ValueError: If any zone reach does not exist in loaded network
        """
        ...



class EvidenceCompatibilityEngine(Protocol):
    """
    Evaluates evidence compatibility with candidate zone hypotheses.
    
    IMPORTANT: This is an interface. Implementations should return UNKNOWN
    when no validated scientific rule applies. The backend provides the
    infrastructure; scientific methodology remains for independent review.
    
    All methods should handle missing data gracefully and provide clear
    provenance for assessments.
    """
    
    def assess_evidence_for_zone(
        self,
        case: Case,
        zone: CandidateZone,
        evidence_items: list[EvidenceItem],
        scientific_rules: list[dict[str, Any]]
    ) -> list[EvidenceAssessment]:
        """
        Assess how each evidence item relates to the hypothesis that
        the zone is the source of the eDNA detection.
        
        For each evidence item, applies relevant scientific rules to determine
        if the evidence SUPPORTS, CONTRADICTS, is NEUTRAL toward, or has
        UNKNOWN relationship with the hypothesis.
        
        Args:
            case: The investigation case
            zone: The candidate zone being evaluated as potential source
            evidence_items: List of evidence items to assess
            scientific_rules: List of validated scientific rules for interpretation
            
        Returns:
            List of EvidenceAssessment objects, one per evidence item.
            When no rule applies to an evidence item, returns assessment with
            compatibility=UNKNOWN and rule_id=None.
            
        Note:
            Scientific rules format is intentionally flexible to allow
            future scientific reviewer to define appropriate structure.
            Current scaffold returns UNKNOWN for all evidence.
        """
        ...
    
    def summarize_zone_assessment(
        self,
        assessments: list[EvidenceAssessment]
    ) -> dict[str, int]:
        """
        Summarize assessment counts by compatibility status.
        
        Provides a quick overview of how evidence relates to a zone hypothesis.
        
        Args:
            assessments: List of evidence assessments for a zone
            
        Returns:
            Dictionary with counts: {
                "supports": <count>,
                "contradicts": <count>,
                "neutral": <count>,
                "unknown": <count>
            }
            
        Note:
            Keys are lowercase for JSON serialization consistency.
            Values sum to len(assessments).
        """
        ...



class SamplingDecisionEngine(Protocol):
    """
    Evaluates sampling site candidates and recommends priorities.
    
    IMPORTANT: This is an interface. When final scoring criteria are not
    defined, implementations should return INSUFFICIENT_DATA rather than
    inventing criteria. The backend provides the infrastructure; scientific
    methodology remains for independent review.
    
    All methods should handle missing data gracefully and provide clear
    audit trails for decisions.
    """
    
    def evaluate_candidates(
        self,
        case: Case,
        zones: list[CandidateZone],
        candidate_sites: list[SamplingSite],
        hydrology_engine: "HydrologyEngine"
    ) -> list[dict[str, Any]]:
        """
        Evaluate each candidate site's discrimination power.
        
        Analyzes each candidate site to determine how well it would help
        discriminate between competing zone hypotheses. Evaluation considers
        network position, zone reachability, and potential to provide
        discriminating evidence.
        
        Args:
            case: The investigation case
            zones: List of candidate zones being evaluated
            candidate_sites: List of potential sampling sites
            hydrology_engine: Engine for network analysis
            
        Returns:
            List of evaluation records, one per candidate site.
            Each record is a dictionary containing:
            - "site_id": UUID of the evaluated site
            - "scores": Dict of evaluation scores (format TBD by scientific reviewer)
            - "rationale": String explaining the evaluation
            - Additional fields as needed for decision-making
            
        Note:
            The evaluation structure is intentionally flexible to allow
            the scientific reviewer to define appropriate scoring metrics.
            Current scaffold returns minimal evaluations with INSUFFICIENT_DATA
            indicators.
        """
        ...
    
    def make_recommendation(
        self,
        evaluations: list[dict[str, Any]]
    ) -> tuple[SamplingDecisionStatus, list[UUID], str]:
        """
        Compare evaluations and recommend site(s).
        
        Analyzes evaluation results to determine which sites, if any, should
        be prioritized for sampling. Returns a clear status indicating the
        decision outcome.
        
        Args:
            evaluations: List of site evaluation records from evaluate_candidates
            
        Returns:
            Tuple of (status, recommended_site_ids, rationale):
            - status: Decision status indicating outcome type
            - recommended_site_ids: List of recommended site UUIDs (may be empty)
            - rationale: String explaining the recommendation
            
        Status interpretation:
            - RECOMMEND: One or more sites clearly preferred based on criteria
            - TIE: Multiple sites have equal value; all returned in recommendations
            - ABSTAIN: No basis for preference among candidates
            - INSUFFICIENT_DATA: Cannot evaluate with available data/criteria
            
        Note:
            When scientific scoring criteria are undefined or incomplete,
            this method MUST return INSUFFICIENT_DATA rather than inventing
            recommendations. The backend enforces this boundary between
            engineering and scientific methodology.
        """
        ...
    
    def create_decision_trace(
        self,
        case: Case,
        evaluations: list[dict[str, Any]],
        status: SamplingDecisionStatus,
        recommended_site_ids: list[UUID],
        decision_id: UUID
    ) -> DecisionTrace:
        """
        Create audit trail for decision.
        
        Constructs a comprehensive trace showing what data, rules, and
        analyses informed the sampling decision. Essential for reproducibility
        and scientific review.
        
        Args:
            case: The investigation case
            evaluations: Site evaluation records
            status: The decision status
            recommended_site_ids: Sites that were recommended (if any)
            decision_id: UUID of the decision being traced
            
        Returns:
            DecisionTrace with complete audit information including:
            - evidence_used: UUIDs of evidence items used
            - rules_applied: IDs of scientific rules applied
            - hydrology_checks: Network operations performed
            - assumptions: Assumptions made during evaluation
            - limitations: Known limitations of the analysis
            
        Note:
            All decision traces should be honest about assumptions and
            limitations. If criteria are incomplete, this should be
            documented in the limitations field.
        """
        ...


class CandidateSiteGenerator(Protocol):
    """Protocol for deterministic topology candidate generation."""

    def generate(
        self,
        zones: list[CandidateZone],
        site_a_hyriv_id: int,
        site_a_fraction: float = 1.0,
        candidate_hyriv_ids: list[int] | None = None,
    ) -> CandidateGenerationResult:
        """Generate representative candidates from validated upstream reaches."""
        ...
