#!/usr/bin/env python3
"""
Generate candidate sampling sites B, C, and D for the Wigger watershed eDNA case study.

This script:
1. Revalidates the upstream graph topology
2. Generates Site B (Z2-specific)
3. Generates Site C (Z3-specific)
4. Generates Site D (shared trunk)
5. Validates directed reachability
6. Calculates network distances
7. Outputs all artifacts

Scientific principle: Use REAL HydroRIVERS geometries and directed topology.
Do not invent coordinates.
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import json
from pathlib import Path
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import linemerge
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Paths
RAW_DIR = Path("data_preflight/raw/hydrorivers")
OUTPUT_DIR = Path("data_preflight/outputs")
HYDRORIVERS_SHP = RAW_DIR / "HydroRIVERS_v10_eu.shp"

# Known verified values
SITE_A_HYRIV_ID = 20446064
SITE_A_LAT = 47.31400039098192
SITE_A_LON = 7.895400745863826
SITE_A_ORIGINAL_X = 634537.17
SITE_A_ORIGINAL_Y = 240447.56

Z1_ROOT = 20447392
Z2_ROOT = 20450127
Z3_ROOT = 20451169

def load_graph():
    """Load the upstream graph from CSV files."""
    reaches = pd.read_csv(OUTPUT_DIR / "upstream_reaches_real.csv")
    edges = pd.read_csv(OUTPUT_DIR / "upstream_edges.csv")
    return reaches, edges

def build_directed_graph(edges):
    """Build a directed graph from edges (upstream -> downstream)."""
    graph = {}
    reverse_graph = {}
    
    for _, row in edges.iterrows():
        upstream = row['upstream']
        downstream = row['downstream']
        
        # Forward: upstream -> downstream
        if upstream not in graph:
            graph[upstream] = []
        graph[upstream].append(downstream)
        
        # Reverse: downstream -> [upstreams]
        if downstream not in reverse_graph:
            reverse_graph[downstream] = []
        reverse_graph[downstream].append(upstream)
    
    return graph, reverse_graph

def find_path_to_target(start_id, target_id, graph):
    """Find path from start_id to target_id using BFS."""
    if start_id == target_id:
        return [start_id]
    
    queue = [(start_id, [start_id])]
    visited = {start_id}
    
    while queue:
        current, path = queue.pop(0)
        
        if current in graph:
            for downstream in graph[current]:
                if downstream == target_id:
                    return path + [downstream]
                
                if downstream not in visited:
                    visited.add(downstream)
                    queue.append((downstream, path + [downstream]))
    
    return None

def get_all_upstream_reaches(root_id, reverse_graph):
    """Get all reaches upstream of root_id (including root)."""
    upstream_set = {root_id}
    queue = [root_id]
    
    while queue:
        current = queue.pop(0)
        if current in reverse_graph:
            for upstream in reverse_graph[current]:
                if upstream not in upstream_set:
                    upstream_set.add(upstream)
                    queue.append(upstream)
    
    return upstream_set

def find_first_common_downstream(zone1_root, zone2_root, graph):
    """Find the first common downstream reach where two zones converge."""
    # Get paths from both roots to Site A
    path1 = find_path_to_target(zone1_root, SITE_A_HYRIV_ID, graph)
    path2 = find_path_to_target(zone2_root, SITE_A_HYRIV_ID, graph)
    
    if not path1 or not path2:
        return None
    
    # Find first common reach
    path1_set = set(path1)
    for reach in path2:
        if reach in path1_set:
            return reach
    
    return None

def get_midpoint_coordinate(geometry):
    """Get the midpoint coordinate of a LineString or MultiLineString."""
    if isinstance(geometry, MultiLineString):
        geometry = linemerge(geometry)
    
    if isinstance(geometry, LineString):
        midpoint = geometry.interpolate(0.5, normalized=True)
        return midpoint.y, midpoint.x  # lat, lon
    
    return None, None

def calculate_network_distance(from_reach_id, to_reach_id, graph, reaches_df, from_fraction=0.5, to_fraction=0.5):
    """Calculate network distance along river from one reach to another.
    
    Args:
        from_reach_id: Starting reach ID
        to_reach_id: Target reach ID
        graph: Directed graph (upstream -> downstream)
        reaches_df: DataFrame with reach information including LENGTH_KM
        from_fraction: Fraction along the from_reach (0.5 = midpoint)
    
    Returns:
        Distance in km, or None if no path exists
    """
    # Find path
    path = find_path_to_target(from_reach_id, to_reach_id, graph)
    if not path:
        return None
    
    if len(path) == 1:
        return max(0.0, to_fraction - from_fraction) * float(reaches_df.loc[reaches_df['HYRIV_ID'] == from_reach_id, 'LENGTH_KM'].iloc[0])

    total_distance = 0.0
    
    for i, reach_id in enumerate(path):
        reach_row = reaches_df[reaches_df['HYRIV_ID'] == reach_id]
        if reach_row.empty:
            return None
        
        reach_length = reach_row.iloc[0]['LENGTH_KM']
        
        if i == 0:
            # Starting reach: use only the fraction from sample point to end
            total_distance += reach_length * (1.0 - from_fraction)
        elif i == len(path) - 1:
            # Destination is a midpoint, not the downstream end of its reach.
            total_distance += reach_length * to_fraction
        else:
            # Middle reaches: count full length
            total_distance += reach_length
    
    return total_distance

def reachability_test(from_reach_id, zone_root, reverse_graph):
    """Test if water from zone_root can reach from_reach_id.
    
    In directed river network: water flows downstream.
    Zone contributions can reach a point if that point is downstream of the zone.
    Equivalently: the zone root is in the upstream network of the point.
    """
    upstream_of_point = get_all_upstream_reaches(from_reach_id, reverse_graph)
    return zone_root in upstream_of_point

print("=" * 80)
print("WIGGER WATERSHED eDNA SAMPLING SITE GENERATION")
print("=" * 80)

# ============================================================================
# PHASE 1: Revalidate the graph
# ============================================================================
print("\nPHASE 1: GRAPH REVALIDATION")
print("-" * 80)

reaches, edges = load_graph()
graph, reverse_graph = build_directed_graph(edges)

# Verify Site A
print(f"Site A HYRIV_ID: {SITE_A_HYRIV_ID}")
assert SITE_A_HYRIV_ID in reaches['HYRIV_ID'].values, "Site A not in graph"

# Verify zones
print(f"Z1 root: {Z1_ROOT}")
print(f"Z2 root: {Z2_ROOT}")
print(f"Z3 root: {Z3_ROOT}")

for zone_root, zone_name in [(Z1_ROOT, "Z1"), (Z2_ROOT, "Z2"), (Z3_ROOT, "Z3")]:
    assert zone_root in reaches['HYRIV_ID'].values, f"{zone_name} root not in graph"
    path = find_path_to_target(zone_root, SITE_A_HYRIV_ID, graph)
    assert path is not None, f"{zone_name} does not route to Site A"
    print(f"{zone_name} routes to Site A: {len(path)} reaches")

# Get zone memberships
z1_reaches = get_all_upstream_reaches(Z1_ROOT, reverse_graph)
z2_reaches = get_all_upstream_reaches(Z2_ROOT, reverse_graph)
z3_reaches = get_all_upstream_reaches(Z3_ROOT, reverse_graph)

# Verify mutual non-overlap
z1_z2_overlap = z1_reaches & z2_reaches
z1_z3_overlap = z1_reaches & z3_reaches
z2_z3_overlap = z2_reaches & z3_reaches

print(f"Z1 reach count: {len(z1_reaches)}")
print(f"Z2 reach count: {len(z2_reaches)}")
print(f"Z3 reach count: {len(z3_reaches)}")
print(f"Z1 ∩ Z2: {len(z1_z2_overlap)} reaches")
print(f"Z1 ∩ Z3: {len(z1_z3_overlap)} reaches")
print(f"Z2 ∩ Z3: {len(z2_z3_overlap)} reaches")

assert len(z1_z2_overlap) == 0, "Z1 and Z2 overlap"
assert len(z1_z3_overlap) == 0, "Z1 and Z3 overlap"
assert len(z2_z3_overlap) == 0, "Z2 and Z3 overlap"

# Find Z2/Z3 convergence
z2_z3_convergence = find_first_common_downstream(Z2_ROOT, Z3_ROOT, graph)
print(f"Z2/Z3 first convergence: {z2_z3_convergence}")
assert z2_z3_convergence is not None, "Z2/Z3 convergence not found"

# Verify convergence is upstream of Site A
conv_path_to_a = find_path_to_target(z2_z3_convergence, SITE_A_HYRIV_ID, graph)
assert conv_path_to_a is not None, "Convergence does not route to Site A"
print(f"Convergence to Site A: {len(conv_path_to_a)} reaches")

print("\n✓ Graph revalidation: VERIFIED")

# ============================================================================
# PHASE 2: Generate Site B (Z2-specific)
# ============================================================================
print("\nPHASE 2: GENERATE SITE B (Z2-specific)")
print("-" * 80)

# Strategy: Select a reach in Z2 that is:
# 1. Not in the shared trunk (below convergence)
# 2. Reasonably upstream to provide discrimination
# 3. On a significant branch (not a tiny tributary)

# Get shared trunk reaches (from convergence to Site A)
shared_trunk = set(find_path_to_target(z2_z3_convergence, SITE_A_HYRIV_ID, graph))

# Z2-specific reaches (excluding shared trunk)
z2_specific = z2_reaches - shared_trunk
print(f"Z2-specific reaches (excluding shared trunk): {len(z2_specific)}")

# Load full shapefile for geometry
gdf_full = gpd.read_file(HYDRORIVERS_SHP)

# Preserve the historical observation and derive a separate network position.
# Fractions are measured on the projected LineString in its stored direction,
# which runs upstream -> downstream for this reach.
site_a_geom = gdf_full[gdf_full['HYRIV_ID'] == SITE_A_HYRIV_ID].iloc[0]['geometry']
site_a_line_metric = gpd.GeoSeries([site_a_geom], crs=gdf_full.crs).to_crs("EPSG:2056").iloc[0]
site_a_historical_metric = gpd.GeoSeries(
    [Point(SITE_A_LON, SITE_A_LAT)], crs="EPSG:4326"
).to_crs("EPSG:2056").iloc[0]
site_a_projected_distance = site_a_line_metric.project(site_a_historical_metric)
site_a_fraction = site_a_projected_distance / site_a_line_metric.length
site_a_snap_metric = site_a_line_metric.interpolate(site_a_projected_distance)
site_a_snap_wgs84 = gpd.GeoSeries(
    [site_a_snap_metric], crs="EPSG:2056"
).to_crs("EPSG:4326").iloc[0]
SITE_A_SNAP_LAT = float(site_a_snap_wgs84.y)
SITE_A_SNAP_LON = float(site_a_snap_wgs84.x)
SITE_A_SNAP_DISTANCE_M = float(site_a_historical_metric.distance(site_a_snap_metric))
gdf_z2_specific = gdf_full[gdf_full['HYRIV_ID'].isin(z2_specific)].copy()

# Selection criterion: Choose Z2 root itself (largest UPLAND_SKM in Z2-specific)
# This ensures we're on the main Z2 branch
z2_reaches_data = reaches[reaches['HYRIV_ID'].isin(z2_specific)]
z2_candidate = z2_reaches_data.loc[z2_reaches_data['UPLAND_SKM'].idxmax()]
site_b_hyriv_id = int(z2_candidate['HYRIV_ID'])

print(f"Site B HYRIV_ID: {site_b_hyriv_id}")
print(f"  UPLAND_SKM: {z2_candidate['UPLAND_SKM']}")
print(f"  LENGTH_KM: {z2_candidate['LENGTH_KM']}")

# Get geometry and calculate midpoint
site_b_geom = gdf_full[gdf_full['HYRIV_ID'] == site_b_hyriv_id].iloc[0]['geometry']
site_b_lat, site_b_lon = get_midpoint_coordinate(site_b_geom)

print(f"  Latitude: {site_b_lat}")
print(f"  Longitude: {site_b_lon}")

# Verify B belongs to Z2 and not Z3
assert site_b_hyriv_id in z2_reaches, "Site B not in Z2"
assert site_b_hyriv_id not in z3_reaches, "Site B in Z3 (should not be)"

# Calculate distances
b_to_conv = calculate_network_distance(site_b_hyriv_id, z2_z3_convergence, graph, reaches)
b_to_a_midpoint = calculate_network_distance(site_b_hyriv_id, SITE_A_HYRIV_ID, graph, reaches)
b_to_a = calculate_network_distance(
    site_b_hyriv_id, SITE_A_HYRIV_ID, graph, reaches, to_fraction=site_a_fraction
)

print(f"  Network distance to convergence: {b_to_conv:.2f} km")
print(f"  Network distance to Site A: {b_to_a:.2f} km")

# Verify downstream path
b_path = find_path_to_target(site_b_hyriv_id, SITE_A_HYRIV_ID, graph)
assert b_path is not None, "Site B does not route to Site A"
assert z2_z3_convergence in b_path, "Site B path does not pass through convergence"

print("✓ Site B: VERIFIED")

# ============================================================================
# PHASE 3: Generate Site C (Z3-specific)
# ============================================================================
print("\nPHASE 3: GENERATE SITE C (Z3-specific)")
print("-" * 80)

# Same strategy for Z3
z3_specific = z3_reaches - shared_trunk
print(f"Z3-specific reaches (excluding shared trunk): {len(z3_specific)}")

# Select Z3 root (largest UPLAND_SKM in Z3-specific)
z3_reaches_data = reaches[reaches['HYRIV_ID'].isin(z3_specific)]
z3_candidate = z3_reaches_data.loc[z3_reaches_data['UPLAND_SKM'].idxmax()]
site_c_hyriv_id = int(z3_candidate['HYRIV_ID'])

print(f"Site C HYRIV_ID: {site_c_hyriv_id}")
print(f"  UPLAND_SKM: {z3_candidate['UPLAND_SKM']}")
print(f"  LENGTH_KM: {z3_candidate['LENGTH_KM']}")

# Get geometry and calculate midpoint
site_c_geom = gdf_full[gdf_full['HYRIV_ID'] == site_c_hyriv_id].iloc[0]['geometry']
site_c_lat, site_c_lon = get_midpoint_coordinate(site_c_geom)

print(f"  Latitude: {site_c_lat}")
print(f"  Longitude: {site_c_lon}")

# Verify C belongs to Z3 and not Z2
assert site_c_hyriv_id in z3_reaches, "Site C not in Z3"
assert site_c_hyriv_id not in z2_reaches, "Site C in Z2 (should not be)"

# Calculate distances
c_to_conv = calculate_network_distance(site_c_hyriv_id, z2_z3_convergence, graph, reaches)
c_to_a_midpoint = calculate_network_distance(site_c_hyriv_id, SITE_A_HYRIV_ID, graph, reaches)
c_to_a = calculate_network_distance(
    site_c_hyriv_id, SITE_A_HYRIV_ID, graph, reaches, to_fraction=site_a_fraction
)

print(f"  Network distance to convergence: {c_to_conv:.2f} km")
print(f"  Network distance to Site A: {c_to_a:.2f} km")

# Verify downstream path
c_path = find_path_to_target(site_c_hyriv_id, SITE_A_HYRIV_ID, graph)
assert c_path is not None, "Site C does not route to Site A"
assert z2_z3_convergence in c_path, "Site C path does not pass through convergence"

print("✓ Site C: VERIFIED")

# ============================================================================
# PHASE 4: Generate Site D (shared trunk)
# ============================================================================
print("\nPHASE 4: GENERATE SITE D (shared trunk)")
print("-" * 80)

# Strategy: Select a reach in shared trunk that is:
# 1. Not the convergence point itself (too close to merge)
# 2. Not Site A (we already have that)
# 3. Intermediate location for comparison

shared_trunk_list = list(shared_trunk)
shared_trunk_list.remove(SITE_A_HYRIV_ID)  # Remove Site A

# Select reach with moderate distance from convergence
# Get the one that's roughly in the middle of the shared trunk
shared_trunk_data = reaches[reaches['HYRIV_ID'].isin(shared_trunk_list)]

# Choose based on distance from convergence: not first, not last
# Sort by distance to Site A (descending), pick middle
shared_trunk_data = shared_trunk_data.copy()
shared_trunk_data['dist_to_a'] = shared_trunk_data['HYRIV_ID'].apply(
    lambda x: calculate_network_distance(x, SITE_A_HYRIV_ID, graph, reaches, from_fraction=0.5)
)
shared_trunk_data = shared_trunk_data.sort_values('dist_to_a', ascending=False)

# Pick middle reach (or close to it)
middle_idx = len(shared_trunk_data) // 2
site_d_candidate = shared_trunk_data.iloc[middle_idx]
site_d_hyriv_id = int(site_d_candidate['HYRIV_ID'])

print(f"Site D HYRIV_ID: {site_d_hyriv_id}")
print(f"  LENGTH_KM: {site_d_candidate['LENGTH_KM']}")

# Get geometry and calculate midpoint
site_d_geom = gdf_full[gdf_full['HYRIV_ID'] == site_d_hyriv_id].iloc[0]['geometry']
site_d_lat, site_d_lon = get_midpoint_coordinate(site_d_geom)

print(f"  Latitude: {site_d_lat}")
print(f"  Longitude: {site_d_lon}")

# Calculate distances
d_to_conv = calculate_network_distance(z2_z3_convergence, site_d_hyriv_id, graph, reaches)
d_to_a_midpoint = calculate_network_distance(site_d_hyriv_id, SITE_A_HYRIV_ID, graph, reaches)
d_to_a = calculate_network_distance(
    site_d_hyriv_id, SITE_A_HYRIV_ID, graph, reaches, to_fraction=site_a_fraction
)

print(f"  Network distance from convergence: {d_to_conv:.2f} km")
print(f"  Network distance to Site A: {d_to_a:.2f} km")

# Verify D is in shared trunk
assert site_d_hyriv_id in shared_trunk, "Site D not in shared trunk"

# Verify both Z2 and Z3 can reach D
z2_reaches_d = reachability_test(site_d_hyriv_id, Z2_ROOT, reverse_graph)
z3_reaches_d = reachability_test(site_d_hyriv_id, Z3_ROOT, reverse_graph)
assert z2_reaches_d, "Z2 cannot reach Site D"
assert z3_reaches_d, "Z3 cannot reach Site D"

print("✓ Site D: VERIFIED")

# ============================================================================
# PHASE 5: Directed discrimination test
# ============================================================================
print("\nPHASE 5: DIRECTED DISCRIMINATION TEST")
print("-" * 80)

sites = {
    'A': SITE_A_HYRIV_ID,
    'B': site_b_hyriv_id,
    'C': site_c_hyriv_id,
    'D': site_d_hyriv_id
}

discrimination_results = []

for site_name, site_id in sites.items():
    z1_can_reach = reachability_test(site_id, Z1_ROOT, reverse_graph)
    z2_can_reach = reachability_test(site_id, Z2_ROOT, reverse_graph)
    z3_can_reach = reachability_test(site_id, Z3_ROOT, reverse_graph)
    
    discrimination_results.append({
        'Site': site_name,
        'HYRIV_ID': site_id,
        'Receives_Z1': z1_can_reach,
        'Receives_Z2': z2_can_reach,
        'Receives_Z3': z3_can_reach,
        'Signature': f"[{int(z1_can_reach)},{int(z2_can_reach)},{int(z3_can_reach)}]"
    })
    
    print(f"Site {site_name}: Z1={z1_can_reach}, Z2={z2_can_reach}, Z3={z3_can_reach}")

discrimination_df = pd.DataFrame(discrimination_results)

print("\nDiscrimination signatures:")
print(discrimination_df[['Site', 'Signature']])

# ============================================================================
# PHASE 6: Network distances
# ============================================================================
print("\nPHASE 6: NETWORK DISTANCES")
print("-" * 80)

distance_results = []

for site_name, site_id in [('B', site_b_hyriv_id), ('C', site_c_hyriv_id), ('D', site_d_hyriv_id)]:
    if site_name in ['B', 'C']:
        dist_to_conv = calculate_network_distance(site_id, z2_z3_convergence, graph, reaches)
    else:  # D
        dist_to_conv = calculate_network_distance(z2_z3_convergence, site_id, graph, reaches)
    
    dist_to_a = calculate_network_distance(
        site_id, SITE_A_HYRIV_ID, graph, reaches, to_fraction=site_a_fraction
    )
    
    distance_results.append({
        'Site': site_name,
        'HYRIV_ID': site_id,
        'Distance_to_Convergence_km': dist_to_conv,
        'Distance_to_Site_A_km': dist_to_a
    })
    
    print(f"Site {site_name}: {dist_to_conv:.2f} km to convergence, {dist_to_a:.2f} km to Site A")

distance_df = pd.DataFrame(distance_results)

print("\n✓ Network distances calculated")

print("\n" + "=" * 80)
print("SITE GENERATION COMPLETE")
print("=" * 80)


# ============================================================================
# OUTPUT GENERATION
# ============================================================================
print("\nGENERATING OUTPUT ARTIFACTS...")
print("-" * 80)

# 1. Candidate sampling sites CSV
sites_data = [
    {
        'site': 'A',
        'role': 'Reference site (positive detection)',
        'HYRIV_ID': SITE_A_HYRIV_ID,
        'latitude': SITE_A_LAT,
        'longitude': SITE_A_LON,
        'network_latitude': SITE_A_SNAP_LAT,
        'network_longitude': SITE_A_SNAP_LON,
        'snap_distance_m': SITE_A_SNAP_DISTANCE_M,
        'zone': 'Downstream of all zones',
        'network_distance_to_site_a_km': 0.0,
        'old_midpoint_proxy_distance_to_site_a_km': 0.0,
        'network_distance_to_confluence_km': None,
        'selection_reason': 'Historical S1 observation represented on HydroRIVERS by its exact projection onto matched Wigger reach 20446064',
        'validation_status': 'MATCHED'
    },
    {
        'site': 'B',
        'role': 'Z2 branch-specific discriminator',
        'HYRIV_ID': site_b_hyriv_id,
        'latitude': site_b_lat,
        'longitude': site_b_lon,
        'network_latitude': site_b_lat,
        'network_longitude': site_b_lon,
        'snap_distance_m': 0.0,
        'zone': 'Z2',
        'network_distance_to_site_a_km': b_to_a,
        'old_midpoint_proxy_distance_to_site_a_km': b_to_a_midpoint,
        'network_distance_to_confluence_km': b_to_conv,
        'selection_reason': 'Z2 root reach (largest UPLAND_SKM in Z2), located upstream of Z2/Z3 convergence',
        'validation_status': 'VERIFIED'
    },
    {
        'site': 'C',
        'role': 'Z3 branch-specific discriminator',
        'HYRIV_ID': site_c_hyriv_id,
        'latitude': site_c_lat,
        'longitude': site_c_lon,
        'network_latitude': site_c_lat,
        'network_longitude': site_c_lon,
        'snap_distance_m': 0.0,
        'zone': 'Z3',
        'network_distance_to_site_a_km': c_to_a,
        'old_midpoint_proxy_distance_to_site_a_km': c_to_a_midpoint,
        'network_distance_to_confluence_km': c_to_conv,
        'selection_reason': 'Z3 root reach (largest UPLAND_SKM in Z3), located upstream of Z2/Z3 convergence',
        'validation_status': 'VERIFIED'
    },
    {
        'site': 'D',
        'role': 'Shared trunk comparator',
        'HYRIV_ID': site_d_hyriv_id,
        'latitude': site_d_lat,
        'longitude': site_d_lon,
        'network_latitude': site_d_lat,
        'network_longitude': site_d_lon,
        'snap_distance_m': 0.0,
        'zone': 'Shared trunk (Z2+Z3)',
        'network_distance_to_site_a_km': d_to_a,
        'old_midpoint_proxy_distance_to_site_a_km': d_to_a_midpoint,
        'network_distance_to_confluence_km': d_to_conv,
        'selection_reason': 'Mid-point of shared trunk between Z2/Z3 convergence and Site A',
        'validation_status': 'VERIFIED'
    }
]

sites_df = pd.DataFrame(sites_data)
sites_csv_path = OUTPUT_DIR / "candidate_sampling_sites.csv"
sites_df.to_csv(sites_csv_path, index=False)
print(f"✓ Created: {sites_csv_path}")

# 2. Candidate sampling sites GeoJSON
sites_geojson_features = []
for site in sites_data:
    if site['latitude'] is not None and site['longitude'] is not None:
        feature = {
            'type': 'Feature',
            'properties': {
                'site': site['site'],
                'role': site['role'],
                'HYRIV_ID': site['HYRIV_ID'],
                'zone': site['zone'],
                'network_dist_to_a_km': site['network_distance_to_site_a_km'],
                'old_midpoint_proxy_dist_to_a_km': site['old_midpoint_proxy_distance_to_site_a_km'],
                'network_dist_to_conv_km': site['network_distance_to_confluence_km'],
                'historical_latitude': site['latitude'] if site['site'] == 'A' else None,
                'historical_longitude': site['longitude'] if site['site'] == 'A' else None,
                'network_latitude': site['network_latitude'],
                'network_longitude': site['network_longitude'],
                'snap_distance_m': site['snap_distance_m'],
                'selection_reason': site['selection_reason'],
                'validation_status': site['validation_status']
            },
            'geometry': {
                'type': 'Point',
                'coordinates': [site['network_longitude'], site['network_latitude']]
            }
        }
        sites_geojson_features.append(feature)

sites_geojson = {
    'type': 'FeatureCollection',
    'name': 'candidate_sampling_sites',
    'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:OGC:1.3:CRS84'}},
    'features': sites_geojson_features
}

sites_geojson_path = OUTPUT_DIR / "candidate_sampling_sites.geojson"
with open(sites_geojson_path, 'w') as f:
    json.dump(sites_geojson, f, indent=2)
print(f"✓ Created: {sites_geojson_path}")

# 3. Combined zones and sampling sites GeoJSON
# Load zone geometries
zones_gdf = gpd.read_file(OUTPUT_DIR / "candidate_zones_real.geojson")

# Create a comprehensive GeoJSON with all features
combined_features = []

# Add zone reaches
for _, zone_reach in zones_gdf.iterrows():
    feature = {
        'type': 'Feature',
        'properties': {
            'feature_type': 'zone_reach',
            'zone': str(zone_reach['zone']),
            'HYRIV_ID': int(zone_reach['HYRIV_ID']),
            'LENGTH_KM': float(zone_reach['LENGTH_KM']),
            'UPLAND_SKM': float(zone_reach['UPLAND_SKM'])
        },
        'geometry': zone_reach['geometry'].__geo_interface__
    }
    combined_features.append(feature)

# Add shared trunk
shared_trunk_gdf = gdf_full[gdf_full['HYRIV_ID'].isin(shared_trunk)].copy()
for _, trunk_reach in shared_trunk_gdf.iterrows():
    feature = {
        'type': 'Feature',
        'properties': {
            'feature_type': 'shared_trunk',
            'HYRIV_ID': int(trunk_reach['HYRIV_ID']),
            'LENGTH_KM': float(trunk_reach['LENGTH_KM'])
        },
        'geometry': trunk_reach['geometry'].__geo_interface__
    }
    combined_features.append(feature)

# Add convergence point
conv_reach_geom = gdf_full[gdf_full['HYRIV_ID'] == z2_z3_convergence].iloc[0]['geometry']
conv_lat, conv_lon = get_midpoint_coordinate(conv_reach_geom)
convergence_feature = {
    'type': 'Feature',
    'properties': {
        'feature_type': 'convergence',
        'name': 'Z2/Z3 convergence',
        'HYRIV_ID': int(z2_z3_convergence)
    },
    'geometry': {
        'type': 'Point',
        'coordinates': [float(conv_lon), float(conv_lat)]
    }
}
combined_features.append(convergence_feature)

# Add sampling sites
combined_features.extend(sites_geojson_features)

combined_geojson = {
    'type': 'FeatureCollection',
    'name': 'zones_and_sampling_sites',
    'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:OGC:1.3:CRS84'}},
    'features': combined_features
}

combined_geojson_path = OUTPUT_DIR / "zones_and_sampling_sites.geojson"
with open(combined_geojson_path, 'w') as f:
    json.dump(combined_geojson, f, indent=2)
print(f"✓ Created: {combined_geojson_path}")

# 4. Sampling design validation JSON
validation_data = {
    'metadata': {
        'analysis_date': pd.Timestamp.now().isoformat(),
        'source_data': 'HydroRIVERS v1.0 Europe',
        'crs_input': 'EPSG:4326',
        'crs_output': 'EPSG:4326 (WGS84)'
    },
    'graph_validation': {
        'site_a_hyriv_id': int(SITE_A_HYRIV_ID),
        'z1_root': int(Z1_ROOT),
        'z2_root': int(Z2_ROOT),
        'z3_root': int(Z3_ROOT),
        'z2_z3_convergence': int(z2_z3_convergence),
        'z1_reach_count': int(len(z1_reaches)),
        'z2_reach_count': int(len(z2_reaches)),
        'z3_reach_count': int(len(z3_reaches)),
        'zones_mutually_exclusive': True,
        'all_zones_route_to_site_a': True,
        'status': 'VERIFIED'
    },
    'sites': {
        site['site']: {
            'hyriv_id': int(site['HYRIV_ID']),
            'latitude': float(site['latitude']) if site['latitude'] is not None else None,
            'longitude': float(site['longitude']) if site['longitude'] is not None else None,
            'network_latitude': float(site['network_latitude']),
            'network_longitude': float(site['network_longitude']),
            'snap_distance_m': float(site['snap_distance_m']),
            'zone': str(site['zone']),
            'role': str(site['role']),
            'network_distance_to_site_a_km': float(site['network_distance_to_site_a_km']) if site['network_distance_to_site_a_km'] is not None else None,
            'old_midpoint_proxy_distance_to_site_a_km': float(site['old_midpoint_proxy_distance_to_site_a_km']),
            'network_distance_to_confluence_km': float(site['network_distance_to_confluence_km']) if site['network_distance_to_confluence_km'] is not None else None,
            'selection_reason': str(site['selection_reason']),
            'validation_status': str(site['validation_status'])
        }
        for site in sites_data
    },
    'discrimination_test': [
        {k: (int(v) if isinstance(v, (np.integer, np.bool_)) else v) 
         for k, v in row.items()} 
        for row in discrimination_df.to_dict(orient='records')
    ],
    'network_distances': [
        {k: (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, np.integer) else v) 
         for k, v in row.items()} 
        for row in distance_df.to_dict(orient='records')
    ],
    'provenance': {
        'hydrorivers_file': str(HYDRORIVERS_SHP),
        'geometry_method': 'midpoint_of_linestring',
        'distance_method': 'LENGTH_KM: half of starting reach, full intermediate reaches, and the projected geometry fraction of Site A reach',
        'distance_endpoint_note': 'Distances labelled to Site A terminate at the snapped network representation; the historical observation coordinate is preserved separately.',
        'site_a_network_assignment': f'MATCHED to Wigger reach {SITE_A_HYRIV_ID}; snap distance {SITE_A_SNAP_DISTANCE_M:.6f} m in EPSG:2056.',
        'validation_checks': [
            'HYRIV_ID exists in shapefile',
            'Generated B/C/D midpoint coordinates lie on their selected reach geometries',
            'Site A snapped network point lies on matched reach 20446064 while the historical coordinate is preserved',
            'Downstream paths verified programmatically',
            'Z2/Z3 convergence verified programmatically',
            'Zone overlap rules verified',
            'Directed reachability verified'
        ]
    }
}

validation_json_path = OUTPUT_DIR / "sampling_design_validation.json"
with open(validation_json_path, 'w') as f:
    json.dump(validation_data, f, indent=2)
print(f"✓ Created: {validation_json_path}")

# 5. Site A snap validation
site_a_snap_validation = {
    'original_coordinate': {
        'x': SITE_A_ORIGINAL_X,
        'y': SITE_A_ORIGINAL_Y,
        'crs': 'EPSG:21781',
        'latitude': SITE_A_LAT,
        'longitude': SITE_A_LON,
        'wgs84_crs': 'EPSG:4326'
    },
    'snapped_coordinate': {
        'latitude': SITE_A_SNAP_LAT,
        'longitude': SITE_A_SNAP_LON,
        'crs': 'EPSG:4326',
        'x_lv95': float(site_a_snap_metric.x),
        'y_lv95': float(site_a_snap_metric.y),
        'metric_crs': 'EPSG:2056',
        'fraction_along_reach': float(site_a_fraction)
    },
    'snap_distance_m': SITE_A_SNAP_DISTANCE_M,
    'distance_crs': 'EPSG:2056',
    'HYRIV_ID': SITE_A_HYRIV_ID,
    'NEXT_DOWN': 20445973,
    'match_status': 'MATCHED',
    'evidence_summary': [
        '20446064 is the nearest HydroRIVERS reach to historical S1.',
        'Swiss federal swissTLM3D hydrography identifies the watercourse at S1 and at the snap location as Wigger (CH0005070000).',
        'HydroRIVERS 20446064 has Wigger-scale UPLAND_SKM=414.3 and DIS_AV_CMS=10.997 and routes directly into Aare-scale reach 20445973.',
        'Carraro data assign S1 to reach 1 even though the station is about 147.75 m from the nearest reach-1 edge, demonstrating that the source analysis itself uses a network assignment with a larger spatial offset than the HydroRIVERS snap.'
    ],
    'rejected_candidates': [
        {'HYRIV_ID': 20445973, 'snap_distance_m': 139.65631997128298, 'reason': 'Aare-scale downstream main stem: UPLAND_SKM=10350.9, DIS_AV_CMS=270.182; receives 20446064.'},
        {'HYRIV_ID': 20446447, 'snap_distance_m': 140.6384990752673, 'reason': 'Aare-scale upstream main stem: UPLAND_SKM=9936.0, DIS_AV_CMS=259.202; flows to 20445973, not into 20446064.'},
        {'HYRIV_ID': 20445974, 'snap_distance_m': 454.2600199308615, 'reason': 'Small separate tributary: UPLAND_SKM=13.4, DIS_AV_CMS=0.315; flows to Aare reach 20445851.'},
        {'HYRIV_ID': 20445851, 'snap_distance_m': 561.2794606231218, 'reason': 'Aare-scale downstream main stem: UPLAND_SKM=10369.2, DIS_AV_CMS=270.4.'}
    ],
    'sources': [
        'Local raw HydroRIVERS v1.0 Europe shapefile',
        'https://api3.geo.admin.ch/rest/services/api/MapServer/ch.swisstopo.swisstlm3d-gewaessernetz/legend',
        'https://github.com/lucarraro/edna-species-distribution'
    ]
}
site_a_snap_path = OUTPUT_DIR / 'site_a_snap_validation.json'
with open(site_a_snap_path, 'w') as f:
    json.dump(site_a_snap_validation, f, indent=2)
print(f"✓ Created: {site_a_snap_path}")

# 6. Create map visualization
print("\nGenerating map visualization...")

fig, ax = plt.subplots(figsize=(14, 12))

# Plot zone reaches with different colors
zone_colors = {'Z1': '#FF6B6B', 'Z2': '#4ECDC4', 'Z3': '#45B7D1'}
for zone_name, color in zone_colors.items():
    zone_subset = zones_gdf[zones_gdf['zone'] == zone_name]
    zone_subset.plot(ax=ax, color=color, linewidth=2, label=f'{zone_name} ({len(zone_subset)} reaches)')

# Plot shared trunk
shared_trunk_gdf.plot(ax=ax, color='#95A5A6', linewidth=3, label='Shared trunk', alpha=0.8)

# Plot convergence point
ax.plot(conv_lon, conv_lat, 'D', color='purple', markersize=12, 
        label=f'Z2/Z3 convergence ({z2_z3_convergence})', zorder=5)

# Plot sampling sites
site_markers = {'A': 'o', 'B': 's', 'C': '^', 'D': 'v'}
site_colors_map = {'A': 'green', 'B': '#4ECDC4', 'C': '#45B7D1', 'D': '#95A5A6'}

for site in sites_data:
    if site['latitude'] is not None and site['longitude'] is not None:
        ax.plot(site['network_longitude'], site['network_latitude'], 
                marker=site_markers[site['site']], 
                color=site_colors_map[site['site']], 
                markersize=15,
                markeredgecolor='black',
                markeredgewidth=2,
                label=f"Site {site['site']}: {site['role']}",
                zorder=10)
        
        # Add site label
        ax.annotate(f"Site {site['site']}", 
                   xy=(site['network_longitude'], site['network_latitude']),
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=10, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

ax.set_xlabel('Longitude (WGS84)', fontsize=12)
ax.set_ylabel('Latitude (WGS84)', fontsize=12)
ax.set_title('Wigger Watershed: Candidate eDNA Sampling Sites\n' +
             'Branch-Aware Design with Directed River Topology', 
             fontsize=14, fontweight='bold')
ax.legend(loc='upper left', fontsize=9, framealpha=0.9)
ax.grid(True, alpha=0.3)

plt.tight_layout()
map_png_path = OUTPUT_DIR / "wigger_preflight_map.png"
plt.savefig(map_png_path, dpi=150, bbox_inches='tight')
print(f"✓ Created: {map_png_path}")
plt.close()

print("\n" + "=" * 80)
print("ALL ARTIFACTS GENERATED SUCCESSFULLY")
print("=" * 80)
