"""Historical Carraro H001 regression using the original MATLAB source."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from uuid import NAMESPACE_URL, uuid5

import pytest
from scipy.io import loadmat

from app.domain.enums import (
    CaseStatus,
    EvidenceCompatibility,
    SamplingDecisionStatus,
    SiteType,
    ValidationStatus,
)
from app.domain.models import Case, CandidateZone, EvidenceItem, SamplingSite
from app.scientific.data_loader import WiggerPreflightLoader
from app.scientific.evidence.engine import EvidenceCompatibilityEngineImpl
from app.scientific.hydrology.engine import HydrologyEngine
from app.scientific.sampling.engine import ScaffoldSamplingDecisionEngine


RAW = Path("../data_preflight/raw/carraro")
OUTPUTS = Path("../data_preflight/outputs")
MAT_SOURCE = RAW / "eDNA_data.mat"
MODEL_SOURCE = RAW / "RUN_MODEL.m"
ROOTS = {"Z1": 20447392, "Z2": 20450127, "Z3": 20451169}
SITE_REACHES = {"A": 20446064, "B": 20450127, "C": 20451169, "D": 20448315}


def _id(label: str):
    return uuid5(NAMESPACE_URL, f"carraro-h001:{label}")


def _matlab_date(serial_day: int):
    """Convert a whole-day MATLAB datenum to a UTC calendar date."""
    return (datetime.fromordinal(int(serial_day)) - timedelta(days=366)).date()


def _load_historical_observation() -> dict:
    source = loadmat(MAT_SOURCE, squeeze_me=True, struct_as_record=False)
    index = 4
    concentration = float(source["Fs"].S1[index - 1])
    return {
        "station": "S1",
        "species_code": "Fs",
        "species": "Fredericella sultana",
        "observation_index": index,
        "date": _matlab_date(source["Date"].S1[index - 1]),
        "concentration_mol_l": concentration,
        "state": "DETECTED" if concentration > 0.0 else "NONDETECTION",
        "edna_source": str(MAT_SOURCE),
    }


def _load_run_model_station_one() -> dict:
    model = MODEL_SOURCE.read_text(encoding="utf-8")
    match = re.search(
        r"station_coord\s*=\s*\[\s*"
        r"(?P<x>\d+(?:\.\d+)?)\s+"
        r"(?P<y>\d+(?:\.\d+)?)\s+"
        r"(?P<reach>\d+)\s*;",
        model,
    )
    assert match is not None, "RUN_MODEL.m station_coord first row was not found"
    return {
        "x": float(match.group("x")),
        "y": float(match.group("y")),
        "carraro_reach_index": int(match.group("reach")),
        "run_model_source": str(MODEL_SOURCE),
    }


@pytest.fixture(scope="module")
def historical_case_fixture():
    """Keep the single observation separate from proposed follow-up sites."""
    observation = _load_historical_observation()
    station = _load_run_model_station_one()
    loader = WiggerPreflightLoader(OUTPUTS)
    site_rows = loader.load_sampling_sites().set_index("site")

    return {
        "case_id": "H001",
        "observed": {
            **observation,
            **station,
            "hyriv_id": SITE_REACHES["A"],
        },
        "counterfactual_follow_up_sites": [
            {
                "site": label,
                "hyriv_id": int(site_rows.loc[label, "HYRIV_ID"]),
                "latitude": float(site_rows.loc[label, "latitude"]),
                "longitude": float(site_rows.loc[label, "longitude"]),
                "role": str(site_rows.loc[label, "role"]),
                "validation_status": str(
                    site_rows.loc[label, "validation_status"]
                ),
            }
            for label in ("B", "C", "D")
        ],
    }


@pytest.fixture(scope="module")
def scientific_run(historical_case_fixture):
    fixture = historical_case_fixture
    observed = fixture["observed"]
    loader = WiggerPreflightLoader(OUTPUTS)
    hydrology = HydrologyEngine(loader.load_reaches(), loader.load_edges())
    zones_frame = loader.load_zones()
    case_id = _id("case")
    case = Case(
        id=case_id,
        target_taxon=observed["species"],
        observation_date=observed["date"],
        detection_site_id=_id("site-a"),
        status=CaseStatus.UNDER_REVIEW,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        metadata={
            "historical_case_id": fixture["case_id"],
            "station": observed["station"],
            "species_code": observed["species_code"],
            "observation_index": observed["observation_index"],
            "concentration_mol_l": observed["concentration_mol_l"],
            "observed_state": observed["state"],
            "carraro_coordinate": {"x": observed["x"], "y": observed["y"]},
            "carraro_reach_index": observed["carraro_reach_index"],
            "hydrorivers_representation": observed["hyriv_id"],
            "source": observed["edna_source"],
        },
    )
    zones = [
        CandidateZone(
            id=_id(label),
            case_id=case_id,
            label=label,
            root_hyriv_id=root,
            reach_ids=[
                int(value)
                for value in zones_frame.loc[
                    zones_frame["zone"] == label, "HYRIV_ID"
                ]
            ],
            validation_status=ValidationStatus.VERIFIED,
            metadata={"source": "candidate_zones_real.geojson"},
        )
        for label, root in ROOTS.items()
    ]
    historical_evidence = EvidenceItem(
        id=_id("historical-observation"),
        case_id=case_id,
        evidence_type="historical_edna_measurement",
        source=observed["edna_source"],
        value={
            "station": observed["station"],
            "species_code": observed["species_code"],
            "observation_index": observed["observation_index"],
            "concentration_mol_l": observed["concentration_mol_l"],
            "state": observed["state"],
        },
        observed_at=datetime.combine(
            observed["date"], datetime.min.time(), tzinfo=timezone.utc
        ),
        quality="SOURCE_VERIFIED",
        provenance={"mat_variable": "Fs.S1", "matlab_index": 4},
        created_at=datetime.now(timezone.utc),
    )
    topology_evidence = [
        EvidenceItem(
            id=_id(f"topology-{zone.label}-to-a"),
            case_id=case_id,
            evidence_type="directed_hydrological_connectivity",
            source="HydroRIVERS NEXT_DOWN traversal",
            value={
                "zone_root_hyriv_id": zone.root_hyriv_id,
                "site_hyriv_id": observed["hyriv_id"],
                "can_contribute": hydrology.can_contribute(
                    zone.root_hyriv_id, observed["hyriv_id"]
                ),
                "network_validation_status": ValidationStatus.MATCHED.value,
            },
            observed_at=None,
            quality="VERIFIED",
            provenance={"historical_site": "S1", "hydrorivers_site": "A"},
            created_at=datetime.now(timezone.utc),
        )
        for zone in zones
    ]
    evidence_engine = EvidenceCompatibilityEngineImpl()
    evidence = [historical_evidence, *topology_evidence]
    assessments = {
        zone.label: evidence_engine.assess_evidence_for_zone(
            case, zone, evidence, scientific_rules=[]
        )
        for zone in zones
    }
    candidates = [
        SamplingSite(
            id=_id(f"site-{row['site'].lower()}"),
            case_id=case_id,
            label=row["site"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            hyriv_id=row["hyriv_id"],
            site_type=SiteType.FOLLOW_UP,
            validation_status=ValidationStatus(row["validation_status"]),
            role=row["role"],
            metadata={"status": "COUNTERFACTUAL"},
        )
        for row in fixture["counterfactual_follow_up_sites"]
    ]
    sampling_engine = ScaffoldSamplingDecisionEngine()
    evaluations = sampling_engine.evaluate_candidates(
        case, zones, candidates, hydrology
    )
    status, recommended_ids, reason = sampling_engine.make_recommendation(
        evaluations
    )
    return {
        "case": case,
        "zones": zones,
        "hydrology": hydrology,
        "assessments": assessments,
        "historical_evidence_id": historical_evidence.id,
        "evaluations": evaluations,
        "status": status,
        "recommended_ids": recommended_ids,
        "recommended_labels": [
            site.label for site in candidates if site.id in recommended_ids
        ],
        "reason": reason,
    }


def test_h001_real_source_and_run_model(historical_case_fixture):
    observed = historical_case_fixture["observed"]
    assert observed == {
        "station": "S1",
        "species_code": "Fs",
        "species": "Fredericella sultana",
        "observation_index": 4,
        "date": datetime(2014, 6, 25).date(),
        "concentration_mol_l": pytest.approx(1.29832198e-17, rel=1e-9),
        "state": "DETECTED",
        "edna_source": str(MAT_SOURCE),
        "x": 634537.17,
        "y": 240447.56,
        "carraro_reach_index": 1,
        "run_model_source": str(MODEL_SOURCE),
        "hyriv_id": 20446064,
    }


def test_h001_preserves_observed_counterfactual_boundary(
    historical_case_fixture,
):
    fixture = historical_case_fixture
    observed = fixture["observed"]
    assert observed["station"] == "S1"
    assert set(observed).isdisjoint({"replicate", "replicates", "replicate_id"})
    assert [site["site"] for site in fixture["counterfactual_follow_up_sites"]] == [
        "B",
        "C",
        "D",
    ]
    forbidden_historical_fields = {
        "station",
        "species",
        "species_code",
        "observation_index",
        "date",
        "concentration_mol_l",
        "state",
        "replicate",
        "replicates",
    }
    for site in fixture["counterfactual_follow_up_sites"]:
        assert set(site).isdisjoint(forbidden_historical_fields)


def test_h001_runs_evidence_hydrology_and_sampling_engines(scientific_run):
    run = scientific_run
    historical_id = run["historical_evidence_id"]
    for zone in run["zones"]:
        assessments = run["assessments"][zone.label]
        historical = next(a for a in assessments if a.evidence_id == historical_id)
        topology = next(
            a
            for a in assessments
            if a.rule_id == "hydrorivers.directed_contribution.v1"
            and a.compatibility == EvidenceCompatibility.SUPPORTS
        )
        assert historical.compatibility == EvidenceCompatibility.UNKNOWN
        assert "No validated scientific rule" in historical.reason
        assert topology.provenance["zone_root_hyriv_id"] == zone.root_hyriv_id
        assert run["hydrology"].can_contribute(zone.root_hyriv_id, 20446064)

    assert {item["site_label"]: item["signature"] for item in run["evaluations"]} == {
        "B": [0, 1, 0],
        "C": [0, 0, 1],
        "D": [0, 1, 1],
    }
    assert run["status"] == SamplingDecisionStatus.TIE
    assert run["recommended_labels"] == ["B", "C", "D"]
    assert run["reason"] == (
        "Multiple sites share the maximum topology-only pair separation score "
        "(2 pairs): B, C, D"
    )
