"""Auditable scientific rule catalog.

Only rules supported by the frozen Wigger topology methodology belong here.
The catalog deliberately contains no biological absence, transport,
degradation, abundance, or detection-probability rules.
"""

from copy import deepcopy
from typing import Any


TOPOLOGY_CONTRIBUTION_RULE: dict[str, Any] = {
    "id": "hydrorivers.directed_contribution.v1",
    "version": "1.0.0",
    "name": "Directed HydroRIVERS contribution compatibility",
    "description": (
        "Classifies a zone hypothesis using independently computed directed "
        "reachability from its root reach to a sampling reach."
    ),
    "condition": {
        "evidence_type": "directed_hydrological_connectivity",
        "required_value_fields": [
            "zone_root_hyriv_id",
            "site_hyriv_id",
            "can_contribute",
            "network_validation_status",
        ],
        "accepted_network_statuses": ["VERIFIED", "SUPPORTED", "MATCHED"],
    },
    "effect": {
        "can_contribute=true": "SUPPORTS",
        "can_contribute=false": "CONTRADICTS",
        "different_zone_root": "NEUTRAL",
        "missing_or_unverified": "UNKNOWN",
    },
    "reason": (
        "A directed route is necessary for represented-network hydrological "
        "contribution; absence of a route contradicts that contribution path."
    ),
    "provenance/source": [
        "HydroRIVERS NEXT_DOWN directed topology",
        "data_preflight/outputs/upstream_edges.csv",
        "data_preflight/outputs/FINAL_REPORT.md",
    ],
    "limitations": [
        "Reachability is evaluated at mapped-reach resolution.",
        "Connectivity does not establish eDNA transport, persistence, detection, biological presence, or abundance.",
        "CONTRADICTS applies only to represented-network hydrological contribution.",
    ],
    "validation_status": "VERIFIED",
}


RULE_CATALOG = (TOPOLOGY_CONTRIBUTION_RULE,)


TOPOLOGY_STRENGTH_RULE: dict[str, Any] = {
    "id": "hydrorivers.directed_connectivity_strength.v1",
    "version": "1.0.0",
    "name": "Directed HydroRIVERS connectivity evidence strength",
    "description": (
        "Assesses only the strength of the mapped hydrological-connectivity "
        "claim using validation and topology-completeness metadata."
    ),
    "evidence_type": "directed_hydrological_connectivity",
    "criteria": [
        "network mapping validation",
        "zone root validation",
        "complete directed topology evaluation",
        "validated graph coverage",
    ],
    "effect": {
        "all_criteria_validated": "HIGH",
        "topology_complete_graph_coverage_unstated": "MEDIUM",
        "unverified_or_missing_topology": "LOW",
        "unsupported_evidence_type": "UNASSESSED",
    },
    "provenance/source": [
        "HydroRIVERS NEXT_DOWN directed topology",
        "validated Wigger graph boundary",
    ],
    "limitations": [
        "Strength applies only to the hydrological-connectivity claim.",
        "It is not the probability that the species occurs at a location.",
        "It does not assess transport, decay, abundance, assay quality, or detection probability.",
    ],
    "validation_status": "VERIFIED",
}


STRENGTH_RULE_CATALOG = (TOPOLOGY_STRENGTH_RULE,)


def get_rule_catalog() -> list[dict[str, Any]]:
    """Return a defensive copy suitable for engine evaluation and tracing."""
    return deepcopy(list(RULE_CATALOG))


def get_strength_rule_catalog() -> list[dict[str, Any]]:
    """Return independently versioned claim-specific strength rules."""
    return deepcopy(list(STRENGTH_RULE_CATALOG))
