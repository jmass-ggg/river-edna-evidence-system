"""
Wigger preflight data loader.

This module loads validated Wigger case data from preflight artifacts.
It reads existing files and validates their structure without modifying values.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import re
from typing import Any

import pandas as pd
import geopandas as gpd
from scipy.io import loadmat


class WiggerPreflightLoader:
    """
    Loads validated Wigger case data from preflight artifacts.
    
    This loader reads existing files and validates their structure
    without modifying values. All data is read-only.
    """
    
    def __init__(self, data_dir: Path | str | None = None):
        """
        Initialize the Wigger preflight data loader.
        
        Args:
            data_dir: Path to the directory containing preflight output files
            
        Raises:
            FileNotFoundError: If required files are missing
        """
        if data_dir is None:
            from config import config

            data_dir = config.PREFLIGHT_DATA_DIR
        self.data_dir = Path(data_dir).expanduser().resolve()
        self._validate_required_files()
    
    def load_site_a(self) -> dict[str, Any]:
        """
        Load Site A (S1) detection site from site_a.json.
        
        Returns:
            Dictionary containing Site A metadata including coordinates,
            network representation, target taxon, and sampling date
            
        Raises:
            FileNotFoundError: If site_a.json is missing
            json.JSONDecodeError: If the file contains invalid JSON
        """
        file_path = self.data_dir / "site_a.json"
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Required preflight file not found: {file_path}. "
                f"Ensure data_preflight/outputs/ contains validated artifacts."
            )

    def load_site_a_snap_validation(self) -> dict[str, Any]:
        """Load the validated Site A snap position and reach fraction."""
        file_path = self.data_dir / "site_a_snap_validation.json"
        try:
            with open(file_path, "r") as source:
                return json.load(source)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Required preflight file not found: {file_path}."
            )
    
    def load_reaches(self) -> pd.DataFrame:
        """
        Load reach data from upstream_reaches_real.csv.
        
        Returns:
            DataFrame with columns: HYRIV_ID, NEXT_DOWN, LENGTH_KM,
            UPLAND_SKM, DIS_AV_CMS, and other HydroRIVERS attributes
            
        Raises:
            FileNotFoundError: If upstream_reaches_real.csv is missing
        """
        file_path = self.data_dir / "upstream_reaches_real.csv"
        try:
            return pd.read_csv(file_path)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Required preflight file not found: {file_path}. "
                f"Ensure data_preflight/outputs/ contains validated artifacts."
            )
    
    def load_edges(self) -> pd.DataFrame:
        """
        Load network edges from upstream_edges.csv.
        
        Returns:
            DataFrame with parent-child reach relationships
            
        Raises:
            FileNotFoundError: If upstream_edges.csv is missing
        """
        file_path = self.data_dir / "upstream_edges.csv"
        try:
            return pd.read_csv(file_path)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Required preflight file not found: {file_path}. "
                f"Ensure data_preflight/outputs/ contains validated artifacts."
            )
    
    def load_zones(self) -> gpd.GeoDataFrame:
        """
        Load candidate zones from candidate_zones_real.geojson.
        
        Returns:
            GeoDataFrame containing zone geometries, labels, and reach memberships
            
        Raises:
            FileNotFoundError: If candidate_zones_real.geojson is missing
        """
        file_path = self.data_dir / "candidate_zones_real.geojson"
        try:
            return gpd.read_file(file_path)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Required preflight file not found: {file_path}. "
                f"Ensure data_preflight/outputs/ contains validated artifacts."
            )
    
    def load_sampling_sites(self) -> pd.DataFrame:
        """
        Load sampling sites from candidate_sampling_sites.csv.
        
        Returns:
            DataFrame containing sites B, C, D with coordinates, HYRIV_IDs,
            network distances, and validation status
            
        Raises:
            FileNotFoundError: If candidate_sampling_sites.csv is missing
        """
        file_path = self.data_dir / "candidate_sampling_sites.csv"
        try:
            return pd.read_csv(file_path)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Required preflight file not found: {file_path}. "
                f"Ensure data_preflight/outputs/ contains validated artifacts."
            )
    
    def load_validation_metadata(self) -> dict[str, Any]:
        """
        Load validation metadata from sampling_design_validation.json.
        
        Returns:
            Dictionary containing validation results, convergence points,
            and quality checks
            
        Raises:
            FileNotFoundError: If sampling_design_validation.json is missing
            json.JSONDecodeError: If the file contains invalid JSON
        """
        file_path = self.data_dir / "sampling_design_validation.json"
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Required preflight file not found: {file_path}. "
                f"Ensure data_preflight/outputs/ contains validated artifacts."
            )

    def load_reach_geometries(self) -> gpd.GeoDataFrame:
        """Load optional validated reach geometry used for map coordinates."""
        file_path = self.data_dir / "upstream_reaches_real.geojson"
        try:
            return gpd.read_file(file_path)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Validated reach geometry not found: {file_path}."
            )
    
    def _validate_required_files(self) -> None:
        """
        Validate that all required preflight files exist.
        
        Raises:
            FileNotFoundError: If any required file is missing, with a clear
                             message indicating which file is missing
        """
        required_files = [
            "site_a.json",
            "upstream_reaches_real.csv",
            "upstream_edges.csv",
            "candidate_zones_real.geojson",
            "candidate_sampling_sites.csv",
            "sampling_design_validation.json"
        ]
        
        missing_files = []
        for filename in required_files:
            file_path = self.data_dir / filename
            if not file_path.exists():
                missing_files.append(str(file_path))
        
        if missing_files:
            raise FileNotFoundError(
                f"Required preflight files not found: {', '.join(missing_files)}. "
                f"Ensure data_preflight/outputs/ contains validated artifacts."
            )


class CarraroHistoricalLoader:
    """Read the independently verified H001 observation from Carraro sources."""

    def __init__(self, data_dir: Path | str | None = None):
        if data_dir is None:
            from config import config

            data_dir = config.CARRARO_DATA_DIR
        self.data_dir = Path(data_dir).expanduser().resolve()

    @staticmethod
    def _matlab_date(serial_day: int):
        return (
            datetime.fromordinal(int(serial_day)) - timedelta(days=366)
        ).date()

    def load_h001(self) -> dict[str, Any]:
        """Return H001 values and exact source provenance."""
        mat_path = self.data_dir / "eDNA_data.mat"
        model_path = self.data_dir / "RUN_MODEL.m"
        if not mat_path.is_file() or not model_path.is_file():
            missing = [
                str(path)
                for path in (mat_path, model_path)
                if not path.is_file()
            ]
            raise FileNotFoundError(
                "Required Carraro source files not found: " + ", ".join(missing)
            )

        source = loadmat(mat_path, squeeze_me=True, struct_as_record=False)
        observation_index = 4
        concentration = float(source["Fs"].S1[observation_index - 1])
        observation_date = self._matlab_date(
            source["Date"].S1[observation_index - 1]
        )

        match = re.search(
            r"station_coord\s*=\s*\[\s*"
            r"(?P<x>\d+(?:\.\d+)?)\s+"
            r"(?P<y>\d+(?:\.\d+)?)\s+"
            r"(?P<reach>\d+)\s*;",
            model_path.read_text(encoding="utf-8"),
        )
        if match is None:
            raise ValueError("RUN_MODEL.m station_coord first row was not found")

        return {
            "case_id": "H001",
            "station": "S1",
            "species_code": "Fs",
            "species": "Fredericella sultana",
            "observation_index": observation_index,
            "date": observation_date,
            "concentration_mol_l": concentration,
            "state": "DETECTED" if concentration > 0.0 else "NONDETECTION",
            "carraro_coordinate": {
                "x": float(match.group("x")),
                "y": float(match.group("y")),
            },
            "carraro_reach_index": int(match.group("reach")),
            "provenance": {
                "edna_source": str(mat_path),
                "date_variable": "Date.S1",
                "concentration_variable": "Fs.S1",
                "matlab_index_1_based": observation_index,
                "station_source": str(model_path),
                "station_variable": "station_coord row 1",
            },
        }
