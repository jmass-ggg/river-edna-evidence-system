#!/usr/bin/env python3

from collections import defaultdict, deque
from pathlib import Path

import geopandas as gpd
import pandas as pd


OUTPUT_DIR = Path("data_preflight/outputs")

SITE_A = 20446064

ZONE_ROOTS = {
    "Z1": 20447392,
    "Z2": 20450127,
    "Z3": 20451169,
}


edges = pd.read_csv(
    OUTPUT_DIR / "upstream_edges.csv"
)

reaches = gpd.read_file(
    OUTPUT_DIR / "upstream_reaches_real.geojson"
)

reaches["HYRIV_ID"] = reaches["HYRIV_ID"].astype(int)

upstream_lookup = defaultdict(list)
downstream_lookup = {}

for _, row in edges.iterrows():

    upstream = int(row["upstream"])
    downstream = int(row["downstream"])

    upstream_lookup[downstream].append(upstream)
    downstream_lookup[upstream] = downstream


def get_subtree(root):
    """Root + every reach upstream of root."""

    visited = set()
    queue = deque([root])

    while queue:

        current = queue.popleft()

        if current in visited:
            continue

        visited.add(current)

        for child in upstream_lookup.get(current, []):
            queue.append(child)

    return visited


def path_to_site(root):
    """Follow NEXT_DOWN from root toward Site A."""

    path = [root]

    current = root

    while current != SITE_A:

        if current not in downstream_lookup:
            return None

        current = downstream_lookup[current]
        path.append(current)

        if len(path) > 1000:
            raise RuntimeError("Unexpected topology loop")

    return path


zone_sets = {}

print()
print("========== ZONE VALIDATION ==========")

for zone, root in ZONE_ROOTS.items():

    subtree = get_subtree(root)

    zone_sets[zone] = subtree

    subset = reaches[
        reaches["HYRIV_ID"].isin(subtree)
    ]

    total_length = subset["LENGTH_KM"].sum()

    root_row = reaches[
        reaches["HYRIV_ID"] == root
    ]

    upland = None

    if not root_row.empty:
        upland = root_row.iloc[0]["UPLAND_SKM"]

    route = path_to_site(root)

    print()
    print(zone)
    print("Root:", root)
    print("Reach count:", len(subtree))
    print(
        "Total length:",
        round(total_length, 2),
        "km"
    )
    print(
        "Root UPLAND_SKM:",
        upland
    )
    print(
        "Path to Site A:",
        route
    )


print()
print("========== OVERLAP TEST ==========")

zones = list(ZONE_ROOTS.keys())

has_overlap = False

for i in range(len(zones)):

    for j in range(i + 1, len(zones)):

        a = zones[i]
        b = zones[j]

        overlap = (
            zone_sets[a]
            & zone_sets[b]
        )

        print(
            f"{a} vs {b}: "
            f"{len(overlap)} overlapping reaches"
        )

        if overlap:

            has_overlap = True

            print(
                "Overlap IDs:",
                sorted(overlap)
            )


# ---------------------------------------------------
# Assign zones to actual geometry
# ---------------------------------------------------

zone_rows = []

for zone, subtree in zone_sets.items():

    subset = reaches[
        reaches["HYRIV_ID"].isin(subtree)
    ].copy()

    subset["zone"] = zone

    zone_rows.append(subset)


zones_gdf = gpd.GeoDataFrame(
    pd.concat(
        zone_rows,
        ignore_index=True
    ),
    crs=reaches.crs,
)

zones_gdf.to_file(
    OUTPUT_DIR / "candidate_zones_real.geojson",
    driver="GeoJSON",
)


# ---------------------------------------------------
# Reaches not belonging to a candidate zone
# ---------------------------------------------------

assigned = set().union(
    *zone_sets.values()
)

unassigned = reaches[
    ~reaches["HYRIV_ID"].isin(assigned)
].copy()

unassigned.to_file(
    OUTPUT_DIR / "shared_trunk_reaches.geojson",
    driver="GeoJSON",
)


print()
print("========== RESULT ==========")

if has_overlap:

    print(
        "❌ Candidate zones overlap."
    )

else:

    print(
        "✅ Candidate zones are mutually non-overlapping."
    )

print()
print(
    "candidate_zones_real.geojson created"
)

print(
    "shared_trunk_reaches.geojson created"
)