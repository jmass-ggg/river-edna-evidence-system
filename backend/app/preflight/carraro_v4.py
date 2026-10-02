"""Reproduce Carraro station, observation, and provisional crosswalk tables."""
from datetime import datetime, timedelta
from pathlib import Path
import re

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.io import loadmat
from shapely.geometry import Point


class CarraroV4Extractor:
    def __init__(self, raw_dir: Path | str, hydrorivers_path: Path | str):
        self.raw_dir = Path(raw_dir)
        self.hydrorivers_path = Path(hydrorivers_path)

    @staticmethod
    def matlab_date(value: float):
        return (datetime.fromordinal(int(value)) - timedelta(days=366)).date()

    def stations(self) -> pd.DataFrame:
        text = (self.raw_dir / "RUN_MODEL.m").read_text(encoding="utf-8")
        block = re.search(r"station_coord\s*=\s*\[(.*?)\];", text, re.S)
        if block is None:
            raise ValueError("station_coord was not found")
        rows = re.findall(r"([0-9.]+)\s+([0-9.]+)\s+([0-9]+)\s*;?", block.group(1))
        return pd.DataFrame([
            {"station": f"S{i}", "original_x": float(x), "original_y": float(y), "carraro_reach_index": int(reach)}
            for i, (x, y, reach) in enumerate(rows, 1)
        ])

    def observations(self) -> pd.DataFrame:
        source = loadmat(self.raw_dir / "eDNA_data.mat", squeeze_me=True, struct_as_record=False)
        rows = []
        for station in source["Date"]._fieldnames:
            dates = np.atleast_1d(getattr(source["Date"], station))
            for taxon in ("Fs", "Tb"):
                values = np.atleast_1d(getattr(source[taxon], station))
                for index, (serial, value) in enumerate(zip(dates, values), 1):
                    if np.isnan(value):
                        continue
                    rows.append({
                        "station": station, "taxon_code": taxon,
                        "observation_index": index, "date": self.matlab_date(serial).isoformat(),
                        "concentration_mol_l": float(value), "detected": bool(value > 0),
                        "source_file": "data_preflight/raw/carraro/eDNA_data.mat",
                        "source_variable": f"{taxon}.{station}",
                        "date_variable": f"Date.{station}",
                    })
        return pd.DataFrame(rows)

    def inventory(self) -> pd.DataFrame:
        stations = self.stations()
        source = loadmat(self.raw_dir / "eDNA_data.mat", squeeze_me=True, struct_as_record=False)
        counts = []
        for station in source["Date"]._fieldnames:
            counts.append({
                "station": station,
                "fs_observation_count": int(np.sum(~np.isnan(np.atleast_1d(getattr(source["Fs"], station))))),
                "tb_observation_count": int(np.sum(~np.isnan(np.atleast_1d(getattr(source["Tb"], station))))),
                "date_count": int(np.sum(~np.isnan(np.atleast_1d(getattr(source["Date"], station))))),
                "coordinate_source": "data_preflight/raw/carraro/RUN_MODEL.m",
                "observation_source": "data_preflight/raw/carraro/eDNA_data.mat",
            })
        return stations.merge(pd.DataFrame(counts), on="station", validate="one_to_one")

    def crosswalk(self, candidate_radius_m: float = 250.0) -> pd.DataFrame:
        stations = self.stations()
        transformer = Transformer.from_crs(21781, 4326, always_xy=True)
        metric = Transformer.from_crs(21781, 2056, always_xy=True)
        lonlat = [transformer.transform(x, y) for x, y in zip(stations.original_x, stations.original_y)]
        stations["converted_lon"] = [value[0] for value in lonlat]
        stations["converted_lat"] = [value[1] for value in lonlat]
        bounds = (
            stations.converted_lon.min() - 0.02, stations.converted_lat.min() - 0.02,
            stations.converted_lon.max() + 0.02, stations.converted_lat.max() + 0.02,
        )
        rivers = gpd.read_file(self.hydrorivers_path, bbox=bounds).to_crs(2056)
        rows = []
        for record in stations.itertuples(index=False):
            x, y = metric.transform(record.original_x, record.original_y)
            point = Point(x, y)
            distances = rivers.geometry.distance(point)
            ordered = rivers.assign(_distance=distances).sort_values(["_distance", "HYRIV_ID"])
            nearest = ordered.iloc[0]
            candidates = ordered[ordered._distance <= candidate_radius_m]
            hyriv_id = int(nearest.HYRIV_ID)
            if record.station == "S1":
                if hyriv_id != 20446064:
                    raise ValueError(f"S1 crosswalk regression: expected 20446064, got {hyriv_id}")
                mapping_status = "MATCHED"
                notes = "Reproduces the existing independently validated S1 crosswalk."
            elif len(candidates):
                mapping_status = "AMBIGUOUS"
                notes = "Nearest geographic candidate retained for review; not scientifically verified."
            else:
                mapping_status = "OUT_OF_RANGE"
                notes = f"No HydroRIVERS reach within {candidate_radius_m:g} m review radius."
            rows.append({
                "station": record.station, "original_x": record.original_x,
                "original_y": record.original_y, "converted_lat": record.converted_lat,
                "converted_lon": record.converted_lon, "candidate_hyriv_id": hyriv_id,
                "snap_distance_m": float(nearest._distance), "mapping_status": mapping_status,
                "mapping_notes": notes, "candidate_count_within_radius": int(len(candidates)),
                "candidate_radius_m": candidate_radius_m,
                "ambiguity_candidate_ids": "|".join(str(int(value)) for value in candidates.HYRIV_ID.tolist()),
                "topology_consistency": "VALIDATED_S1" if record.station == "S1" else "NOT_EVALUATED",
            })
        return pd.DataFrame(rows)


def build_all(repository_root: Path | str) -> dict[str, pd.DataFrame]:
    root = Path(repository_root)
    extractor = CarraroV4Extractor(
        root / "data_preflight/raw/carraro",
        root / "data_preflight/raw/hydrorivers/HydroRIVERS_v10_eu.shp",
    )
    return {
        "carraro_station_inventory.csv": extractor.inventory(),
        "carraro_station_hydrorivers_crosswalk_v4.csv": extractor.crosswalk(),
        "carraro_observations_v4.csv": extractor.observations(),
    }
