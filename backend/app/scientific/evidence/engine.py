"""Deterministic evidence compatibility evaluation."""

from typing import Any
from dataclasses import replace

from app.domain.enums import EvidenceCompatibility, EvidenceStrength, ValidationStatus
from app.domain.models import Case, CandidateZone, EvidenceItem, EvidenceAssessment
from app.scientific.rules.catalog import get_rule_catalog, get_strength_rule_catalog


class EvidenceCompatibilityEngineImpl:
    """Apply only validated catalog rules; leave unsupported evidence UNKNOWN."""

    def __init__(self, hydrology_engine=None, graph_provenance: dict[str, Any] | None = None):
        # These dependencies are injected by server code, never evidence JSON.
        self.hydrology_engine = hydrology_engine
        self.graph_provenance = dict(graph_provenance or {})

    def _validated_connectivity(self, case, zone, evidence, required):
        validation = {"status": "NOT_VERIFIED", "method": "HydrologyEngine.can_contribute"}
        value = evidence.value
        if evidence.case_id != case.id or zone.case_id != case.id:
            return validation, "Evidence and zone must belong to the assessed case."
        if not isinstance(value, dict) or any(field not in value for field in required):
            return validation, f"Directed-connectivity evidence is incomplete; required fields are {required}."
        if (type(value["zone_root_hyriv_id"]) is not int or type(value["site_hyriv_id"]) is not int
                or not isinstance(value["can_contribute"], bool)):
            return validation, "Directed-connectivity reach IDs must be integers and can_contribute must be boolean."
        try:
            if self.hydrology_engine is None:
                from app.scientific.data_loader import WiggerPreflightLoader
                from app.scientific.hydrology.engine import HydrologyEngine
                loader = WiggerPreflightLoader()
                hashes = loader.validate_frozen_reference()
                self.hydrology_engine = HydrologyEngine(loader.load_reaches(), loader.load_edges())
                self.graph_provenance = {
                    "network_validation_status": "VERIFIED", "artifact_sha256": hashes,
                    "network_source": str(loader.data_dir / "upstream_edges.csv"),
                    # Preserve the frozen claim-strength boundary: graph coverage
                    # is not established by an evidence author's boolean.
                    "graph_coverage_validated": False,
                }
            validation["source_graph"] = dict(self.graph_provenance)
            if self.graph_provenance.get("network_validation_status") not in {"VERIFIED", "MATCHED", "SUPPORTED"}:
                return validation, "No server-validated source graph is available."
            for reach_id in (zone.root_hyriv_id, value["zone_root_hyriv_id"], value["site_hyriv_id"]):
                self.hydrology_engine.get_reach(reach_id)
            actual = self.hydrology_engine.can_contribute(value["zone_root_hyriv_id"], value["site_hyriv_id"])
            validation.update({"actual_can_contribute": actual,
                               "submitted_can_contribute": value["can_contribute"],
                               "zone_root_hyriv_id": value["zone_root_hyriv_id"],
                               "site_hyriv_id": value["site_hyriv_id"]})
            if actual != value["can_contribute"]:
                return validation, "Submitted connectivity contradicts the directed source graph; compatibility remains UNKNOWN."
            if zone.validation_status not in {ValidationStatus.MATCHED, ValidationStatus.SUPPORTED, ValidationStatus.VERIFIED}:
                return validation, "The source-zone network state is not validated."
            validation["status"] = self.graph_provenance["network_validation_status"]
            return validation, None
        except (ValueError, OSError, KeyError, TypeError) as exc:
            return validation, f"Directed graph validation unavailable: {exc}"

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

            validation = {"status": "NOT_APPLICABLE"}
            strength_evidence = evidence
            if evidence.evidence_type == "directed_hydrological_connectivity":
                # An unavailable catalog rule cannot leave submitted strength
                # flags trusted, even though no compatibility rule is applied.
                unchecked = dict(evidence.value) if isinstance(evidence.value, dict) else {}
                unchecked.update(network_validation_status="NOT_VERIFIED",
                                 can_contribute=None, graph_coverage_validated=False)
                strength_evidence = replace(evidence, value=unchecked)
            if topology_rule is not None and evidence.evidence_type == "directed_hydrological_connectivity":
                validation, error = self._validated_connectivity(
                    case, zone, evidence, topology_rule["condition"]["required_value_fields"]
                )
                # Strength uses the server's result, not submitted validation labels.
                checked_value = dict(evidence.value) if isinstance(evidence.value, dict) else {}
                checked_value.update({
                    "network_validation_status": validation["status"],
                    "can_contribute": validation.get("actual_can_contribute") if error is None else None,
                    "graph_coverage_validated": error is None and self.graph_provenance.get("graph_coverage_validated") is True,
                })
                strength_evidence = replace(evidence, value=checked_value)
                if error:
                    reason = error
                else:
                    rule_id = topology_rule["id"]
                    applied_rule = topology_rule
                    if evidence.value["zone_root_hyriv_id"] != zone.root_hyriv_id:
                        compatibility = EvidenceCompatibility.NEUTRAL
                        reason = f"Connectivity evidence targets another validated root; it is neutral for zone {zone.label}."
                    elif validation["actual_can_contribute"]:
                        compatibility = EvidenceCompatibility.SUPPORTS
                        reason = (f"Zone {zone.label} has a directed HydroRIVERS route to sampling reach "
                                  f"{evidence.value['site_hyriv_id']}; this supports topological compatibility only.")
                    else:
                        compatibility = EvidenceCompatibility.CONTRADICTS
                        reason = (f"Zone {zone.label} has no directed HydroRIVERS route to sampling reach "
                                  f"{evidence.value['site_hyriv_id']}; represented-network hydrological contribution is contradicted.")

            assessments.append(
                EvidenceAssessment(
                    evidence_id=evidence.id,
                    compatibility=compatibility,
                    rule_id=rule_id,
                    reason=reason,
                    provenance={
                        "engine_version": "deterministic_v1",
                        "graph_validation": validation,
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
                    **self._assess_strength(strength_evidence, zone, strength_rule),
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
