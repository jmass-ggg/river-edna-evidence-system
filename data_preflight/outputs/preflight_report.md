# Wigger eDNA Evidence Investigator — Data Preflight Report

**Run date:** 2026-09-30  
**Scope:** data preflight only; no application implementation.  
**Primary gate:** prove `S1 -> HydroRIVERS HYRIV_ID` without guessing.

## SECTION 1 — Sources inspected

### Carraro study / repository
- Carraro et al. (2018), *Estimating species distribution and abundance in river networks using environmental DNA*, PNAS, DOI: 10.1073/pnas.1813843115.
- Repository: https://github.com/lucarraro/edna-species-distribution
- Inspected repository code: `RUN_MODEL.m`, `ANALYSE_DATA.m`, repository README/listing.
- Repository lists `data_wigger.mat`, `eDNA_data.mat`, and `data_explanation.xlsx`; their binary contents were not retrievable in this runtime.
- Related Carraro Wigger field-method paper confirms a Wigger network extracted from a 25 m DTM using TauDEM and 15 eDNA sampling locations.
- Later `rivnet` documentation by the same research line constructs the Wigger network with `EPSG=21781`, providing strong CRS evidence.

### HydroRIVERS
- Product: HydroRIVERS v1.0.
- Regional tile required: `eu` = Europe and Middle East.
- Official download target: https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_eu_shp.zip
- Technical documentation: https://data.hydrosheds.org/file/technical-documentation/HydroRIVERS_TechDoc_v10.pdf
- HydroRIVERS v1.0 is derived from HydroSHEDS at 15 arc-second resolution and is distributed as WGS84 geographic vector data.
- Verified documented fields include `HYRIV_ID`, `NEXT_DOWN`, `MAIN_RIV`, `LENGTH_KM`, `DIST_DN_KM`, `DIST_UP_KM`, `CATCH_SKM`, `UPLAND_SKM`, `DIS_AV_CMS`, `ORD_STRA`, `ORD_CLAS`, `ORD_FLOW`, `HYBAS_L12`.
- `DIS_AV_CMS` is long-term average discharge, not sampling-day discharge.

## SECTION 2 — S1 verification

| Field | Result | Evidence | Status |
|---|---|---|---|
| Study station | S1 / first measuring site | `RUN_MODEL.m` first row of `station_coord`; `ANALYSE_DATA.m` indexes site data as `S1` ... `S15` | VERIFIED |
| Original coordinate | X=634537.17, Y=240447.56 | `RUN_MODEL.m` `station_coord` row 1 | VERIFIED |
| Carraro reach index | 1 | third value of first `station_coord` row | VERIFIED |
| CRS | CH1903/LV03, EPSG:21781 | Same-author Wigger `rivnet` construction uses `EPSG=21781`; swisstopo defines LV03/CH1903 as EPSG:21781 | SUPPORTED |
| Sampling date | 25 June 2014 | Present in project brief; exact date not recovered from accessible primary binary data | NOT VERIFIED |
| Species | *Fredericella sultana* (`Fs`) | `RUN_MODEL.m` selects `Fs` and states it is F. sultana | VERIFIED |
| WGS84 transformation | 47.31400039098192 N, 7.895400745863826 E | PyProj/PROJ EPSG:21781 -> EPSG:4326 | VERIFIED MATCH (conditional on supported CRS) |

## SECTION 3 — Coordinate transformation

- Original coordinate: `(634537.17, 240447.56)`
- Source CRS: `EPSG:21781` — CH1903/LV03
- Target CRS: `EPSG:4326` — WGS84
- Transformation: PROJ/PyProj `Transformer.from_crs(21781, 4326, always_xy=True)`
- Output latitude: `47.31400039098192`
- Output longitude: `7.895400745863826`
- Project-brief comparison coordinate: `47.314000, 7.895401`
- Geodesic difference: approximately `0.0475 m`
- Classification: **VERIFIED MATCH**

Both the original Swiss coordinate and transformed coordinate are preserved in `site_a.json`.

## SECTION 4 — HydroRIVERS candidate matches

| Rank | HYRIV_ID | NEXT_DOWN | Snap distance | Reach length | Upstream area | Reason plausible/not plausible |
|---|---:|---:|---:|---:|---:|---|
| — | — | — | — | — | — | **NOT EXTRACTED** — authoritative vector candidates could not be retrieved/query-executed in this runtime. No surrogate or guessed IDs are reported. |

The official schema and a query-capable HydroRIVERS v1.0 hosted layer were verified, but parameterized spatial queries and binary vector downloads were inaccessible from the runtime. Therefore a nearest-neighbour result cannot be reported honestly.

## SECTION 5 — Final Site A network match

**UNRESOLVED_NETWORK_MATCH**

`HYRIV_ID = NOT VERIFIED`

