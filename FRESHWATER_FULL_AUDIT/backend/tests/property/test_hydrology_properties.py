"""
Property-based tests for HydrologyEngine.

These tests validate universal properties across many generated inputs,
ensuring correctness for the full input space rather than specific examples.
"""

import pytest
import pandas as pd
from hypothesis import given, settings, strategies as st

from app.scientific.data_loader import WiggerPreflightLoader
from app.scientific.hydrology.engine import HydrologyEngine


@pytest.fixture(scope="module")
def hydrology_engine():
    """Create a hydrology engine with Wigger network data."""
    loader = WiggerPreflightLoader("../data_preflight/outputs")
    reaches = loader.load_reaches()
    edges = loader.load_edges()
    return HydrologyEngine(reaches=reaches, edges=edges)


@pytest.fixture(scope="module")
def valid_hyriv_ids(hydrology_engine):
    """Get set of all valid HYRIV_IDs from loaded network."""
    return set(hydrology_engine._reaches.keys())


@pytest.fixture(scope="module")
def valid_hyriv_ids_list(valid_hyriv_ids):
    """Get list of all valid HYRIV_IDs for hypothesis sampling."""
    return list(valid_hyriv_ids)


# Feature: edna-backend-foundation, Property 5: HYRIV_ID validation
# Validates: Requirements 2.2, 4.3, 13.2
@given(invalid_id=st.integers(min_value=-1000000, max_value=1000000))
@settings(max_examples=100)
def test_invalid_hyriv_id_rejection(hydrology_engine, valid_hyriv_ids, invalid_id):
    """
    Property: For any HYRIV_ID not in the loaded network, operations should
    raise ValueError with a clear message.
    
    This property ensures that all hydrology operations validate HYRIV_IDs
    and reject invalid ones consistently.
    
    Feature: edna-backend-foundation, Property 5: HYRIV_ID validation
    Validates: Requirements 2.2, 4.3, 13.2
    """
    # Skip if we accidentally generated a valid ID
    if invalid_id in valid_hyriv_ids:
        return
    
    # Test get_reach
    with pytest.raises(ValueError, match="not found in loaded network"):
        hydrology_engine.get_reach(invalid_id)
    
    # Test get_upstream_reaches
    with pytest.raises(ValueError, match="not found in loaded network"):
        hydrology_engine.get_upstream_reaches(invalid_id)
    
    # Test get_downstream_path (start invalid)
    with pytest.raises(ValueError, match="not found in loaded network"):
        hydrology_engine.get_downstream_path(invalid_id)
    
    # Test get_downstream_path (stop invalid) - need a valid start
    valid_id = next(iter(valid_hyriv_ids))
    with pytest.raises(ValueError, match="not found in loaded network"):
        hydrology_engine.get_downstream_path(valid_id, invalid_id)
    
    # Test is_upstream (source invalid)
    with pytest.raises(ValueError, match="not found in loaded network"):
        hydrology_engine.is_upstream(invalid_id, valid_id)
    
    # Test is_upstream (target invalid)
    with pytest.raises(ValueError, match="not found in loaded network"):
        hydrology_engine.is_upstream(valid_id, invalid_id)
    
    # Test first_common_downstream (first invalid)
    with pytest.raises(ValueError, match="not found in loaded network"):
        hydrology_engine.first_common_downstream(invalid_id, valid_id)
    
    # Test first_common_downstream (second invalid)
    with pytest.raises(ValueError, match="not found in loaded network"):
        hydrology_engine.first_common_downstream(valid_id, invalid_id)
    
    # Test network_distance_km (from invalid)
    with pytest.raises(ValueError, match="not found in loaded network"):
        hydrology_engine.network_distance_km(invalid_id, valid_id)
    
    # Test network_distance_km (to invalid)
    with pytest.raises(ValueError, match="not found in loaded network"):
        hydrology_engine.network_distance_km(valid_id, invalid_id)
    
    # Test zone_can_contribute_to_site (zone contains invalid)
    with pytest.raises(ValueError, match="not found in loaded network"):
        hydrology_engine.zone_can_contribute_to_site([invalid_id], valid_id)
    
    # Test zone_can_contribute_to_site (site invalid)
    with pytest.raises(ValueError, match="not found in loaded network"):
        hydrology_engine.zone_can_contribute_to_site([valid_id], invalid_id)


# Feature: edna-backend-foundation, Property 6: Network data loading
# Validates: Requirements 3.5
def test_network_data_loading_matches_source(hydrology_engine, valid_hyriv_ids_list):
    """
    Property: For any known HYRIV_ID in the upstream_reaches_real.csv file,
    querying the reach should return metadata matching the source file exactly
    (NEXT_DOWN, LENGTH_KM, UPLAND_SKM, DIS_AV_CMS).
    
    This property ensures that the hydrology engine loads network data without
    modification and preserves all values exactly as they appear in the source.
    
    Feature: edna-backend-foundation, Property 6: Network data loading
    Validates: Requirements 3.5
    """
    # Load the source data once
    loader = WiggerPreflightLoader("../data_preflight/outputs")
    reaches_df = loader.load_reaches()
    
    # Define the property test function
    @given(hyriv_id=st.sampled_from(valid_hyriv_ids_list))
    @settings(max_examples=100)
    def check_reach_matches_source(hyriv_id):
        # Find the source row
        source_row = reaches_df[reaches_df['HYRIV_ID'] == hyriv_id].iloc[0]
        
        # Get the reach from the engine
        reach = hydrology_engine.get_reach(hyriv_id)
        
        # Verify all metadata matches exactly
        assert reach.hyriv_id == int(source_row['HYRIV_ID'])
        
        # Check NEXT_DOWN (may be NaN/None)
        if pd.notna(source_row['NEXT_DOWN']):
            assert reach.next_down == int(source_row['NEXT_DOWN'])
        else:
            assert reach.next_down is None
        
        # Check LENGTH_KM
        assert reach.length_km == float(source_row['LENGTH_KM'])
        
        # Check UPLAND_SKM
        assert reach.upland_skm == float(source_row['UPLAND_SKM'])
        
        # Check DIS_AV_CMS
        assert reach.dis_av_cms == float(source_row['DIS_AV_CMS'])
    
    # Run the property test
    check_reach_matches_source()
