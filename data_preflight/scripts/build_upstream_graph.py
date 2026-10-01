#!/usr/bin/env python3

from collections import defaultdict, deque
from pathlib import Path

import geopandas as gpd
import pandas as pd


SHAPEFILE = Path(
    "data_preflight/raw/hydrorivers/HydroRIVERS_v10_eu.shp"
)

OUTPUT_DIR = Path("data_preflight/outputs")

SITE_A_ID = 20446064


def main():
    print("Loading HydroRIVERS...")

    rivers = gpd.read_file(SHAPEFILE)

    required = {
        "HYRIV_ID",
        "NEXT_DOWN",
        "LENGTH_KM",
        "UPLAND_SKM",
        "DIS_AV_CMS",
    }

    missing = required - set(rivers.columns)

    if missing:
        raise RuntimeError(
            f"Missing HydroRIVERS fields: {sorted(missing)}"
        )

    # Make sure IDs behave as integers.
    rivers["HYRIV_ID"] = rivers["HYRIV_ID"].astype(int)
    rivers["NEXT_DOWN"] = rivers["NEXT_DOWN"].fillna(0).astype(int)

    # ------------------------------------------------------
    # 1. Build reverse NEXT_DOWN mapping
    #
    # Normal HydroRIVERS:
    #
    # upstream reach ----NEXT_DOWN----> downstream reach
    #
    # We need:
    #
    # downstream reach -> [upstream reaches]
    # ------------------------------------------------------

    upstream_lookup = defaultdict(list)

    for row in rivers[["HYRIV_ID", "NEXT_DOWN"]].itertuples(
        index=False
    ):
        upstream_lookup[row.NEXT_DOWN].append(row.HYRIV_ID)

    # ------------------------------------------------------
    # 2. Traverse recursively upstream from Site A
    # ------------------------------------------------------

    visited = set()
    queue = deque([SITE_A_ID])

    edges = []

    while queue:
        current = queue.popleft()

        if current in visited:
            continue

        visited.add(current)

        predecessors = upstream_lookup.get(current, [])

        for upstream_id in predecessors:
            edges.append(
                {
                    "upstream": upstream_id,
                    "downstream": current,
                }
            )

            if upstream_id not in visited:
                queue.append(upstream_id)

    # Site A itself is included in visited.
    upstream_only = visited - {SITE_A_ID}

    # ------------------------------------------------------
    # 3. Extract actual geometries
    # ------------------------------------------------------

    graph_reaches = rivers[
        rivers["HYRIV_ID"].isin(visited)
    ].copy()

    # ------------------------------------------------------
    # 4. Find branch points
    # ------------------------------------------------------

    branch_rows = []

    for reach_id in visited:
        predecessors = [
            rid
            for rid in upstream_lookup.get(reach_id, [])
            if rid in visited
        ]

        if len(predecessors) >= 2:
            branch_rows.append(
                {
                    "HYRIV_ID": reach_id,
                    "upstream_count": len(predecessors),
                    "upstream_reaches": ",".join(
                        map(str, predecessors)
                    ),
                }
            )

    branches = pd.DataFrame(branch_rows)

    # ------------------------------------------------------
    # 5. Save graph edges
    # ------------------------------------------------------

    edge_df = pd.DataFrame(
        edges,
        columns=["upstream", "downstream"]
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    edge_df.to_csv(
        OUTPUT_DIR / "upstream_edges.csv",
        index=False,
    )

    # ------------------------------------------------------
    # 6. Save reaches
    # ------------------------------------------------------

    graph_reaches.to_file(
        OUTPUT_DIR / "upstream_reaches_real.geojson",
        driver="GeoJSON",
    )

    graph_reaches.drop(
        columns="geometry"
    ).to_csv(
        OUTPUT_DIR / "upstream_reaches_real.csv",
        index=False,
    )

    branches.to_csv(
        OUTPUT_DIR / "upstream_branch_points.csv",
        index=False,
    )

    # ------------------------------------------------------
    # 7. Summary
    # ------------------------------------------------------

    site_immediate_upstream = upstream_lookup.get(
        SITE_A_ID, []
    )

    total_length = graph_reaches["LENGTH_KM"].sum()

    print()
    print("========== UPSTREAM GRAPH ==========")
    print(f"Site A HYRIV_ID: {SITE_A_ID}")
    print(
        "Immediate upstream reaches:",
        site_immediate_upstream,
    )
    print(
        f"Upstream reaches excluding Site A: "
        f"{len(upstream_only)}"
    )
    print(
        f"Total reaches including Site A: "
        f"{len(visited)}"
    )
    print(
        f"Total represented length: "
        f"{total_length:.2f} km"
    )
    print(
        f"Branch points: "
        f"{len(branches)}"
    )

    print()

    if not branches.empty:
        print("========== BRANCH POINTS ==========")
        print(branches.to_string(index=False))

    print()
    print("Outputs:")
    print(
        OUTPUT_DIR / "upstream_reaches_real.geojson"
    )
    print(
        OUTPUT_DIR / "upstream_reaches_real.csv"
    )
    print(
        OUTPUT_DIR / "upstream_edges.csv"
    )
    print(
        OUTPUT_DIR / "upstream_branch_points.csv"
    )


if __name__ == "__main__":
    main()