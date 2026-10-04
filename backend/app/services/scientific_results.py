"""Canonical scientific comparisons; original audit records remain untouched."""
from datetime import date, datetime
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[3]
AUDIT_KEYS = {"id", "case_id", "decision_id", "investigation_run_id", "previous_decision_id",
              "new_decision_id", "started_at", "completed_at", "created_at", "retrieved_at",
              "collected_at", "execution_id", "historical_evidence_id", "sample_id"}
REFERENCE_KEYS = {"site_id", "zone_id", "evidence_id", "sampling_site_id", "candidate_reference"}
UNORDERED_LISTS = {"hypotheses", "source_hypotheses", "states", "candidates", "sites", "zones", "evidence", "assessments",
                   "reach_ids", "equivalent_hyriv_ids", "rules_applied", "rule_ids", "evidence_used",
                   "recommended_site_ids", "recommended_sites", "hydrology_checks", "limitations",
                   "assumptions", "scientific_sources", "pathways", "distinguished_hypothesis_pairs"}


def canonical_scientific_result(value, identities=None, key=""):
    """Normalize only explicit execution fields and unordered collections.

    Measurement dates, concentrations, scores, signatures and unknown reference
    values are retained. Signature ordering is scientifically meaningful.
    """
    identities = identities or {}
    if isinstance(value, dict):
        result = {}
        for name, item in sorted(value.items()):
            if name in AUDIT_KEYS:
                if name == "id" and str(item) not in identities and not (
                    "candidate_scope" in value and "status" in value
                    or "target_taxon" in value and "detection_site_id" in value
                    or "evidence_type" in value and "case_id" in value
                ):
                    # Catalog rule IDs and unknown scientific source IDs are
                    # meaningful inputs, not generated database identities.
                    result[name] = canonical_scientific_result(item, identities, name)
                continue
            if name in REFERENCE_KEYS:
                result[name + "_reference"] = identities.get(str(item), str(item) if item is not None else None)
            else:
                result[name] = canonical_scientific_result(item, identities, name)
        return result
    if isinstance(value, (list, tuple)):
        result = [canonical_scientific_result(item, identities, key) for item in value
                  if not (key == "assumptions" and isinstance(item, str) and item.startswith("InvestigationRun: "))]
        return sorted(result, key=lambda item: json.dumps(item, sort_keys=True)) if key in UNORDERED_LISTS else result
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, UUID)):
        value = str(value)
        if value in identities:
            return identities[value]
        if value.startswith(str(ROOT) + "/"):
            return str(Path(value).relative_to(ROOT))
    return value


def scientific_fingerprint(value):
    return sha256(json.dumps(canonical_scientific_result(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def current_rule_versions(rule_ids):
    from app.scientific.rules.catalog import get_rule_catalog, get_strength_rule_catalog
    versions = {rule["id"]: rule["version"] for rule in [*get_rule_catalog(), *get_strength_rule_catalog()]}
    return {rule_id: versions.get(rule_id, rule_id.rsplit(".", 1)[-1] if ".v" in rule_id else "UNKNOWN")
            for rule_id in sorted(rule_ids)}


def reference_identities(sites, zones, evidence):
    identities = {
        **{str(item["id"]): f"reach:{item['hyriv_id']}:{item.get('role') or item.get('site_type', '')}" for item in sites},
        **{str(item["id"]): f"zone:{item['label']}:{item['root_hyriv_id']}" for item in zones},
    }
    identities.update({str(item["id"]): "evidence:" + scientific_fingerprint(canonical_scientific_result(
        {key: item.get(key) for key in ("evidence_type", "source", "value", "observed_at", "quality", "provenance")},
        identities)) for item in evidence})
    return identities
