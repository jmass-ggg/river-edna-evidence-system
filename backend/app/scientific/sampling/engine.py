"""Transparent topology-based sampling decisions."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.domain.enums import SamplingDecisionStatus, ValidationStatus
from app.domain.models import Case, CandidateZone, DecisionTrace, SamplingSite
from app.scientific.interfaces import HydrologyEngine


DISCRIMINATION_RULE_ID = "sampling.topology_pair_separation.v1"


class ScaffoldSamplingDecisionEngine:
    """Rank sites by how many remaining hypothesis pairs they separate.

    For one candidate site, each zone hypothesis predicts either that its root
    can reach the site or that it cannot. If ``r`` of ``n`` roots can reach the
    site, the site separates ``r * (n - r)`` unordered hypothesis pairs.
    This is a topology-only criterion and is not a detection probability.

    The historical class name is retained because services depend on it.
    """

    def evaluate_candidates(
        self,
        case: Case,
        zones: list[CandidateZone],
        candidate_sites: list[SamplingSite],
        hydrology_engine: HydrologyEngine,
    ) -> list[dict[str, Any]]:
        """Calculate reachability signatures and pair separation per site."""
        evaluations: list[dict[str, Any]] = []
        unverified_zones = [
            zone.label
            for zone in zones
            if zone.validation_status == ValidationStatus.NOT_VERIFIED
        ]

        for site in candidate_sites:
            signature: list[int] = []
            reachable_zones: list[str] = []
            hydrology_checks: list[dict[str, Any]] = []
            incomplete_reasons: list[str] = []

            if site.validation_status == ValidationStatus.NOT_VERIFIED:
                incomplete_reasons.append(
                    f"Site {site.label} network state is NOT_VERIFIED"
                )
            if unverified_zones:
                incomplete_reasons.append(
                    "Zone network state is NOT_VERIFIED for "
                    + ", ".join(unverified_zones)
                )

            for zone in zones:
                try:
                    if hasattr(hydrology_engine, "can_contribute"):
                        reachable = hydrology_engine.can_contribute(
                            zone.root_hyriv_id, site.hyriv_id
                        )
                    else:
                        reachable = hydrology_engine.zone_can_contribute_to_site(
                            [zone.root_hyriv_id], site.hyriv_id
                        )
                    signature.append(int(reachable))
                    if reachable:
                        reachable_zones.append(zone.label)
                    hydrology_checks.append(
                        {
                            "type": "directed_zone_root_reachability",
                            "zone_label": zone.label,
                            "zone_root_hyriv_id": zone.root_hyriv_id,
                            "site_label": site.label,
                            "site_hyriv_id": site.hyriv_id,
                            "result": reachable,
                        }
                    )
                except (ValueError, KeyError) as exc:
                    signature.append(0)
                    incomplete_reasons.append(
                        f"Could not evaluate {zone.label} at {site.label}: {exc}"
                    )
                    hydrology_checks.append(
                        {
                            "type": "directed_zone_root_reachability",
                            "zone_label": zone.label,
                            "zone_root_hyriv_id": zone.root_hyriv_id,
                            "site_label": site.label,
                            "site_hyriv_id": site.hyriv_id,
                            "error": str(exc),
                        }
                    )

            hypothesis_count = len(zones)
            reachable_count = sum(signature)
            separated_pairs = (
                reachable_count * (hypothesis_count - reachable_count)
                if hypothesis_count > 1
                else 0
            )
            distinct_outcomes = (
                2
                if 0 < reachable_count < hypothesis_count
                else (1 if hypothesis_count else 0)
            )
            scientifically_complete = not incomplete_reasons and bool(zones)

            evaluations.append(
                {
                    "site_id": site.id,
                    "site_label": site.label,
                    "site_hyriv_id": site.hyriv_id,
                    "remaining_hypotheses": [zone.label for zone in zones],
                    "signature": signature,
                    "reachable_zones": reachable_zones,
                    "hypothesis_count": hypothesis_count,
                    "scores": {
                        "separated_hypothesis_pairs": separated_pairs,
                        "distinct_outcomes": distinct_outcomes,
                    },
                    "scientific_state_valid": scientifically_complete,
                    "incomplete_reasons": incomplete_reasons,
                    "rule_id": DISCRIMINATION_RULE_ID,
                    "hydrology_checks": hydrology_checks,
                    "rationale": (
                        f"Site {site.label} has reachability signature {signature} "
                        f"and separates {separated_pairs} of "
                        f"{hypothesis_count * (hypothesis_count - 1) // 2} "
                        "remaining hypothesis pairs."
                    ),
                }
            )

        return evaluations

    def make_recommendation(
        self,
        evaluations: list[dict[str, Any]],
    ) -> tuple[SamplingDecisionStatus, list[UUID], str]:
        """Choose the strict pair-separation winner, tie, or abstain."""
        if not evaluations:
            return (
                SamplingDecisionStatus.INSUFFICIENT_DATA,
                [],
                "No candidate evaluations are available.",
            )

        incomplete = [
            evaluation
            for evaluation in evaluations
            if not evaluation.get("scientific_state_valid", False)
        ]
        if incomplete:
            reasons = sorted(
                {
                    reason
                    for evaluation in incomplete
                    for reason in evaluation.get("incomplete_reasons", [])
                }
            )
            return (
                SamplingDecisionStatus.INSUFFICIENT_DATA,
                [],
                "Required scientific state is incomplete: " + "; ".join(reasons),
            )

        hypothesis_counts = {
            evaluation.get("hypothesis_count") for evaluation in evaluations
        }
        if len(hypothesis_counts) != 1 or None in hypothesis_counts:
            return (
                SamplingDecisionStatus.INSUFFICIENT_DATA,
                [],
                "Candidate evaluations do not describe one consistent hypothesis set.",
            )

        hypothesis_count = hypothesis_counts.pop()
        if hypothesis_count <= 1:
            return (
                SamplingDecisionStatus.ABSTAIN,
                [],
                "One or fewer hypotheses remain; another site cannot discriminate between hypotheses.",
            )

        best_score = max(
            evaluation["scores"]["separated_hypothesis_pairs"]
            for evaluation in evaluations
        )
        if best_score == 0:
            return (
                SamplingDecisionStatus.ABSTAIN,
                [],
                "No candidate separates any remaining hypothesis pair.",
            )

        winners = [
            evaluation
            for evaluation in evaluations
            if evaluation["scores"]["separated_hypothesis_pairs"] == best_score
        ]
        winner_ids = [evaluation["site_id"] for evaluation in winners]
        if len(winners) == 1:
            return (
                SamplingDecisionStatus.RECOMMEND,
                winner_ids,
                f"{winners[0]['site_label']} strictly maximizes topology-only "
                f"pair separation ({best_score} pairs).",
            )

        return (
            SamplingDecisionStatus.TIE,
            winner_ids,
            "Multiple sites share the maximum topology-only pair separation "
            f"score ({best_score} pairs): "
            + ", ".join(winner["site_label"] for winner in winners),
        )

    def create_decision_trace(
        self,
        case: Case,
        evaluations: list[dict[str, Any]],
        status: SamplingDecisionStatus,
        recommended_site_ids: list[UUID],
        decision_id: UUID,
    ) -> DecisionTrace:
        """Create the auditable trace required for every sampling decision."""
        hydrology_checks = [
            check
            for evaluation in evaluations
            for check in evaluation.get("hydrology_checks", [])
        ]
        evidence_used = sorted(
            {
                evidence_id
                for evaluation in evaluations
                for evidence_id in evaluation.get("evidence_ids", [])
            },
            key=str,
        )
        rules_applied = sorted(
            {
                evaluation["rule_id"]
                for evaluation in evaluations
                if evaluation.get("rule_id")
            }
        )
        limitations = [
            "Reachability is a mapped-network relation, not eDNA detection probability.",
            "The criterion compares binary outcomes and does not model transport, decay, abundance, field access, or analytical error.",
        ]
        if status == SamplingDecisionStatus.INSUFFICIENT_DATA:
            limitations.append("Required validated network state was incomplete.")
        if status == SamplingDecisionStatus.ABSTAIN:
            limitations.append("Available candidates provide no comparative discrimination.")

        return DecisionTrace(
            decision_id=decision_id,
            evidence_used=evidence_used,
            rules_applied=rules_applied,
            hydrology_checks=hydrology_checks,
            assumptions=[
                "The supplied zones are the remaining hypotheses.",
                "Each hypothesis is represented by its validated root reach.",
                "A site outcome is binary directed reachability at HydroRIVERS reach resolution.",
            ],
            limitations=limitations,
            created_at=datetime.now(timezone.utc),
        )
