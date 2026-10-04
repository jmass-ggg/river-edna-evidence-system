"""Deterministic evidence compatibility evaluation."""

from typing import Any

from app.domain.enums import EvidenceCompatibility, EvidenceStrength, ValidationStatus
from app.domain.models import Case, CandidateZone, EvidenceItem, EvidenceAssessment
from app.scientific.rules.catalog import get_rule_catalog, get_strength_rule_catalog


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
        strength_rule = get_strength_rule_catalog()[0]
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
                    **self._assess_strength(evidence, zone, strength_rule),
                )
            )

        return assessments

    def _assess_strength(
        self,
        evidence: EvidenceItem,
        zone: CandidateZone,
        rule: dict[str, Any],
    ) -> dict[str, Any]:
        """Assess claim-specific strength without changing direction."""
        limitations = list(rule["limitations"])
        provenance = {
            "evidence_source": evidence.source,
            "evidence_provenance": evidence.provenance,
            "rule_source": rule["provenance/source"],
        }
        if evidence.evidence_type != rule["evidence_type"]:
            return {
                "strength": EvidenceStrength.UNASSESSED,
                "strength_criteria": [
                    {
                        "criterion": "supported evidence type",
                        "result": False,
                        "observed": evidence.evidence_type,
                    }
                ],
                "strength_reason": (
                    "No validated strength rule exists for this evidence type."
                ),
                "strength_rule_id": None,
                "strength_rule_version": None,
                "strength_provenance": provenance,
                "strength_limitations": limitations,
            }

        value = evidence.value if isinstance(evidence.value, dict) else {}
        accepted = {"VERIFIED", "SUPPORTED", "MATCHED"}
        network_validated = value.get("network_validation_status") in accepted
        zone_validated = zone.validation_status in {
            ValidationStatus.VERIFIED,
            ValidationStatus.SUPPORTED,
            ValidationStatus.MATCHED,
        }
        topology_complete = isinstance(value.get("can_contribute"), bool)
        graph_coverage_validated = value.get("graph_coverage_validated") is True
        criteria = [
            {
                "criterion": "network mapping validation",
                "result": network_validated,
                "observed": value.get("network_validation_status"),
            },
            {
                "criterion": "zone root validation",
                "result": zone_validated,
                "observed": zone.validation_status.value,
            },
            {
                "criterion": "complete directed topology evaluation",
                "result": topology_complete,
                "observed": topology_complete,
            },
            {
                "criterion": "validated graph coverage",
                "result": graph_coverage_validated,
                "observed": value.get("graph_coverage_validated"),
            },
        ]
        if network_validated and zone_validated and topology_complete:
            if graph_coverage_validated:
                strength = EvidenceStrength.HIGH
                reason = (
                    "Hydrological-connectivity evidence has validated network "
                    "mapping, zone validation, complete topology evaluation, "
                    "and explicit validated graph coverage."
                )
            else:
                strength = EvidenceStrength.MEDIUM
                reason = (
                    "Hydrological-connectivity evidence has validated mapping, "
                    "zone validation, and a complete topology result; explicit "
                    "validated graph-coverage metadata was not supplied."
                )
        else:
            strength = EvidenceStrength.LOW
            reason = (
                "Hydrological-connectivity evidence is missing validated mapping, "
                "zone validation, or a complete topology result."
            )
        return {
            "strength": strength,
            "strength_criteria": criteria,
            "strength_reason": reason,
            "strength_rule_id": rule["id"],
            "strength_rule_version": rule["version"],
            "strength_provenance": provenance,
            "strength_limitations": limitations,
        }

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
