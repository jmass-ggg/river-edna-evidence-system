"""Regression tests against frozen Wigger preflight artifacts."""

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes import demo
from app.domain.enums import ValidationStatus
from app.scientific.data_loader import WiggerPreflightLoader
from app.scientific.hydrology.engine import HydrologyEngine


OUTPUTS = Path("../data_preflight/outputs")
ROOTS = {"Z1": 20447392, "Z2": 20450127, "Z3": 20451169}
SITES = {"A": 20446064, "B": 20450127, "C": 20451169, "D": 20448315}


@pytest.fixture(scope="module")
def loader():
    return WiggerPreflightLoader(OUTPUTS)


@pytest.fixture(scope="module")
def engine(loader):
    return HydrologyEngine(loader.load_reaches(), loader.load_edges())


def test_site_a_matched_representation_is_separate_and_provenanced():
    snap = json.loads((OUTPUTS / "site_a_snap_validation.json").read_text())
    site_a = json.loads((OUTPUTS / "site_a.json").read_text())
    assert snap["match_status"] == "MATCHED"
    assert snap["HYRIV_ID"] == SITES["A"]
    assert snap["original_coordinate"]["latitude"] == 47.31400039098192
    assert snap["snapped_coordinate"]["latitude"] == 47.31458336166783
    assert snap["original_coordinate"] != snap["snapped_coordinate"]
    assert snap["sources"] and snap["evidence_summary"]
    assert site_a["network_representation"]["status"] == "MATCHED"
    assert ValidationStatus.MATCHED.value == "MATCHED"


def test_demo_refuses_unverified_historical_date(monkeypatch):
    site_a = json.loads((OUTPUTS / "site_a.json").read_text())

    class FakeLoader:
        def load_site_a(self):
            return site_a

        def load_zones(self):
            return None

        def load_sampling_sites(self):
            return None

        def load_validation_metadata(self):
            return None

    monkeypatch.setattr(demo, "WiggerPreflightLoader", FakeLoader)
    with pytest.raises(HTTPException) as exc_info:
        demo.load_wigger_demo(db=None)
    assert exc_info.value.status_code == 422
    assert "not verified" in exc_info.value.detail["message"]


def test_wigger_topology_from_graph(engine):
    assert len(engine.get_upstream_reaches(SITES["A"])) == 48
    assert engine.first_common_downstream(ROOTS["Z2"], ROOTS["Z3"]) == 20449905
    for root in ROOTS.values():
        assert engine.get_downstream_path(root, SITES["A"])[-1] == SITES["A"]
    with pytest.raises(ValueError, match="not found"):
        engine.get_reach(20446447)  # nearby Aare reach, excluded from upstream graph


def test_wigger_zone_exclusivity(loader):
    zones = loader.load_zones()
    reach_sets = {
        label: set(zones.loc[zones["zone"] == label, "HYRIV_ID"])
        for label in ROOTS
    }
    assert all(ROOTS[label] in reach_sets[label] for label in ROOTS)
    assert reach_sets["Z1"].isdisjoint(reach_sets["Z2"])
    assert reach_sets["Z1"].isdisjoint(reach_sets["Z3"])
    assert reach_sets["Z2"].isdisjoint(reach_sets["Z3"])


def test_wigger_reachability_signatures_from_traversal(engine):
    signatures = {
        site: [
            int(engine.can_contribute(root, reach_id))
            for root in ROOTS.values()
        ]
        for site, reach_id in SITES.items()
    }
    assert signatures == {
        "A": [1, 1, 1],
        "B": [0, 1, 0],
        "C": [0, 0, 1],
        "D": [0, 1, 1],
    }


def test_wigger_snapped_site_a_distances(engine, loader):
    snap = json.loads((OUTPUTS / "site_a_snap_validation.json").read_text())
    fraction = snap["snapped_coordinate"]["fraction_along_reach"]
    sites = loader.load_sampling_sites().set_index("site")
    for site in ("B", "C", "D"):
        recomputed = engine.network_distance_km(
            SITES[site], SITES["A"], from_fraction=0.5, to_fraction=fraction
        )
        assert recomputed == pytest.approx(
            sites.loc[site, "network_distance_to_site_a_km"], abs=1e-12
        )
