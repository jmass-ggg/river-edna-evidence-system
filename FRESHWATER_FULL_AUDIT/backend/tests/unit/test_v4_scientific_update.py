from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from app.api.routes.demo import load_wigger_demo
from app.domain.enums import EvidenceCompatibility, HypothesisStatus
from app.repositories.evidence import EvidenceRepository
from app.scientific.historical_validation import classify_candidate_history, review_station_crosswalk
from app.scientific.hypothesis import ConservativeHypothesisStateResolver
from app.scientific.sampling.candidate_generator import CandidateSiteGenerator
from app.services.investigation_service import InvestigationService
from tests.unit.test_investigation_runs import _service


def _assessment(direction, rule_id="hydrorivers.directed_contribution.v1"):
    return SimpleNamespace(compatibility=direction, rule_id=rule_id)


def test_conservative_resolver_deterministic_states():
    resolver = ConservativeHypothesisStateResolver()
    zone = object()
    summary = {"supports": 0, "contradicts": 0, "neutral": 0, "unknown": 0}
    assert resolver.resolve(zone, [], summary)[0] == HypothesisStatus.UNKNOWN
    assert resolver.resolve(zone, [_assessment(EvidenceCompatibility.SUPPORTS)], summary)[0] == HypothesisStatus.SUPPORTED
    weakened = resolver.resolve(zone, [_assessment(EvidenceCompatibility.CONTRADICTS)], summary)[0]
    assert weakened == HypothesisStatus.WEAKENED
    assert weakened != HypothesisStatus.ELIMINATED
    assert resolver.resolve(zone, [
        _assessment(EvidenceCompatibility.SUPPORTS),
        _assessment(EvidenceCompatibility.CONTRADICTS),
    ], summary)[0] == HypothesisStatus.CONFLICTING


def test_unsupported_assessments_cannot_change_hypothesis():
    resolver = ConservativeHypothesisStateResolver()
    unsupported = [_assessment(EvidenceCompatibility.SUPPORTS, rule_id=None)]
    status, reason = resolver.resolve(object(), unsupported, {})
    assert status == HypothesisStatus.UNKNOWN
    assert "unsupported evidence cannot alter" in reason


def test_unknown_follow_up_preserves_zones_decision_and_trace(db_session):
    case_id = load_wigger_demo(db_session).case_id
    service = _service(db_session)
    before = service.reinvestigate(case_id)
    evidence = EvidenceRepository(db_session).add_evidence(
        case_id=case_id, evidence_type="follow_up_edna_sample", source="fixture",
        value={"positive_replicates": 1}, provenance={"fixture": True},
    )

    after = service.reinvestigate(case_id, trigger_evidence_id=evidence.id)

    assert [item["status"] for item in after["hypotheses"]] == [
        item["status"] for item in before["hypotheses"]
    ]
    assert after["before"]["candidate_representatives"] == after["after"]["candidate_representatives"]
    assert after["changed"]["overall"] is False
    assert "No scientifically supported" in after["change_reason"]
    trace = after["decision_trace"]
    assert any(check.get("check") == "hypothesis_state_reasoning" for check in trace["hydrology_checks"])
    assert any(check.get("check") == "candidate_generation_criterion" for check in trace["hydrology_checks"])
    assert any("no validated interpretation rule" in text for text in trace["limitations"])
    assert str(after["investigation_run_id"]) in " ".join(trace["assumptions"])
    assert before["new_decision_id"] == after["previous_decision_id"]


def test_reviewed_mapping_and_candidate_overlap_are_conservative():
    from app.scientific.data_loader import WiggerPreflightLoader
    from app.scientific.hydrology.engine import HydrologyEngine
    from app.domain.enums import ValidationStatus
    from app.domain.models import CandidateZone
    from pathlib import Path
    from uuid import uuid4

    root = Path(__file__).resolve().parents[3]
    loader = WiggerPreflightLoader(root / "data_preflight/outputs")
    hydrology = HydrologyEngine(loader.load_reaches(), loader.load_edges())
    reviewed = review_station_crosswalk(
        root / "data_preflight/outputs/carraro_station_hydrorivers_crosswalk_v4.csv",
        root / "data_preflight/raw/carraro/data_wigger.mat", hydrology,
    )
    stored = pd.read_csv(
        root / "data_preflight/outputs/carraro_station_hydrorivers_review_v4.csv",
        keep_default_na=False,
    )
    pd.testing.assert_frame_equal(reviewed, stored, check_dtype=False)
    assert reviewed.review_status.value_counts().to_dict() == {
        "SUPPORTED": 7, "NOT_VERIFIED": 6, "VERIFIED": 1, "AMBIGUOUS": 1,
    }
    assert reviewed.loc[reviewed.station == "S1", "candidate_hyriv_id"].item() == 20446064
    assert reviewed.topology_agrees.all()

    zones_frame = loader.load_zones()
    zones = []
    case_id = uuid4()
    for label in ("Z1", "Z2", "Z3"):
        frame = zones_frame[zones_frame.zone == label]
        root_id = int(frame.loc[frame.UPLAND_SKM.idxmax()].HYRIV_ID)
        zones.append(CandidateZone(uuid4(), case_id, label, root_id, frame.HYRIV_ID.astype(int).tolist(), ValidationStatus.VERIFIED))
    coordinates = {}
    for _, row in loader.load_reach_geometries().iterrows():
        midpoint = row.geometry.interpolate(.5, normalized=True)
        coordinates[int(row.HYRIV_ID)] = (midpoint.y, midpoint.x)
    generated = CandidateSiteGenerator(hydrology, coordinates).generate(
        zones, 20446064,
        site_a_fraction=loader.load_site_a_snap_validation()["snapped_coordinate"]["fraction_along_reach"],
    )
    outcomes = classify_candidate_history(generated.candidates, reviewed)
    overlap = [item for item in outcomes if item["classification"] == "HISTORICAL OVERLAP AVAILABLE"]
    assert overlap == [{
        "hyriv_id": 20450127, "pair_separation_score": 2,
        "classification": "HISTORICAL OVERLAP AVAILABLE", "historical_stations": ["S14"],
    }]
    counterfactual = [item for item in outcomes if item["classification"].startswith("COUNTERFACTUAL")]
    assert len(counterfactual) == 3
    assert all(not item["historical_stations"] for item in counterfactual)
