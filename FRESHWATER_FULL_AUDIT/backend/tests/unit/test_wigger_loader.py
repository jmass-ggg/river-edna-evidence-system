"""
Unit tests for WiggerPreflightLoader.

Tests verify that the loader correctly reads Wigger case preflight data,
including Site A coordinates, candidate zones Z1/Z2/Z3, sampling sites B/C/D,
and provides clear error messages for missing files.
"""

import json
from pathlib import Path
import pytest
import pandas as pd
import geopandas as gpd

from app.scientific.data_loader import WiggerPreflightLoader


class TestWiggerPreflightLoader:
    """Test suite for WiggerPreflightLoader."""
    
    def test_loader_initialization_with_valid_directory(self):
        """Test that loader initializes successfully with valid data directory."""
        # Given a valid data directory (relative to workspace root)
        data_dir = Path("../data_preflight/outputs")
        
        # When initializing the loader
        loader = WiggerPreflightLoader(data_dir)
        
        # Then it should succeed
        assert loader.data_dir == data_dir.resolve()

    def test_default_path_is_independent_of_current_working_directory(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        loader = WiggerPreflightLoader()
        assert loader.load_site_a()["network_representation"]["hyriv_id"] == 20446064
    
    def test_loader_initialization_with_missing_directory(self):
        """Test that loader raises clear error for missing directory."""
        # Given a non-existent data directory
        data_dir = Path("nonexistent/directory")
        
        # When initializing the loader
        # Then it should raise FileNotFoundError with clear message
        with pytest.raises(FileNotFoundError) as exc_info:
            WiggerPreflightLoader(data_dir)
        
        assert "Required preflight files not found" in str(exc_info.value)
    
    def test_load_site_a_with_correct_coordinates(self):
        """
        Test loading Site A (S1) with correct coordinates.
        
        Validates: Requirements 11.1
        """
        # Given a loader (path relative to workspace root from backend/)
        loader = WiggerPreflightLoader("../data_preflight/outputs")
        
        # When loading Site A
        site_a = loader.load_site_a()
        
        # Then it should contain correct coordinates
        assert site_a["station_id"] == "S1"
        assert site_a["target_taxon"] == "Fredericella sultana"
        
        # Verify transformed coordinates (WGS84)
        transformed = site_a["transformed_coordinate"]
        assert transformed["longitude"] == 7.895400745863826
        assert transformed["latitude"] == 47.31400039098192
        
        # Verify network representation
        network = site_a["network_representation"]
        assert network["hyriv_id"] == 20446064
        assert network["next_down"] == 20445973
        assert abs(network["snap_distance_m"] - 64.81356293400535) < 0.001
    
    def test_load_sampling_sites_with_correct_hyriv_ids(self):
        """
        Test loading sites B, C, D with correct HYRIV_IDs.
        
        Validates: Requirements 11.3
        """
        # Given a loader
        loader = WiggerPreflightLoader("../data_preflight/outputs")
        
        # When loading sampling sites
        sites_df = loader.load_sampling_sites()
        
        # Then it should be a DataFrame
        assert isinstance(sites_df, pd.DataFrame)
        assert len(sites_df) >= 4  # A, B, C, D at minimum
        
        # Verify sites A, B, C, D are present
        site_labels = sites_df['site'].tolist()
        assert 'A' in site_labels
        assert 'B' in site_labels
        assert 'C' in site_labels
        assert 'D' in site_labels
        
        # Verify HYRIV_IDs for each site
        site_b = sites_df[sites_df['site'] == 'B'].iloc[0]
        assert site_b['HYRIV_ID'] == 20450127
        assert site_b['zone'] == 'Z2'
        assert abs(site_b['network_distance_to_site_a_km'] - 19.225939051634158) < 0.001
        
        site_c = sites_df[sites_df['site'] == 'C'].iloc[0]
        assert site_c['HYRIV_ID'] == 20451169
        assert site_c['zone'] == 'Z3'
        assert abs(site_c['network_distance_to_site_a_km'] - 23.935939051634158) < 0.001
        
        site_d = sites_df[sites_df['site'] == 'D'].iloc[0]
        assert site_d['HYRIV_ID'] == 20448315
        assert site_d['zone'] == 'Shared trunk (Z2+Z3)'
        assert abs(site_d['network_distance_to_site_a_km'] - 10.940939051634162) < 0.001
        
        site_a = sites_df[sites_df['site'] == 'A'].iloc[0]
        assert site_a['HYRIV_ID'] == 20446064
        assert site_a['network_distance_to_site_a_km'] == 0.0
    
    def test_load_zones_z1_z2_z3(self):
        """
        Test loading candidate zones Z1, Z2, Z3.
        
        Validates: Requirements 11.2
        """
        # Given a loader
        loader = WiggerPreflightLoader("../data_preflight/outputs")
        
        # When loading zones
        zones_gdf = loader.load_zones()
        
        # Then it should be a GeoDataFrame
        assert isinstance(zones_gdf, gpd.GeoDataFrame)
        assert len(zones_gdf) >= 3  # Z1, Z2, Z3 at minimum
        
        # Verify zone labels are present
        zone_labels = zones_gdf['zone'].tolist()
        assert 'Z1' in zone_labels
        assert 'Z2' in zone_labels
        assert 'Z3' in zone_labels
        
        # Verify each zone has geometry and reach information
        for zone_label in ['Z1', 'Z2', 'Z3']:
            zone = zones_gdf[zones_gdf['zone'] == zone_label].iloc[0]
            assert zone.geometry is not None
            assert 'root_hyriv_id' in zone or 'HYRIV_ID' in zone or 'hyriv_id' in zone
    
    def test_load_reaches(self):
        """Test loading reach data from upstream_reaches_real.csv."""
        # Given a loader
        loader = WiggerPreflightLoader("../data_preflight/outputs")
        
        # When loading reaches
        reaches_df = loader.load_reaches()
        
        # Then it should be a DataFrame with HydroRIVERS attributes
        assert isinstance(reaches_df, pd.DataFrame)
        assert len(reaches_df) > 0
        
        # Verify required columns
        required_columns = ['HYRIV_ID', 'NEXT_DOWN', 'LENGTH_KM', 'UPLAND_SKM', 'DIS_AV_CMS']
        for col in required_columns:
            assert col in reaches_df.columns
        
        # Verify Site A reach is present
        site_a_reach = reaches_df[reaches_df['HYRIV_ID'] == 20446064]
        assert len(site_a_reach) == 1
        assert site_a_reach.iloc[0]['NEXT_DOWN'] == 20445973
    
    def test_load_edges(self):
        """Test loading network edges from upstream_edges.csv."""
        # Given a loader
        loader = WiggerPreflightLoader("../data_preflight/outputs")
        
        # When loading edges
        edges_df = loader.load_edges()
        
        # Then it should be a DataFrame
        assert isinstance(edges_df, pd.DataFrame)
        assert len(edges_df) > 0
    
    def test_load_validation_metadata(self):
        """
        Test loading validation metadata.
        
        Validates: Requirements 11.4
        """
        # Given a loader
        loader = WiggerPreflightLoader("../data_preflight/outputs")
        
        # When loading validation metadata
        metadata = loader.load_validation_metadata()
        
        # Then it should be a dictionary with validation results
        assert isinstance(metadata, dict)
        # Metadata should contain validation information
        assert len(metadata) > 0
    
    def test_missing_file_error_messages(self):
        """
        Test that missing files produce clear error messages.
        
        Validates: Requirements 11.5
        """
        # Given a loader pointing to an empty directory
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # When initializing with missing files
            # Then it should raise FileNotFoundError with file paths
            with pytest.raises(FileNotFoundError) as exc_info:
                WiggerPreflightLoader(tmpdir)
            
            error_message = str(exc_info.value)
            assert "Required preflight files not found" in error_message
            assert "site_a.json" in error_message
            assert "upstream_reaches_real.csv" in error_message
            assert "candidate_zones_real.geojson" in error_message
    
    def test_missing_individual_file_error(self):
        """Test error message when loading individual missing file."""
        # Given a loader with a non-existent directory
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files but not all
            (Path(tmpdir) / "site_a.json").write_text("{}")
            (Path(tmpdir) / "upstream_reaches_real.csv").write_text("HYRIV_ID\n")
            (Path(tmpdir) / "upstream_edges.csv").write_text("parent,child\n")
            (Path(tmpdir) / "candidate_zones_real.geojson").write_text('{"type":"FeatureCollection","features":[]}')
            (Path(tmpdir) / "candidate_sampling_sites.csv").write_text("site\n")
            # Missing: sampling_design_validation.json
            
            # When initializing
            # Then it should raise FileNotFoundError for missing file
            with pytest.raises(FileNotFoundError) as exc_info:
                WiggerPreflightLoader(tmpdir)
            
            error_message = str(exc_info.value)
            assert "sampling_design_validation.json" in error_message
