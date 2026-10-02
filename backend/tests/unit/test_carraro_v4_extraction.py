from pathlib import Path

import pandas as pd
import pytest

from app.preflight.carraro_v4 import CarraroV4Extractor


ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data_preflight/raw/carraro"
HYDRO = ROOT / "data_preflight/raw/hydrorivers/HydroRIVERS_v10_eu.shp"
OUTPUT = ROOT / "data_preflight/outputs"


def _extractor():
    return CarraroV4Extractor(RAW, HYDRO)


def test_station_inventory_reproduces_source_counts():
    actual = _extractor().inventory()
    stored = pd.read_csv(OUTPUT / "carraro_station_inventory.csv")
    pd.testing.assert_frame_equal(actual, stored, check_dtype=False)
    assert len(actual) == 15
    assert actual.fs_observation_count.sum() == 301
    assert actual.tb_observation_count.sum() == 301
    assert actual.date_count.sum() == 305


def test_tidy_observations_reproduce_dates_and_h001():
    actual = _extractor().observations()
    stored = pd.read_csv(OUTPUT / "carraro_observations_v4.csv")
    stored["date"] = stored["date"].astype(str)
    pd.testing.assert_frame_equal(actual, stored, check_dtype=False)
    assert set(actual.taxon_code) == {"Fs", "Tb"}
    h001 = actual[(actual.station == "S1") & (actual.taxon_code == "Fs") & (actual.observation_index == 4)].iloc[0]
    assert h001.date == "2014-06-25"
    assert h001.concentration_mol_l == pytest.approx(1.29832198e-17)
    assert bool(h001.detected) is True


def test_crosswalk_is_deterministic_and_only_s1_is_matched():
    first = _extractor().crosswalk()
    second = _extractor().crosswalk()
    stored = pd.read_csv(
        OUTPUT / "carraro_station_hydrorivers_crosswalk_v4.csv", keep_default_na=False
    )
    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(first, stored, check_dtype=False)
    s1 = first[first.station == "S1"].iloc[0]
    assert s1.candidate_hyriv_id == 20446064
    assert s1.mapping_status == "MATCHED"
    assert set(first[first.station != "S1"].mapping_status) <= {"AMBIGUOUS", "OUT_OF_RANGE", "NOT_MAPPABLE"}
    assert not (first[first.station != "S1"].mapping_status == "VERIFIED").any()
