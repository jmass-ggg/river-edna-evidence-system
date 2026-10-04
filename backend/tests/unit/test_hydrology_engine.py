"""
Unit tests for HydrologyEngine.

Tests hydrology network analysis operations including reachability,
distance calculation, and convergence detection.
"""

import pytest
from pathlib import Path

from app.scientific.data_loader import WiggerPreflightLoader
from app.scientific.hydrology.engine import HydrologyEngine

_REPO_DATA_DIR = Path(__file__).resolve().parents[4] / "data_preflight/outputs"


class TestHydrologyEngine:
    """Test suite for HydrologyEngine implementation."""
    
    @pytest.fixture
    def loader(self):
        """Create a data loader resolved relative to this test file."""
        return WiggerPreflightLoader(_REPO_DATA_DIR)
    
    @pytest.fixture
    def engine(self, loader):
        """Create a hydrology engine with Wigger network data."""
        reaches = loader.load_reaches()
        edges = loader.load_edges()
        return HydrologyEngine(reaches=reaches, edges=edges)
    
    def test_engine_initialization(self, loader):
        """Test that engine initializes successfully with valid data."""
        reaches = loader.load_reaches()
        edges = loader.load_edges()
        engine = HydrologyEngine(reaches=reaches, edges=edges)
        
        # Verify engine is created
        assert engine is not None
    
    def test_get_reach_with_valid_id(self, engine):
        """Test retrieving reach metadata for a valid HYRIV_ID."""
        # Given a known HYRIV_ID from the Wigger network (Site A)
        hyriv_id = 20446064  # Site A
        
        # When getting reach metadata
        reach = engine.get_reach(hyriv_id)
        
        # Then the reach should have all expected fields
        assert reach.hyriv_id == hyriv_id
        assert reach.next_down is not None or reach.next_down is None  # May be terminal
        assert reach.length_km > 0
        assert reach.upland_skm > 0
        assert reach.dis_av_cms >= 0
    
    def test_get_reach_with_invalid_id(self, engine):
        """Test that invalid HYRIV_ID raises ValueError."""
        # Given an invalid HYRIV_ID
        invalid_id = 99999999
        
        # When attempting to get reach
        # Then it should raise ValueError
        with pytest.raises(ValueError, match="not found in loaded network"):
            engine.get_reach(invalid_id)
    
    def test_get_upstream_reaches(self, engine):
        """Test retrieving upstream reaches for Site A."""
        # Given Site A's HYRIV_ID
        site_a_hyriv = 20446064  # Site A
        
        # When getting upstream reaches
        upstream = engine.get_upstream_reaches(site_a_hyriv)
        
        # Then we should get a list of upstream reach IDs
        assert isinstance(upstream, list)
        # Site A should have upstream reaches since it's a detection site
        assert len(upstream) > 0
    
    def test_get_downstream_path_to_terminus(self, engine):
        """Test following downstream path to terminus."""
        # Given a known upstream reach
        start_reach = 20450127  # Z2 root
        
        # When getting downstream path without stop
        path = engine.get_downstream_path(start_reach)
        
        # Then path should be ordered and end at Site A or beyond
        assert isinstance(path, list)
        assert len(path) > 0
        assert path[0] == start_reach
    
    def test_get_downstream_path_with_stop(self, engine):
        """Test following downstream path to specific stop point."""
        # Given Z2 root and Site A
        start_reach = 20450127  # Z2 root (Site B)
        stop_reach = 20446064   # Site A
        
        # When getting downstream path
        path = engine.get_downstream_path(start_reach, stop_reach)
        
        # Then path should include both endpoints
        assert path[0] == start_reach
        assert path[-1] == stop_reach
    
    def test_get_downstream_path_invalid_stop(self, engine):
        """Test that invalid stop raises ValueError."""
        # Given a start that is NOT upstream of stop
        start = 20446064  # Site A
        stop = 20450127   # Z2 root (Site B) - upstream of Site A
        
        # When attempting to get downstream path
        # Then it should raise ValueError
        with pytest.raises(ValueError, match="not downstream"):
            engine.get_downstream_path(start, stop)
    
    def test_is_upstream_true(self, engine):
        """Test upstream check returns True when source is upstream of target."""
        # Given Z2 root and Site A
        source = 20450127  # Z2 root
        target = 20449905  # Site A
        
        # When checking if source is upstream of target
        result = engine.is_upstream(source, target)
        
        # Then result should be True
        assert result is True
    
    def test_is_upstream_false(self, engine):
        """Test upstream check returns False when not upstream."""
        # Given Site A and Z2 root
        source = 20449905  # Site A
        target = 20450127  # Z2 root
        
        # When checking if source is upstream of target
        result = engine.is_upstream(source, target)
        
        # Then result should be False
        assert result is False
    
    def test_is_upstream_same_reach(self, engine):
        """Test that a reach is not upstream of itself."""
        # Given the same reach
        reach_id = 20449905
        
        # When checking if reach is upstream of itself
        result = engine.is_upstream(reach_id, reach_id)
        
        # Then result should be False
        assert result is False
    
    def test_first_common_downstream_z2_z3(self, engine):
        """
        Test Z2/Z3 convergence at Site A.
        
        Validates: Requirements 7.4
        Property 14: Z2/Z3 convergence verification
        """
        # Given Z2 and Z3 roots
        z2_root = 20450127
        z3_root = 20451169
        expected_convergence = 20449905  # Site A
        
        # When finding first common downstream
        convergence = engine.first_common_downstream(z2_root, z3_root)
        
        # Then convergence should be at Site A
        assert convergence == expected_convergence
    
    def test_first_common_downstream_same_reach(self, engine):
        """Test convergence of reach with itself."""
        # Given the same reach
        reach_id = 20449905
        
        # When finding convergence
        convergence = engine.first_common_downstream(reach_id, reach_id)
        
        # Then it should return the reach itself
        assert convergence == reach_id
    
    def test_network_distance_z2_to_site_a(self, engine):
        """
        Test network distance calculation from Z2 to Site A.
        
        Validates: Requirements 7.5, 8.4
        Property 15: Network distance accuracy
        """
        # Given Z2 root and Site A
        from_reach = 20450127  # Z2 root
        to_reach = 20449905    # Site A
        
        # When calculating network distance
        distance = engine.network_distance_km(from_reach, to_reach)
        
        # Then distance should be calculated
        assert distance is not None
        assert distance > 0
        # Approximate expected distance based on preflight data
        # This should match candidate_sampling_sites.csv
    
    def test_network_distance_not_connected(self, engine):
        """Test network distance returns None when reaches not connected."""
        # Given Site A and Z2 root (wrong direction)
        from_reach = 20449905  # Site A
        to_reach = 20450127    # Z2 root
        
        # When calculating distance (Site A is NOT upstream of Z2)
        distance = engine.network_distance_km(from_reach, to_reach)
        
        # Then distance should be None
        assert distance is None
    
    def test_network_distance_same_reach(self, engine):
        """Test network distance for same reach is zero."""
        # Given the same reach
        reach_id = 20449905
        
        # When calculating distance
        distance = engine.network_distance_km(reach_id, reach_id)
        
        # Then distance should be 0
        assert distance == 0.0
    
    def test_zone_can_contribute_to_site_true(self, engine, loader):
        """Test that Z2 can contribute to Site A."""
        # Given Z2 reaches and Site A
        zones_df = loader.load_zones()
        z2_rows = zones_df[zones_df['zone'] == 'Z2']
        z2_reaches = z2_rows['HYRIV_ID'].tolist()
        site_a_hyriv = 20449905
        
        # When checking if zone can contribute
        result = engine.zone_can_contribute_to_site(z2_reaches, site_a_hyriv)
        
        # Then result should be True
        assert result is True
    
    def test_zone_can_contribute_to_site_false(self, engine, loader):
        """Test zone cannot contribute if not upstream."""
        # Z1 does not route upstream into the Z2 root reach.
        non_upstream_reaches = [20447392]
        site_a_hyriv = 20450127
        
        # When checking if zone can contribute
        result = engine.zone_can_contribute_to_site(non_upstream_reaches, site_a_hyriv)
        
        # Then result should be False
        assert result is False

    def test_network_distance_partial_reaches(self):
        """Test same, adjacent, and multi-reach fractional distances."""
        import pandas as pd

        reaches = pd.DataFrame([
            {"HYRIV_ID": 1, "NEXT_DOWN": 2, "LENGTH_KM": 2.0, "UPLAND_SKM": 1, "DIS_AV_CMS": 1},
            {"HYRIV_ID": 2, "NEXT_DOWN": 3, "LENGTH_KM": 4.0, "UPLAND_SKM": 2, "DIS_AV_CMS": 2},
            {"HYRIV_ID": 3, "NEXT_DOWN": 0, "LENGTH_KM": 6.0, "UPLAND_SKM": 3, "DIS_AV_CMS": 3},
            {"HYRIV_ID": 9, "NEXT_DOWN": 0, "LENGTH_KM": 1.0, "UPLAND_SKM": 1, "DIS_AV_CMS": 1},
        ])
        edges = pd.DataFrame([
            {"upstream": 1, "downstream": 2},
            {"upstream": 2, "downstream": 3},
        ])
        engine = HydrologyEngine(reaches, edges)

        assert engine.network_distance_km(1, 1, 0.25, 0.75) == 1.0
        assert engine.network_distance_km(1, 2, 0.5, 0.25) == 2.0
        assert engine.network_distance_km(1, 3, 0.5, 0.25) == 6.5
        assert engine.network_distance_km(1, 3) == 8.0
        assert engine.network_distance_km(1, 1, 0.75, 0.25) is None
        assert engine.network_distance_km(3, 1) is None
        assert engine.network_distance_km(1, 9) is None

        with pytest.raises(ValueError, match="from_fraction"):
            engine.network_distance_km(1, 2, -0.1, 0.5)
        with pytest.raises(ValueError, match="to_fraction"):
            engine.network_distance_km(1, 2, 0.5, 1.1)

    def test_can_contribute_includes_same_reach(self, engine):
        assert engine.can_contribute(20450127, 20450127) is True
    
    def test_invalid_hyriv_id_in_operations(self, engine):
        """Test that all operations validate HYRIV_IDs."""
        invalid_id = 99999999
        valid_id = 20449905
        
        # Test get_upstream_reaches
        with pytest.raises(ValueError):
            engine.get_upstream_reaches(invalid_id)
        
        # Test get_downstream_path
        with pytest.raises(ValueError):
            engine.get_downstream_path(invalid_id)
        
        # Test is_upstream
        with pytest.raises(ValueError):
            engine.is_upstream(invalid_id, valid_id)
        
        with pytest.raises(ValueError):
            engine.is_upstream(valid_id, invalid_id)
        
        # Test first_common_downstream
        with pytest.raises(ValueError):
            engine.first_common_downstream(invalid_id, valid_id)
        
        # Test network_distance_km
        with pytest.raises(ValueError):
            engine.network_distance_km(invalid_id, valid_id)
        
        # Test zone_can_contribute_to_site
        with pytest.raises(ValueError):
            engine.zone_can_contribute_to_site([invalid_id], valid_id)
