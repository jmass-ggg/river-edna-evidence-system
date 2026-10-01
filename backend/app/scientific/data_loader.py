"""
Wigger preflight data loader.

This module loads validated Wigger case data from preflight artifacts.
It reads existing files and validates their structure without modifying values.
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import geopandas as gpd


class WiggerPreflightLoader:
    """
    Loads validated Wigger case data from preflight artifacts.
    
    This loader reads existing files and validates their structure
    without modifying values. All data is read-only.
    """
    
    def __init__(self, data_dir: Path | str = Path("data_preflight/outputs")):
        """
        Initialize the Wigger preflight data loader.
        
        Args:
            data_dir: Path to the directory containing preflight output files
            
        Raises:
            FileNotFoundError: If required files are missing
        """
        self.data_dir = Path(data_dir)
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
