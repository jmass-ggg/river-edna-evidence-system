import json
from pathlib import Path

from app.api.routes.demo import load_wigger_demo
from app.api.routes.evidence import assess_evidence, get_evidence, get_evidence_service
from app.api.routes.sampling import (
    evaluate_sampling_decision,
    generate_sampling_candidates,
    get_decision_trace,
    get_latest_sampling_decision,
    get_sampling_service,
)


def _normalized_run(db_session):
    demo = load_wigger_demo(db_session)
    service = get_sampling_service(db_session)
    evidence_service = get_evidence_service(db_session)
    evidence = get_evidence(demo.case_id, evidence_service)
    assessments = assess_evidence(demo.case_id, db_session, evidence_service)
    generated = generate_sampling_candidates(demo.case_id, db_session, service)
    decision = evaluate_sampling_decision(demo.case_id, db_session, service)
    trace = get_decision_trace(demo.case_id, db_session)
    return demo, {
        "observation": demo.summary["historical_observation"],
        "evidence": sorted((item.evidence_type, item.quality) for item in evidence),
        "assessment": {
            item.zone_label: {
                "summary": item.summary,
                "directions": sorted(
                    (assessment.compatibility.value, assessment.rule_id)
                    for assessment in item.assessments
                ),
            }
            for item in assessments
        },
        "candidates": [
            (
                item.hyriv_id,
                item.signature,
                item.distinguished_hypothesis_pairs,
                item.pair_separation_score,
                item.network_distance_km,
            )
            for item in generated.candidates
        ],
        "decision": (decision.status.value, decision.rationale),
        "trace": {
            "rules": trace.rules_applied,
            "assumptions": trace.assumptions,
            "limitations": trace.limitations,
        },
    }


def test_wigger_demo_is_idempotent_and_scientifically_reproducible(db_session):
    first_demo, first = _normalized_run(db_session)
    second_demo, second = _normalized_run(db_session)

    assert first_demo.case_id == second_demo.case_id
    assert first_demo.detection_site_id == second_demo.detection_site_id
    assert first_demo.sites_created == second_demo.sites_created == 4
    assert first_demo.zones_created == second_demo.zones_created == 3
    assert len(first["evidence"]) == len(second["evidence"]) == 4
    assert first == second

    assert first["observation"]["station"] == "S1"
    assert first["observation"]["observation_index"] == 4
    assert first["decision"][0] == "TIE"
    latest = get_latest_sampling_decision(first_demo.case_id, db_session)
    assert latest is not None
    assert latest.status.value == "TIE"
    assert set(first["trace"]["rules"]) == {"sampling.topology_pair_separation.v1", "hydrorivers.directed_contribution.v1"}
    assert {candidate[0]: candidate[2] for candidate in first["candidates"]} == {
        20451169: [["Z1", "Z3"], ["Z2", "Z3"]],
        20450127: [["Z1", "Z2"], ["Z2", "Z3"]],
        20446568: [["Z1", "Z2"], ["Z1", "Z3"]],
        20447392: [["Z1", "Z2"], ["Z1", "Z3"]],
    }


def test_generated_report_matches_machine_readable_decision():
    root = Path(__file__).resolve().parents[3]
    result = json.loads(
        (root / "reproducibility_outputs/wigger_result.json").read_text()
    )
    report = (
        root / "reproducibility_outputs/WIGGER_INVESTIGATION_REPORT.md"
    ).read_text()

    observation = result["observation"]
    decision = result["registered_site_decision"]
    assert observation["station"] == "S1"
    assert observation["date"] == "2014-06-25"
    assert observation["concentration_mol_l"] == 1.2983219767633366e-17
    assert decision["status"] == "TIE"
    assert decision["recommended_sites"] == ["Site B", "Site C", "Site D"]
    assert "1.2983219767633366e-17 mol/L" in report
    assert f"**{decision['status']}** — {decision['rationale']}" in report
    assert "Z1 vs Z2" in report
