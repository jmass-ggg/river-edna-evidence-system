# Wigger Site A / S1 network-match audit

Date: 2026-09-30. Scope: resolve only the historical S1 to HydroRIVERS network match. No historical-case validation was performed.

## SECTION 1 — Site A candidate reaches

Distances were recomputed in EPSG:2056 from historical S1 to raw HydroRIVERS LineStrings. Geometry is reported as WGS84 start → end; all five are LineStrings.

| HYRIV_ID | Distance m | NEXT_DOWN | LENGTH_KM | UPLAND_SKM | DIS_AV_CMS | Geometry | Reason plausible/not plausible |
|---:|---:|---:|---:|---:|---:|---|---|
| 20446064 | 64.813563 | 20445973 | 0.87 | 414.3 | 10.997 | (7.902083333, 47.310416667) → (7.893750000, 47.314583333), 3 vertices | **Plausible and selected:** nearest candidate, Wigger-scale basin/discharge, and direct tributary routing into the Aare-scale main stem. |
| 20445973 | 139.656320 | 20445851 | 0.56 | 10350.9 | 270.182 | (7.893750000, 47.314583333) → (7.897916667, 47.318750000), 2 vertices | Not plausible: downstream Aare main stem; receives 20446064. |
| 20446447 | 140.638499 | 20445973 | 3.81 | 9936.0 | 259.202 | (7.856250000, 47.297916667) → (7.893750000, 47.314583333), 5 vertices | Not plausible: upstream Aare main stem; joins 20445973 independently of the Wigger reach. |
| 20445974 | 454.260020 | 20445851 | 4.04 | 13.4 | 0.315 | (7.941666667, 47.314583333) → (7.897916667, 47.318750000), 6 vertices | Not plausible: small separate tributary and substantially farther away. |
| 20445851 | 561.279461 | 20445022 | 3.44 | 10369.2 | 270.400 | (7.897916667, 47.318750000) → (7.906250000, 47.347916667), 4 vertices | Not plausible: downstream Aare main stem and substantially farther away. |

## SECTION 2 — Exact snap

- Historical S1: 47.31400039098192, 7.895400745863826 (original LV03: 634537.17, 240447.56)
- Snapped S1: 47.31458336166783, 7.895400748900512
- Snap distance: 64.813562934 m in EPSG:2056
- Selected HYRIV_ID: 20446064
- Projected position: 0.8574012088 of the way along the stored upstream-to-downstream LineString

The historical observation was retained unchanged. The exact projected snap is `(2634536.793412143, 1240512.373616542)` in EPSG:2056. Its stored WGS84 round trip is within 1.2 mm of the projected raw reach.

## SECTION 3 — River identity validation

The selected reach is defensibly the Wigger at S1:

1. The Swiss federal swissTLM3D hydrography service identifies the watercourse at the historical S1 location and at the HydroRIVERS snap location as **Wigger**, watercourse number `CH0005070000`.
2. HydroRIVERS 20446064 has `UPLAND_SKM=414.3` and `DIS_AV_CMS=10.997`, consistent with a substantial Wigger tributary near its mouth. Its two immediate upstream reaches have combined branch structure representing the Wigger system.
3. `NEXT_DOWN=20445973`. That downstream reach has `UPLAND_SKM=10350.9` and `DIS_AV_CMS=270.182`, consistent with the much larger Aare. The raw geometry shares the exact junction coordinate `(7.89375, 47.314583333)`.
4. The competing Aare reaches are farther from S1 and have approximately 10,000 km² contributing area and 260–270 m³/s discharge, making them incompatible with a Wigger observation.

This conclusion uses river identity, scale, and routing together; it does not rely on nearest distance alone.

## SECTION 4 — Alternative candidates rejected

- **20445973:** Aare downstream of the Wigger junction. It receives 20446064 and is an order of magnitude larger in discharge and about 25 times larger in upstream area.
- **20446447:** Aare upstream of the junction. It flows independently into 20445973 and does not represent the Wigger branch.
- **20445974:** a small eastern tributary joining farther downstream; it is 454.26 m away and has only 13.4 km² upstream area.
- **20445851:** Aare farther downstream; it is 561.28 m away and has Aare-scale hydrology.

## SECTION 5 — Carraro vs HydroRIVERS comparison

The primary Carraro repository data were downloaded to temporary storage and inspected without adding them to this repository. `RUN_MODEL.m` explicitly assigns S1 to Carraro reach index 1. In `data_wigger.mat`, S1 is approximately **147.75 m** from the nearest modeled edge assigned to reach 1, even though the authors deliberately associate it with that reach.

Carraro’s river network was extracted from a 25 m terrain model and stores 8,988 network nodes and 166 aggregated reaches. HydroRIVERS is a generalized continental network derived from 15 arc-second HydroSHEDS data. They are separate networks and were not merged. The Carraro offset shows that its station-to-network representation is also an assignment rather than exact coordinate coincidence; the smaller 64.81 m HydroRIVERS offset is therefore technically plausible. The decisive independent check is the Swiss federal hydrography identification of the historical point as Wigger.

## SECTION 6 — Final network-match status

**MATCHED**  
**HYRIV_ID = 20446064**

The match satisfies spatial proximity, topology, river identity, alternative rejection, and resolution-explanation requirements. This is a network crosswalk, not a change to the historical observation coordinate.

## SECTION 7 — Distance corrections

Distances use HydroRIVERS `LENGTH_KM`: half of each B/C/D starting reach, full intermediate reaches, and 0.8574012088 of Site A reach 20446064 to the snapped position.

| Site | Old midpoint-proxy km | New snapped-Site-A km | Difference km |
|---|---:|---:|---:|
| B | 18.915000 | 19.225939 | +0.310939 |
| C | 23.625000 | 23.935939 | +0.310939 |
| D | 10.630000 | 10.940939 | +0.310939 |

B/C/D reach IDs, coordinates, zone memberships, and reachability signatures are unchanged.

## SECTION 8 — Files changed

- `data_preflight/scripts/generate_candidate_sites.py`
- `data_preflight/scripts/validate_sampling_design.py`
- `data_preflight/outputs/candidate_sampling_sites.csv`
- `data_preflight/outputs/candidate_sampling_sites.geojson`
- `data_preflight/outputs/sampling_design_validation.json`
- `data_preflight/outputs/zones_and_sampling_sites.geojson`
- `data_preflight/outputs/wigger_preflight_map.png`
- `data_preflight/outputs/site_a_snap_validation.json` (new)
- `data_preflight/outputs/site_a.json`
- `data_preflight/outputs/hydrorivers_site_match.json`
- `data_preflight/outputs/FINAL_REPORT.md`

All six raw HydroRIVERS components remain byte-for-byte identical to the separate local source copy. No production application files were changed.

## SECTION 9 — Final gate

**YES.** The Site A / S1 network-match blocker is resolved. The project may proceed to REAL CARRARO HISTORICAL-CASE VALIDATION as a separate next phase. That validation was not started here.
