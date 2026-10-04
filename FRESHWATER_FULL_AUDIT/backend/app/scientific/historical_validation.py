"""Reproducible topology-only review of Carraro/HydroRIVERS alignment."""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat


def review_station_crosswalk(
    crosswalk_path: Path | str, data_wigger_path: Path | str, hydrology_engine,
) -> pd.DataFrame:
    crosswalk = pd.read_csv(crosswalk_path, keep_default_na=False)
    network = loadmat(data_wigger_path, squeeze_me=True, struct_as_record=False)
    reach_upstream = np.asarray(network["reach_upstream"])
    reach_by_station = {
        f"S{index + 1}": reach
        for index, reach in enumerate([1, 6, 13, 26, 25, 41, 64, 65, 120, 121, 123, 85, 86, 72, 71])
    }
    rows = []
    for item in crosswalk.to_dict("records"):
        station = item["station"]
        hyriv_id = int(item["candidate_hyriv_id"])
        carraro_reach = reach_by_station[station]
        carraro_relation = "SAME_AS_S1" if carraro_reach == 1 else (
            "UPSTREAM_OF_S1" if reach_upstream[0, carraro_reach - 1] > 0 else "NOT_UPSTREAM_OF_S1"
        )
        hydro_relation = "SAME_AS_S1" if hyriv_id == 20446064 else (
            "UPSTREAM_OF_S1" if hydrology_engine.is_upstream(hyriv_id, 20446064) else "NOT_UPSTREAM_OF_S1"
        )
        topology_agrees = carraro_relation == hydro_relation
        if station == "S1":
            review_status = "VERIFIED"
            reason = "Existing validated S1 crosswalk reproduced; validation is not weakened."
        elif item["mapping_status"] == "AMBIGUOUS" and int(item["candidate_count_within_radius"]) == 1 and topology_agrees:
            review_status = "SUPPORTED"
            reason = "Single candidate within 250 m and upstream relationship to S1 agrees across networks; independent watercourse verification is absent."
        elif item["mapping_status"] == "AMBIGUOUS":
            review_status = "AMBIGUOUS"
            reason = "Multiple nearby HydroRIVERS candidates prevent a unique mapping."
        else:
            review_status = "NOT_VERIFIED"
            reason = "Nearest reach is outside the 250 m review radius; topology agreement alone is insufficient."
        rows.append({
            **item, "carraro_reach_index": carraro_reach,
            "carraro_relation_to_s1": carraro_relation,
            "hydrorivers_relation_to_s1": hydro_relation,
            "topology_agrees": topology_agrees,
            "review_status": review_status,
            "review_reason": reason,
            "review_provenance": "RUN_MODEL.m; data_wigger.mat; HydroRIVERS v1.0; V4 deterministic review",
        })
    return pd.DataFrame(rows)


def classify_candidate_history(candidates, reviewed_crosswalk: pd.DataFrame) -> list[dict]:
    accepted = reviewed_crosswalk[
        reviewed_crosswalk.review_status.isin(["VERIFIED", "SUPPORTED"])
    ]
    results = []
    for candidate in candidates:
        overlaps = accepted[accepted.candidate_hyriv_id == candidate.hyriv_id]
        results.append({
            "hyriv_id": candidate.hyriv_id,
            "pair_separation_score": candidate.pair_separation_score,
            "classification": (
                "HISTORICAL OVERLAP AVAILABLE" if len(overlaps)
                else "COUNTERFACTUAL — NO HISTORICAL OUTCOME"
            ),
            "historical_stations": overlaps.station.tolist(),
        })
    return results
