"""Guard the distinction between generated reaches and registered sites."""
import csv
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_sampling import audit  # noqa: E402


def test_frozen_sampling_scope_and_historical_overlap():
    result = json.loads((ROOT / "reproducibility_outputs/wigger_result.json").read_text())
    with (ROOT / "data_preflight/outputs/carraro_station_hydrorivers_review_v4.csv").open(newline="") as stream:
        crosswalk = list(csv.DictReader(stream))
    with (ROOT / "data_preflight/outputs/carraro_observations_v4.csv").open(newline="") as stream:
        observations = list(csv.DictReader(stream))

    comparison = audit(result, crosswalk, observations)

    assert comparison["generated_representative_count"] == 4
    assert comparison["registered_follow_up_site_count"] == 3
    assert comparison["registered_decision"]["status"] == "TIE"
    assert comparison["registered_decision"]["recommended_sites"] == ["Site B", "Site C", "Site D"]
    assert {item["pair_separation_score"] for item in comparison["generated_representatives"]} == {2}
    assert comparison["topology_only_comparison"]["nearest_generated_representative"] == {
        "hyriv_id": 20446568, "pair_separation_score": 2,
    }
    assert comparison["topology_only_comparison"]["correct_source_identification"] is None
    assert [item for item in comparison["historical_overlap"] if item["stations"]] == [{
        "hyriv_id": 20450127,
        "stations": ["S14"],
        "crosswalk_status": ["SUPPORTED"],
        "same_date_fs_observations": [{
            "station": "S14", "detected": True,
            "concentration_mol_l": "1.3338877637558446e-17",
        }],
    }]
