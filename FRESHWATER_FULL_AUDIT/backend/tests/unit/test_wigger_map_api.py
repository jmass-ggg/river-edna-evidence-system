import pytest

from app.api.routes.demo import get_wigger_map
from app.scientific.data_loader import WiggerPreflightLoader
from app.scientific.hydrology.engine import HydrologyEngine
from config import config


def test_wigger_map_returns_validated_preflight_geometry_and_sites():
    response = get_wigger_map()

    assert response.crs == "EPSG:4326"
    assert response.river_network["type"] == "FeatureCollection"
    assert len(response.river_network["features"]) == 49
    assert response.source_zones["type"] == "FeatureCollection"
    assert {site["label"] for site in response.sites} == {"A", "B", "C", "D"}
    site_a = next(site for site in response.sites if site["label"] == "A")
    assert site_a["hyriv_id"] == 20446064
    assert site_a["snap_distance_m"] == 64.81356293400535
    assert response.provenance["status"] == "validated preflight artifacts"

    loader = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
    expected = loader.load_sampling_sites().set_index("site")
    hydrology = HydrologyEngine(loader.load_reaches(), loader.load_edges())
    for site in response.sites:
        row = expected.loc[site["label"]]
        assert site["hyriv_id"] == int(row["HYRIV_ID"])
        assert site["latitude"] == float(row["latitude"])
        assert site["longitude"] == float(row["longitude"])
        assert site["network_latitude"] == float(row["network_latitude"])
        assert site["network_longitude"] == float(row["network_longitude"])
        assert site["snap_distance_m"] == float(row["snap_distance_m"])
        assert hydrology.can_contribute(site["hyriv_id"], 20446064)

    upstream = hydrology.get_upstream_reaches(20446064)
    assert len(upstream) == 48
    assert len(response.river_network["features"]) == len(upstream) + 1
    assert sum(
        float(feature["properties"]["LENGTH_KM"])
        for feature in response.river_network["features"]
    ) == pytest.approx(145.23)
