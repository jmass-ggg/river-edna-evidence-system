"""
Domain enumerations for the eDNA Evidence Investigator system.

These enumerations provide type-safe constants for domain concepts
and ensure consistency across the system.
"""

from enum import Enum


class EvidenceCompatibility(str, Enum):
    """
    Compatibility status for evidence with respect to a hypothesis.
    
    - SUPPORTS: Evidence is consistent with the hypothesis
    - CONTRADICTS: Evidence is inconsistent with the hypothesis
    - NEUTRAL: Evidence neither supports nor contradicts the hypothesis
    - UNKNOWN: No validated scientific rule can assess this evidence
    """
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class HypothesisStatus(str, Enum):
    """
    Overall status of a hypothesis based on cumulative evidence.
    
    - SUPPORTED: Evidence strongly supports the hypothesis
    - POSSIBLE: Hypothesis remains viable but not strongly supported
    - WEAKENED: Evidence has reduced confidence in the hypothesis
    - CONFLICTING: Evidence both supports and contradicts the hypothesis
    - ELIMINATED: Evidence rules out the hypothesis
    - UNKNOWN: Insufficient data to assess hypothesis status
    """
    SUPPORTED = "SUPPORTED"
    POSSIBLE = "POSSIBLE"
    WEAKENED = "WEAKENED"
    CONFLICTING = "CONFLICTING"
    ELIMINATED = "ELIMINATED"
    UNKNOWN = "UNKNOWN"


class SamplingDecisionStatus(str, Enum):
    """
    Decision status for sampling site recommendations.
    
    - RECOMMEND: One or more sites are clearly recommended
    - TIE: Multiple sites have equal value
    - ABSTAIN: No basis for preference among candidates
    - INSUFFICIENT_DATA: Cannot evaluate with available data/criteria
    """
    RECOMMEND = "RECOMMEND"
    TIE = "TIE"
    ABSTAIN = "ABSTAIN"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ValidationStatus(str, Enum):
    """
    Validation status for network matches and zone definitions.
    
    - MATCHED: Observation has a validated network crosswalk
    - VERIFIED: Independently verified through multiple methods
    - SUPPORTED: Has supporting evidence from validation checks
    - ASSUMPTION: Assumed to be correct but not independently verified
    - NOT_VERIFIED: Has not been verified
    """
    MATCHED = "MATCHED"
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    ASSUMPTION = "ASSUMPTION"
    NOT_VERIFIED = "NOT_VERIFIED"


class SiteType(str, Enum):
    """
    Type classification for sampling sites.
    
    - DETECTION_SITE: Original location where eDNA was detected
    - BRANCH_SPECIFIC: Site specific to one candidate zone branch
    - SHARED_TRUNK: Site on shared river trunk below multiple zones
    - FOLLOW_UP: Additional site for follow-up sampling
    """
    DETECTION_SITE = "DETECTION_SITE"
    BRANCH_SPECIFIC = "BRANCH_SPECIFIC"
    SHARED_TRUNK = "SHARED_TRUNK"
    FOLLOW_UP = "FOLLOW_UP"


class CaseStatus(str, Enum):
    """
    Investigation case status.
    
    - ACTIVE: Case is currently being investigated
    - UNDER_REVIEW: Case is under scientific review
    - COMPLETED: Investigation is complete
    - ARCHIVED: Case has been archived
    """
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"
