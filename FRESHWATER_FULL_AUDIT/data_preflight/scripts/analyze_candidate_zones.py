from collections import defaultdict, deque
from pathlib import Path

import pandas as pd


OUTPUT_DIR = Path("data_preflight/outputs")

SITE_A = 20446064

edges = pd.read_csv(
    OUTPUT_DIR / "upstream_edges.csv"
)

reaches = pd.read_csv(
    OUTPUT_DIR / "upstream_reaches_real.csv"
)

branches = pd.read_csv(
    OUTPUT_DIR / "upstream_branch_points.csv"
)


# downstream -> upstream children
upstream_lookup = defaultdict(list)

for _, row in edges.iterrows():
    upstream_lookup[int(row["downstream"])].append(
        int(row["upstream"])
    )


def upstream_subtree(root):
    """Return root + every reach upstream of root."""

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


def distance_from_site(root):
    """Number of graph hops from Site A upstream."""

    queue = deque([(SITE_A, 0)])
    visited = set()

    while queue:
        current, depth = queue.popleft()

        if current == root:
            return depth

        if current in visited:
            continue

        visited.add(current)

        for child in upstream_lookup.get(current, []):
            queue.append((child, depth + 1))

    return None


candidate_roots = set()

# immediate Site A branches
candidate_roots.update(
    upstream_lookup.get(SITE_A, [])
)

# branches emerging from every confluence
for _, row in branches.iterrows():
    ids = str(row["upstream_reaches"]).split(",")

    for reach_id in ids:
        candidate_roots.add(int(reach_id))


results = []

for root in candidate_roots:

    subtree = upstream_subtree(root)

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

    results.append(
        {
            "branch_root": root,
            "distance_from_site_hops":
                distance_from_site(root),
            "reach_count": len(subtree),
            "total_length_km":
                round(total_length, 2),
            "root_upland_skm": upland,
        }
    )


result_df = pd.DataFrame(results)

result_df = result_df.sort_values(
    [
        "distance_from_site_hops",
        "total_length_km",
    ],
    ascending=[True, False],
)

out = OUTPUT_DIR / "candidate_zone_branches.csv"

result_df.to_csv(out, index=False)

print()
print("===== CANDIDATE BRANCHES =====")
print(result_df.to_string(index=False))

print()
print("Saved:", out)