This status does **not** mean HydroRIVERS lacks the Wigger at S1. A `NETWORK_COVERAGE_LIMITATION` has not been demonstrated. It means the real local HydroRIVERS geometries/attributes were not available for the required candidate-distance and topology test. Forcing an ID here would violate the preflight rule.

## SECTION 6 — Topology validation

- Site A HydroRIVERS reach: **NOT VERIFIED**
- Immediate upstream HydroRIVERS reaches: **NOT VERIFIED**
- Downstream HydroRIVERS reach: **NOT VERIFIED**
- Upstream traversal count: **NOT VERIFIED**
- Major HydroRIVERS confluences: **NOT VERIFIED**
- Disconnected nearby reaches rejected: **NOT VERIFIED**

Carraro's model clearly contains its own river-network geometry/topology objects (`reach`, `reach_upstream`, `AD_pixel`, `outlet`, etc.), but these are Carraro reach indices/structures, not HydroRIVERS `HYRIV_ID`s.

## SECTION 7 — Potential future candidate zones

- Potential Z1 branch root: **NOT VERIFIED**
- Potential Z2 branch root: **NOT VERIFIED**
- Potential Z3 branch root: **NOT VERIFIED**

Current feasibility classification: **BLOCKED** for real HydroRIVERS-based Z1/Z2/Z3. Branches must not be invented before the S1 HydroRIVERS reach and its upstream graph are established.

## SECTION 8 — Carraro network vs HydroRIVERS

| Property | Carraro network | HydroRIVERS | Difference | Implication |
|---|---|---|---|---|
| Source | Wigger-specific network | Global HydroSHEDS-derived river network | Local vs global | Carraro was built specifically for this catchment |
| Underlying resolution | 25 m DTM reported in related Carraro Wigger methods | 15 arc-sec (~500 m at equator) | Carraro input is substantially finer | Small tributaries may be represented differently |
| Site mapping | S1 maps to Carraro reach index 1 | S1 `HYRIV_ID` not yet proven | Different identifier systems | Carraro reach `1` must never be treated as a HYRIV_ID |
| Topology | Explicit model network variables and upstream relationships | `HYRIV_ID` + `NEXT_DOWN` topology | Both can represent routing but at different resolution/model assumptions | Must compare spatially before choosing authority |
| Current verification at S1 | S1 coordinate/reach index verified in code | Match unresolved | HydroRIVERS local candidate extraction missing | Cannot yet make an evidence-based final network choice |

## SECTION 9 — Final network decision

**FURTHER VERIFICATION REQUIRED**

Carraro's network has a strong local-resolution advantage, while HydroRIVERS provides standardized IDs and `NEXT_DOWN` topology. However, no defensible choice should be made until the actual HydroRIVERS reaches around S1 are loaded, the nearest several candidates are compared in a metric CRS, and the candidate's upstream/downstream topology is checked against the Wigger geometry. If HydroRIVERS proves too coarse or places S1 ambiguously near the Wigger-Aare confluence, the Carraro network should then be evaluated as the authoritative demonstration graph.

## SECTION 10 — Preflight artifacts

- `outputs/site_a.json`
- `outputs/hydrorivers_site_match.json`
- `outputs/upstream_reaches.geojson`
- `outputs/reach_candidates.csv`
- `outputs/preflight_report.md`

## SECTION 11 — BLOCKER STATUS

- S1 identity: **READY**
- S1 CRS: **READY** (evidence classification: SUPPORTED)
- S1 WGS84 coordinate: **READY**
- S1 HYRIV_ID: **BLOCKED**
- Upstream graph: **BLOCKED**
- Real branching suitable for Z1/Z2/Z3: **BLOCKED**

## SECTION 12 — IMPLEMENTATION GATE

**Can we now generate the real Z1/Z2/Z3 and B/C/D? — NO.**

What remains unresolved:
1. Retrieve the real HydroRIVERS v1.0 Europe/Middle East vector data.
2. Extract the local S1/Wigger subset.
3. Reproject to a metric Swiss CRS for distance calculations.
4. Compare at least the nearest several reaches to S1 and record actual metric snap distances.
5. Validate the selected reach using `NEXT_DOWN`, reverse upstream predecessors, downstream path, Wigger geometry, and nearby confluence context.
6. Only then record the actual `HYRIV_ID`, build the upstream graph, and derive real Z1/Z2/Z3 roots.

### Provenance / data-quality notes
- No `HYRIV_ID` was invented.
- No tributary/reach IDs were invented.
- `DIS_AV_CMS` is not used as sampling-day discharge.
- The exact demo date 25 June 2014 remains **NOT VERIFIED** from the accessible source material.
- The official HydroRIVERS ZIP was identified but not successfully downloaded by this runtime, so no official ZIP/file hash is claimed.
