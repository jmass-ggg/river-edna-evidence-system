#!/usr/bin/env python3
"""Wigger S1 → HydroRIVERS candidate reach preflight.

Research/preflight only. This script deliberately does NOT auto-select a
HYRIV_ID. It finds nearby candidate reaches and exports evidence for manual
spatial + topology verification.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import math
import sys

import geopandas as gpd
from shapely.geometry import Point

# Verified WGS84 position of Carraro Wigger sampling station S1.
S1_LON = 7.895400745863826
S1_LAT = 47.31400039098192

SCRIPT_DIR = Path(__file__).resolve().parent
PREFLIGHT_DIR = SCRIPT_DIR.parent
DEFAULT_SHP = PREFLIGHT_DIR / "raw" / "hydrorivers" / "HydroRIVERS_v10_eu.shp"
DEFAULT_CSV = PREFLIGHT_DIR / "outputs" / "reach_candidates_real.csv"
DEFAULT_GEOJSON = PREFLIGHT_DIR / "outputs" / "reach_candidates_real.geojson"

REQUIRED_FIELDS = {
    "HYRIV_ID",
    "NEXT_DOWN",
    "LENGTH_KM",
    "UPLAND_SKM",
    "DIS_AV_CMS",
    "HYBAS_L12",
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Find HydroRIVERS reaches near verified Wigger Site S1."
    )
    ap.add_argument(
        "shapefile",
        nargs="?",
        type=Path,
        default=DEFAULT_SHP,
        help=f"HydroRIVERS .shp path (default: {DEFAULT_SHP})",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_CSV,
        help=f"Candidate CSV output (default: {DEFAULT_CSV})",
    )
    ap.add_argument(
        "--geojson",
        type=Path,
        default=DEFAULT_GEOJSON,
        help=f"Candidate geometry output (default: {DEFAULT_GEOJSON})",
    )
    ap.add_argument(
        "--radius-m",
        type=float,
        default=3000.0,
        help="Search radius around S1 in metres (default: 3000)",
    )
    ap.add_argument(
        "--top",
        type=int,
        default=20,
        help="Maximum candidate reaches to export (default: 20)",
    )
    return ap.parse_args()


def validate_shapefile(shp: Path) -> None:
    if not shp.exists():
        raise FileNotFoundError(
            f"HydroRIVERS shapefile not found:\n  {shp}\n\n"
            "Put the complete shapefile set in:\n"
            f"  {DEFAULT_SHP.parent}\n"
            "Expected at least .shp, .dbf, .shx and .prj files."
        )

    required_sidecars = [
        shp.with_suffix(".dbf"),
        shp.with_suffix(".shx"),
        shp.with_suffix(".prj"),
    ]
    missing = [p.name for p in required_sidecars if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Shapefile companion files are missing: " + ", ".join(missing)
        )


def make_wgs84_bbox(radius_m: float) -> tuple[float, float, float, float]:
    """Return an approximate WGS84 bbox around S1 for fast source filtering."""
    lat_delta = radius_m / 111_320.0
    lon_delta = radius_m / (111_320.0 * math.cos(math.radians(S1_LAT)))
    return (
        S1_LON - lon_delta,
        S1_LAT - lat_delta,
        S1_LON + lon_delta,
        S1_LAT + lat_delta,
    )


def main() -> None:
    args = parse_args()
    shp = args.shapefile.resolve()
    validate_shapefile(shp)

    print(f"S1 WGS84: {S1_LAT:.9f}, {S1_LON:.9f}")
    print(f"HydroRIVERS: {shp}")
    print(f"Search radius: {args.radius_m:.0f} m")

    # HydroRIVERS v1.0 is distributed in WGS84. Read only a small geographic
    # window around S1 so we do not reproject the entire Europe dataset.
    bbox = make_wgs84_bbox(args.radius_m * 1.25)
    rivers = gpd.read_file(shp, bbox=bbox)

    if rivers.empty:
        raise RuntimeError(
            "No HydroRIVERS reaches were loaded near S1. "
            "Check the dataset/CRS and search radius."
        )

    if rivers.crs is None:
        raise RuntimeError("HydroRIVERS file has no CRS metadata (.prj problem).")

    missing_fields = REQUIRED_FIELDS - set(rivers.columns)
    if missing_fields:
        raise RuntimeError(
            f"Missing expected HydroRIVERS fields: {sorted(missing_fields)}\n"
            f"Available fields: {list(rivers.columns)}"
        )

    print(f"Source CRS: {rivers.crs}")
    print(f"Reaches loaded in local bbox: {len(rivers)}")

    # EPSG:2056 (Swiss LV95) is a metric projected CRS suitable for distances
    # in Switzerland. Never compute snapping distance in latitude/longitude.
    s1_metric = gpd.GeoDataFrame(
        {"station": ["S1"]},
        geometry=[Point(S1_LON, S1_LAT)],
        crs="EPSG:4326",
    ).to_crs("EPSG:2056")

    rivers_metric = rivers.to_crs("EPSG:2056")
    p = s1_metric.geometry.iloc[0]

    rivers_metric["snap_distance_m"] = rivers_metric.geometry.distance(p)
    local = rivers_metric[
        rivers_metric["snap_distance_m"] <= args.radius_m
    ].copy()
    local = local.sort_values("snap_distance_m").head(args.top)

    if local.empty:
        raise RuntimeError(
            f"No reaches found within {args.radius_m:.0f} m of S1. "
            "Do not force a match; inspect coverage or increase the radius."
        )

    cols = [
        "HYRIV_ID",
        "NEXT_DOWN",
        "LENGTH_KM",
        "UPLAND_SKM",
        "DIS_AV_CMS",
        "HYBAS_L12",
        "snap_distance_m",
    ]

    print("\nNearest HydroRIVERS candidates (NOT yet a final match):")
    print(local[cols].head(10).to_string(index=False))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    local[cols].to_csv(args.out, index=False)

    # Export the same candidates with real line geometry in WGS84 so they can
    # be inspected in QGIS/GeoJSON viewers before choosing a HYRIV_ID.
    args.geojson.parent.mkdir(parents=True, exist_ok=True)
    local_wgs84 = local.to_crs("EPSG:4326")
    local_wgs84[cols + ["geometry"]].to_file(args.geojson, driver="GeoJSON")

    print(f"\nSaved CSV:     {args.out.resolve()}")
    print(f"Saved GeoJSON: {args.geojson.resolve()}")
    print(
        "\nIMPORTANT: Do NOT pick the first HYRIV_ID automatically. "
        "Next verify candidate geometry plus NEXT_DOWN/upstream topology."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
