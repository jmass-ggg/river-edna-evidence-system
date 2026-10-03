#!/usr/bin/env python3
"""Audit the frozen Wigger sampling comparison without inferring field outcomes."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def audit(result: dict, crosswalk: list[dict], observations: list[dict]) -> dict:
    generated = result["generated_candidates"]
    registered = [site for site in result["sites"] if site["label"] in {"Site B", "Site C", "Site D"}]
    labels = sorted(zone["label"] for zone in result["zones"])
    if len(labels) != 3 or len(registered) != 3:
        raise ValueError("Expected the frozen three-zone, three-registered-site Wigger case")

    # A deterministic planning baseline, not an observed field campaign.
    nearest = min(generated, key=lambda item: (item["network_distance_km"], item["hyriv_id"]))
    best = max(item["pair_separation_score"] for item in generated)
    if best <= 0:
        raise ValueError("Frozen candidate set has no useful discriminator")
    registered_reaches = {site["hyriv_id"] for site in registered}
    reviewed = [row for row in crosswalk if row["review_status"] in {"VERIFIED", "SUPPORTED"}]
    overlaps = []
    for candidate in generated:
        stations = [row["station"] for row in reviewed if int(row["candidate_hyriv_id"]) == candidate["hyriv_id"]]
        matched = [row for row in observations if row["station"] in stations and row["taxon_code"] == "Fs" and row["date"] == result["observation"]["date"]]
        overlaps.append({
            "hyriv_id": candidate["hyriv_id"],
            "stations": stations,
            "same_date_fs_observations": [{"station": row["station"], "detected": row["detected"] == "True", "concentration_mol_l": row["concentration_mol_l"]} for row in matched],
            "crosswalk_status": [row["review_status"] for row in reviewed if row["station"] in stations],
        })
    return {
        "analysis_id": "wigger.sampling_scope_audit.v1",
        "source_result": "reproducibility_outputs/wigger_result.json",
        "historical_sources": ["data_preflight/outputs/carraro_station_hydrorivers_review_v4.csv", "data_preflight/outputs/carraro_observations_v4.csv"],
        "generated_representatives": [{"hyriv_id": item["hyriv_id"], "signature": item["signature"], "pair_separation_score": item["pair_separation_score"], "network_distance_km": item["network_distance_km"], "registered_follow_up_site": item["hyriv_id"] in registered_reaches} for item in generated],
        "generated_representative_count": len(generated),
        "registered_follow_up_site_count": len(registered),
        "registered_decision": result["registered_site_decision"],
        "topology_only_comparison": {
            "nearest_generated_representative": {"hyriv_id": nearest["hyriv_id"], "pair_separation_score": nearest["pair_separation_score"]},
            "maximum_pair_separation_score": best,
            "maximum_score_reaches": [item["hyriv_id"] for item in generated if item["pair_separation_score"] == best],
            "candidate_representatives_examined_by_algorithm": len(generated),
            "field_samples_collected": None,
            "field_or_lab_cost": None,
            "analyst_time_seconds": None,
            "correct_source_identification": None,
        },
        "historical_overlap": overlaps,
        "limitations": [
            "Registered sites and generated reach representatives are different candidate sets; equal reach scores do not add a fourth registered site to the persisted decision.",
            "A reachability signature assumes binary ideal outcomes; no detection, transport, or assay probability is calibrated.",
            "The nearest-representative comparison is a computed planning baseline, not measured field performance.",
            "Historical station overlap and same-date detection do not establish the biological source or validate counterfactual sampling decisions.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "scientific_validation_outputs/sampling_audit.json")
    args = parser.parse_args()
    result = json.loads((ROOT / "reproducibility_outputs/wigger_result.json").read_text())
    with (ROOT / "data_preflight/outputs/carraro_station_hydrorivers_review_v4.csv").open(newline="") as stream:
        crosswalk = list(csv.DictReader(stream))
    with (ROOT / "data_preflight/outputs/carraro_observations_v4.csv").open(newline="") as stream:
        observations = list(csv.DictReader(stream))
    output = audit(result, crosswalk, observations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
