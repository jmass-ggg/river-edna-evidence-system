"""Deterministic evidence compatibility evaluation."""

from typing import Any

from app.domain.enums import EvidenceCompatibility
from app.domain.models import Case, CandidateZone, EvidenceItem, EvidenceAssessment
from app.scientific.rules.catalog import get_rule_catalog


class EvidenceCompatibilityEngineImpl:
    """Apply only validated catalog rules; leave unsupported evidence UNKNOWN."""

    def assess_evidence_for_zone(
        self,
        case: Case,
        zone: CandidateZone,
        evidence_items: list[EvidenceItem],
        scientific_rules: list[dict[str, Any]],
    ) -> list[EvidenceAssessment]:
        """Assess each evidence item for one candidate-zone hypothesis."""
        rules = scientific_rules or get_rule_catalog()
        topology_rule = next(
            (
                rule
                for rule in rules
                if rule.get("id") == "hydrorivers.directed_contribution.v1"
                and rule.get("validation_status") == "VERIFIED"
            ),
            None,
        )
        assessments: list[EvidenceAssessment] = []

        for evidence in evidence_items:
            compatibility = EvidenceCompatibility.UNKNOWN
            rule_id = None
            applied_rule = None
            reason = (
                f"No validated scientific rule applies to evidence type "
                f"'{evidence.evidence_type}'."
            )

            if (
                topology_rule is not None
                and evidence.evidence_type == "directed_hydrological_connectivity"
            ):
                value = evidence.value
                required = topology_rule["condition"]["required_value_fields"]
                if not isinstance(value, dict) or any(
                    field not in value for field in required
                ):
                    reason = (
                        "Directed-connectivity evidence is incomplete; required "
                        f"fields are {required}."
                    )
                elif value["zone_root_hyriv_id"] != zone.root_hyriv_id:
                    compatibility = EvidenceCompatibility.NEUTRAL
                    rule_id = topology_rule["id"]
                    applied_rule = topology_rule
                    reason = (
                        f"Connectivity evidence targets zone root "
                        f"{value['zone_root_hyriv_id']}, not {zone.root_hyriv_id}; "
                        f"it is neutral for zone {zone.label}."
                    )
                elif value["network_validation_status"] not in topology_rule[
                    "condition"
                ]["accepted_network_statuses"]:
                    reason = (
                        "Directed connectivity is not sufficiently validated; "
                        "compatibility remains UNKNOWN."
                    )
                elif not isinstance(value["can_contribute"], bool):
                    reason = (
                        "Directed-connectivity evidence must provide a boolean "
                        "can_contribute value."
                    )
                else:
                    rule_id = topology_rule["id"]
                    applied_rule = topology_rule
                    if value["can_contribute"]:
                        compatibility = EvidenceCompatibility.SUPPORTS
                        reason = (
                            f"Zone {zone.label} has a directed HydroRIVERS route "
                            f"to sampling reach {value['site_hyriv_id']}; this "
                            "supports topological compatibility only."
                        )
                    else:
                        compatibility = EvidenceCompatibility.CONTRADICTS
                        reason = (
                            f"Zone {zone.label} has no directed HydroRIVERS route "
                            f"to sampling reach {value['site_hyriv_id']}; represented-"
                            "network hydrological contribution is contradicted."
                        )

            assessments.append(
                EvidenceAssessment(
                    evidence_id=evidence.id,
                    compatibility=compatibility,
                    rule_id=rule_id,
                    reason=reason,
                    provenance={
                        "engine_version": "deterministic_v1",
                        "case_id": str(case.id),
                        "zone_label": zone.label,
                        "zone_root_hyriv_id": zone.root_hyriv_id,
                        "evidence_type": evidence.evidence_type,
                        "evidence_source": evidence.source,
                        "evidence_provenance": evidence.provenance,
                        "rule_version": (
                            applied_rule.get("version") if applied_rule else None
                        ),
                        "rule_source": (
                            applied_rule.get("provenance/source")
                            if applied_rule
                            else None
                        ),
                        "rule_limitations": (
                            applied_rule.get("limitations")
                            if applied_rule
                            else None
                        ),
                    },
                )
            )

        return assessments

    def summarize_zone_assessment(
        self,
        assessments: list[EvidenceAssessment],
    ) -> dict[str, int]:
        """Count assessments by compatibility state without aggregating them."""
        summary = {
            "supports": 0,
            "contradicts": 0,
            "neutral": 0,
            "unknown": 0,
        }
        for assessment in assessments:
            summary[assessment.compatibility.value.lower()] += 1
        return summary
