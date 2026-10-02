# eDNA Evidence Investigator: Scientific Resource and Data Provenance Audit

**Audit date:** 2026-10-01  
**Evidence basis:** repository files, source data, generated artifacts, backend code, tests, and freeze records. No external facts were added during this audit.

## Status key

- 🟢 **REAL / USED**: real source data or a method connected to runtime behavior.
- 🟡 **PARTIAL**: implemented or scientifically supported only within an explicit boundary.
- ⚪ **AVAILABLE BUT UNUSED**: present locally but not used by the runtime scientific pipeline.
- 🔴 **MISSING**: no operational source or modeled variable.
- ❓ **UNVERIFIED**: present as a claim or proposed mapping without enough evidence for acceptance.

“Used” means the application or its verified preflight pipeline reads the resource. A source file that exists locally but is not read by the runtime is listed separately.

---

# 1. Complete data inventory

| Dataset or resource | Provider | Coverage | Data type | Purpose | Used by | Status |
| --- | --- | --- | --- | --- | --- | --- |
| HydroRIVERS v1.0 Europe | HydroSHEDS / WWF, as identified by the supplied technical documentation and artifacts | Europe; runtime uses a 49-reach Wigger subset | Directed river network | Reach identity, geometry, downstream linkage, reach length, topology, candidate generation | Preflight scripts, `WiggerPreflightLoader`, `HydrologyEngineImpl`, candidate and decision engines | 🟢 REAL / USED |
| Carraro/Wigger research package | Carraro et al. research repository | Wigger catchment, Switzerland | Catchment morphology, river network, station coordinates, eDNA concentrations, dates | Historical case H001, station inventory, topology comparison, historical overlap review | `CarraroHistoricalLoader`, `CarraroV4Extractor`, demo route, validation tests | 🟢 REAL / USED |
| Carraro eDNA observations | Carraro et al. | Stations S1–S15, 2014-05-28 to 2015-05-15 | Fs and Tb concentration time series | Historical observations and validation | H001 loader, V4 extraction and historical validation | 🟢 REAL / USED |
| Carraro catchment morphology | Carraro et al. | Wigger catchment | MATLAB structures: reach network, DTM, discharge series, geometry and covariates | Station coordinates and cross-network topology review; source research context | `RUN_MODEL.m`, V4 extractor and validation | 🟡 PARTIAL |
| Carraro preflight outputs | Project generated | Wigger upstream network and case | CSV, GeoJSON, JSON | Runtime-ready graph, zones, sites, snap metadata and validation | Backend loaders and APIs | 🟢 REAL / USED |
| Carraro multi-station crosswalk | Project generated from Carraro and HydroRIVERS | S1–S15 | Coordinate transform, candidate reaches, distances and review status | Historical network mapping review | Historical validation module/tests | 🟡 PARTIAL |
| GBIF occurrence search | Global Biodiversity Information Facility | Live query around requested coordinates | Species occurrence records | Optional species-occurrence context | `GbifOccurrenceProvider`, context API | 🟡 PARTIAL |
| GHSL-derived urbanization | Provider named in adapter; no operational dataset client configured | Intended case vicinity | Built-up context | Intended urban context | Interface and provider only | 🔴 MISSING at runtime |
| Historical weather | No concrete provider/model configured | Intended case coordinates and date window | Temperature and precipitation | Intended environmental context | Interface and provider only | 🔴 MISSING at runtime |
| Follow-up eDNA samples | User or field collector supplied | Case-specific | Replicates, positives, concentration, assay, controls and provenance | Store new evidence and trigger reinvestigation | Follow-up sample service and investigation pipeline | 🟡 IMPLEMENTED INPUT; no records bundled |
| Citizen-science observations | None found | None | Intended/possible occurrence context | No implemented use | No provider found | 🔴 MISSING |

## 1.1 HydroRIVERS source fields

The canonical local source is [`data_preflight/raw/hydrorivers/HydroRIVERS_v10_eu.shp`](data_preflight/raw/hydrorivers/HydroRIVERS_v10_eu.shp), with its `.dbf`, `.prj`, `.shx`, `.sbn`, and `.sbx` companions. It contains **938,544** European reaches in EPSG:4326.

Actual fields:

```text
HYRIV_ID, NEXT_DOWN, MAIN_RIV, LENGTH_KM, DIST_DN_KM, DIST_UP_KM,
CATCH_SKM, UPLAND_SKM, ENDORHEIC, DIS_AV_CMS, ORD_STRA, ORD_CLAS,
ORD_FLOW, HYBAS_L12, geometry
```

Runtime uses the 49-row Wigger subset in:

- `data_preflight/outputs/upstream_reaches_real.csv`
- `data_preflight/outputs/upstream_reaches_real.geojson`
- `data_preflight/outputs/upstream_edges.csv`

`DIS_AV_CMS` is a HydroRIVERS attribute. The system does **not** treat it as discharge on a sampling date.

## 1.2 Carraro/Wigger source fields

Original local files:

- `data_preflight/raw/carraro/data_wigger.mat`
- `data_preflight/raw/carraro/eDNA_data.mat`
- `data_preflight/raw/carraro/data_explanation.xlsx`
- `data_preflight/raw/carraro/RUN_MODEL.m`
- `data_preflight/raw/carraro/ANALYSE_DATA.m`
- `data_preflight/raw/carraro/README.md`

Verified `data_wigger.mat` variables:

```text
AD_pixel, DTM, Drainage_area, N_reach, Q_ZOF, X, XX, Xb, Xc,
Y, YY, Yb, Yc, area_local, area_upstream, celerity,
length_downstream, length_reach, mean_subcatchment_altitude,
nnodes, outlet, reach, reach_geology_class, reach_upstream,
reach_width, subcatch
```

Verified `eDNA_data.mat` variables:

```text
Date, Fs, Tb
```

The supplied workbook defines `Date.SNUM` as MATLAB dates and `Fs.SNUM` / `Tb.SNUM` as concentration time series in mol/L. It also documents the Wigger morphology variables, including mean daily `Q_ZOF` discharge measured at Zofingen for 2014–2016. That discharge series exists in the source package but is not consumed by the current backend analysis.

## 1.3 Project-derived artifact inventory

| Artifact group | Main paths | Contents | Runtime role |
| --- | --- | --- | --- |
| Detection site | `site_a.json`, `site_a_snap_validation.json`, `hydrorivers_site_match.json` | Historical coordinate, CRS transform, HYRIV_ID 20446064, snapped position and distance | Creates Site A and anchors graph analysis |
| Wigger network | `upstream_reaches_real.csv/.geojson`, `upstream_edges.csv`, `upstream_branch_points.csv` | 49 reaches and 48 directed edges | Builds hydrology graph |
| Source zones | `candidate_zones_real.geojson`, `candidate_zone_branches.csv` | Z1–Z3 reach membership and branch summaries | Creates source hypotheses |
| Candidate sites | `candidate_sampling_sites.csv/.geojson`, `sampling_design_validation.json` | A/B/C/D reference design, positions, distances, signatures | Demo seed and regression reference |
| Automatic candidates | Runtime `GeneratedCandidateSite` and persisted snapshots | Equivalence class, representative, signature and score | Reinvestigation output |
| Historical inventory | `carraro_station_inventory.csv`, `carraro_observations_v4.csv` | 15 stations and 602 observations | Historical reconstruction and review |
| Crosswalk review | `carraro_station_hydrorivers_crosswalk_v4.csv`, `carraro_station_hydrorivers_review_v4.csv` | Candidate reaches, snap distances, alternatives, topology and status | Partial network validation |

---

# 2. Hydrological data and flow

```text
Historical S1 coordinate (Carraro, EPSG:21781)
                 │ coordinate transform and geometric snap
                 ▼
      Site A = HYRIV_ID 20446064
                 │
                 ▼
 HydroRIVERS HYRIV_ID + NEXT_DOWN + LENGTH_KM
                 │
       build downstream and reverse graphs
                 ▼
      traverse 48 upstream reaches
                 │
        ┌────────┴─────────┐
        ▼                  ▼
 candidate zones      network paths/distances
        │                  │
        └────────┬─────────┘
                 ▼
       reachability signatures
                 ▼
 equivalence classes and candidate representatives
                 ▼
 topology pair-separation decision and trace
```

## Real source values

- Reach identity: `HYRIV_ID`.
- Downstream pointer: `NEXT_DOWN`.
- Reach length: `LENGTH_KM`.
- Geometry: HydroRIVERS line geometry.
- Other retained attributes: `MAIN_RIV`, distance fields, catchment/upstream area, average discharge, stream orders and HydroBASINS level-12 ID.
- Historical station geometry: Carraro `station_coord` in `RUN_MODEL.m`.

## Calculated values

- Site A snap and reach fraction.
- Upstream reach set and edge list.
- Downstream paths and first common downstream reach.
- Network distance using partial start/end reaches and full intermediate reaches.
- Zone membership and zone-to-site reachability.
- Candidate signatures, equivalence classes, representatives and pair-separation scores.

The graph calculation proves mapped hydrological connectivity at HydroRIVERS resolution. It does not establish eDNA transport amount, travel time, survival, or biological occupancy.

---

# 3. Wigger case study

## Original scientific source

The repository identifies:

**Carraro, L. et al. (2018). “Estimating species distribution and abundance in river networks using environmental DNA.” Proceedings of the National Academy of Sciences. DOI: [10.1073/pnas.1813843115](https://doi.org/10.1073/pnas.1813843115).**

The local README describes the files as code and data supporting that publication. The repository URL recorded in `site_a.json` is [lucarraro/edna-species-distribution](https://github.com/lucarraro/edna-species-distribution).

The current application uses the paper’s supplied observations and catchment files. It does **not** implement the paper’s Metropolis-within-Gibbs species distribution and abundance model, posterior evaluation, or concentration transport equation. Those remain in the supplied MATLAB research package.

## Source-to-project transformation

```text
Carraro data_wigger.mat + RUN_MODEL.m
        │ station coordinates, Carraro topology, catchment data
        ├──────────────────────────────────────────┐
Carraro eDNA_data.mat                              │
        │ dates and Fs/Tb concentrations           │
        ▼                                          ▼
 Carraro inventory/observation extraction    HydroRIVERS matching
        │                                          │
        └──────────────────┬───────────────────────┘
                           ▼
             reviewed station crosswalk
                           │
                           ▼
   Wigger runtime graph, Site A, zones and candidates
```

## Historical case H001

- Station: S1.
- Carraro coordinate: 634537.17, 240447.56, EPSG:21781.
- Carraro reach index: 1.
- HydroRIVERS representation: 20446064.
- Taxon: *Fredericella sultana* (Fs).
- Observation index: 4.
- Date: 2014-06-25.
- Concentration: 1.29832198e-17 mol/L.
- Recorded state: DETECTED because concentration is greater than zero.

B/C/D and automatically generated candidates are proposed follow-up locations. They are not historical H001 measurements.

---

# 4. eDNA data

The extracted historical table has **602 non-missing observations**: 301 Fs and 301 Tb across 15 stations and 21 dates. There are 132 positive Fs concentrations and 70 positive Tb concentrations. Missing values are omitted rather than converted into nondetections.

| Field | What it records | Source | Backend use | Scientific interpretation |
| --- | --- | --- | --- | --- |
| `station` | S1–S15 identifier | MATLAB structure field and `RUN_MODEL.m` station order | Historical inventory and overlap matching | Observation location label only |
| `taxon_code` | Fs or Tb | `eDNA_data.mat` structure name | Separates target measurements | Taxon identity from source |
| `observation_index` | One-based position in station series | Extractor | Reproducibility | No ecological meaning assigned |
| `date` | Sampling date | `Date.S#` | Case metadata and temporal summaries | Observation time only |
| `concentration_mol_l` | Measured eDNA concentration | `Fs.S#` or `Tb.S#` | Historical evidence record | Positive is recorded as detection; magnitude is not modeled further |
| `detected` | `concentration > 0` encoding | Project-derived | Descriptive historical state | Does not prove local residence or source location |
| source variables/files | Exact input provenance | Extractor | Audit trail | No inference |

Historical records do not include project-level replicate IDs, assay name, controls status, laboratory identity, confidence score, or analytical error fields. The follow-up sample API can collect replicate count, positive replicates, concentration/unit, assay, controls, collector source and provenance, but the repository contains no real follow-up sample dataset.

The evidence engine currently assigns historical and follow-up eDNA evidence `UNKNOWN` compatibility and `UNASSESSED` strength because no validated biological interpretation rule exists.

---

# 5. Scientific resources

| Resource | Type | Author/provider | Application use | Implemented? |
| --- | --- | --- | --- | --- |
| Carraro et al. Wigger package | Paper, dataset and MATLAB code | Carraro et al. | Historical observations, station coordinates, catchment topology comparison | 🟢 Data used; original model not implemented |
| HydroRIVERS v1.0 Europe | Hydrological database | HydroSHEDS / WWF | Directed reach graph, distance, zones and candidate discrimination | 🟢 Yes |
| HydroRIVERS Technical Documentation v1.0 | Technical documentation | HydroSHEDS / WWF | Documents supplied dataset | 🟡 Present; backend logic relies on fields, not parsed PDF |
| Swiss CH1903/LV03 and LV95 transformations | Coordinate reference systems | CRS definitions through PROJ/PyProj | Carraro coordinate conversion and metric snap distance | 🟢 Yes |
| GBIF occurrence API | Biodiversity database/API | GBIF | Optional occurrence context near a case | 🟡 Live adapter exists; no bundled response |
| GHSL-derived urbanization concept | Environmental data architecture | Provider not operationally connected | Intended built-up metric | 🔴 No runtime data |
| Historical weather concept | Environmental data architecture | No source/model configured | Intended temperature and precipitation | 🔴 No runtime data |
| Morris & Adams (2007) | Peer-reviewed paper | D. J. Morris, A. Adams | General Fs–Tb host relationship | 🟢 Used in One Health narrative |
| Sudhagar et al. (2020) | Peer-reviewed review | A. Sudhagar, G. Kumar, M. El-Matbouli | General Tb–PKD/salmonid relationship | 🟢 Used in One Health narrative |
| Conservative claim-status framework | Project method | Project implementation | Separates observed, supported relationship, possible relevance and unknown | 🟢 Yes |

---

# 6. Scientific papers

## Carraro et al. (2018)

**Citation recorded by the project:** Carraro, L. et al. (2018). “Estimating species distribution and abundance in river networks using environmental DNA.” *Proceedings of the National Academy of Sciences*. DOI: [10.1073/pnas.1813843115](https://doi.org/10.1073/pnas.1813843115).

**Contribution:** Wigger catchment data, station/date/concentration measurements, morphology, and original MATLAB inference model.

**System use:** The project uses the supplied data and station/network information. Its current topology-only backend is not an implementation of the publication’s Bayesian model, Metropolis-within-Gibbs sampler, posterior calculation, abundance inference, or Eq. (1) concentration model.

## Morris and Adams (2007)

**Citation:** D. J. Morris and A. Adams (2007). “Sacculogenesis and sporogony of *Tetracapsuloides bryosalmonae* within the bryozoan host *Fredericella sultana*.” *Parasitology Research*. DOI: [10.1007/s00436-006-0371-0](https://doi.org/10.1007/s00436-006-0371-0). PMID: 17205353.

**Contribution:** Supports the general host relationship between Fs and Tb.

**System use:** Citation-backed narrative logic in `OneHealthService`. It does not create a local parasite inference, disease probability, or computational ecological model.

## Sudhagar, Kumar, and El-Matbouli (2020)

**Citation:** A. Sudhagar, G. Kumar, and M. El-Matbouli (2020). “The Malacosporean Myxozoan Parasite *Tetracapsuloides bryosalmonae*: A Threat to Wild Salmonids.” *Pathogens*. DOI: [10.3390/pathogens9010016](https://doi.org/10.3390/pathogens9010016). PMID: 31877926.

**Contribution:** Supports the general relationship between Tb, proliferative kidney disease, salmonids, and temperature-sensitive biology.

**System use:** Citation-backed animal-health relevance. The application does not infer local infection, PKD, temperature-driven risk, or human-health impact.

No other paper is directly cited in executable scientific logic.

---

# 7. Scientifically meaningful methods

| Method | Input | Processing | Output | Scientific basis | Status |
| --- | --- | --- | --- | --- | --- |
| Coordinate transform and snap | Carraro coordinates, source CRS, HydroRIVERS geometry | PyProj transform; projected metric distance; line projection | Matched reach, snapped coordinate, distance and fraction | Standard GIS geometry/CRS operations | 🟢 Implemented |
| Directed graph construction | `HYRIV_ID`, `NEXT_DOWN`, edge table | Downstream map plus reverse upstream adjacency | Queryable river graph | HydroRIVERS topology | 🟢 Implemented |
| Upstream traversal | Detection reach and reverse graph | Breadth-first traversal | Upstream reach IDs | Directed network reachability | 🟢 Implemented |
| Downstream path / confluence | Source reach(s), `NEXT_DOWN` | Follow downstream pointers with cycle checks | Path or first common downstream reach | Directed network topology | 🟢 Implemented |
| Network distance | Path, `LENGTH_KM`, reach fractions | Remaining source length + intermediate lengths + destination fraction | Kilometres along mapped network | Network path length | 🟢 Implemented |
| Source-zone connectivity | Zone roots/reaches and site reach | Test same reach or upstream relation | Can/cannot hydrologically contribute | Mapped directional plausibility | 🟢 Implemented |
| Evidence compatibility | Typed evidence and rule catalog | Apply required fields and directional rule | SUPPORTS, CONTRADICTS, NEUTRAL or UNKNOWN | Explicit rule `hydrorivers.directed_contribution.v1` | 🟢 Implemented |
| Connectivity evidence strength | Validation metadata | Evaluate network mapping, root, topology and graph coverage | HIGH, MEDIUM, LOW or UNASSESSED | Claim-specific project rule | 🟢 Implemented, topology only |
| Conservative hypothesis resolution | Validated directional assessments | Support/contradiction state machine | SUPPORTED, CONFLICTING, WEAKENED or UNKNOWN | Explicit auditable semantics | 🟢 Implemented |
| Candidate equivalence classes | Upstream reaches and zone roots | Binary zone-root reachability vector | Signature classes | Topology-based experimental discrimination | 🟢 Implemented |
| Representative selection | Members of one signature class | Minimum network distance to A, then HYRIV_ID tie-break | One representative per useful class | Deterministic engineering criterion | 🟢 Implemented |
| Pair-separation score | Signature with `r` reachable hypotheses among `n` | `r × (n-r)` | Number of hypothesis pairs separated by binary topology outcome | Defined topology objective | 🟢 Implemented |
| Decision rule | Candidate validity and scores | Strict winner, tie, abstain or insufficient-data logic | Sampling status and site IDs | Transparent deterministic rule | 🟢 Implemented |
| Reinvestigation | Current evidence, zones and graph | Reassess → resolve → regenerate → decide → snapshot | Versioned run and trace | Project orchestration | 🟢 Implemented |
| Historical overlap classification | Generated HYRIV_ID and accepted crosswalk | Exact ID match only for VERIFIED/SUPPORTED stations | Overlap or counterfactual label | Conservative retrospective comparison | 🟢 Implemented |

The pair-separation criterion is optimized only for its stated binary topology objective. It is not an optimization of detection probability, ecological value, cost, access, or restoration benefit.

---

# 8. Source data versus derived data

## Source data

- HydroRIVERS reach IDs, downstream pointers, lengths, attributes and geometries.
- Carraro station coordinates and Carraro reach indices.
- Carraro river morphology and `reach_upstream` matrix.
- Carraro dates and Fs/Tb concentrations.
- User-submitted follow-up sample fields, if supplied.
- GBIF occurrence records, only when the live context endpoint succeeds.

## Derived data and provenance formulas

```text
Carraro coordinate + CRS
  → transform and line projection
  → WGS84 coordinate, HYRIV_ID, snap distance, reach fraction

HYRIV_ID + NEXT_DOWN
  → directed graph traversal
  → upstream set, downstream path, first common downstream

Directed path + LENGTH_KM + endpoint fractions
  → network-distance calculation
  → network_distance_km

Zone roots + candidate reach + directed graph
  → can_contribute for each zone
  → binary reachability signature

Signature with r reachable of n hypotheses
  → r × (n-r)
  → separated_hypothesis_pairs

Candidate scores + validation state
  → SamplingDecisionEngine
  → RECOMMEND / TIE / ABSTAIN / INSUFFICIENT_DATA

Evidence assessments from validated rule IDs
  → ConservativeHypothesisStateResolver
  → hypothesis status and reason
```

---

# 9. Result provenance map

## Key implementation files

- Data loaders: `backend/app/scientific/data_loader.py`
- Carraro V4 extraction: `backend/app/preflight/carraro_v4.py`
- Historical mapping review: `backend/app/scientific/historical_validation.py`
- Hydrology graph and distance: `backend/app/scientific/hydrology/engine.py`
- Evidence interpretation: `backend/app/scientific/evidence/engine.py`
- Scientific rules: `backend/app/scientific/rules/catalog.py`
- Hypothesis resolver: `backend/app/scientific/hypothesis.py`
- Candidate generation: `backend/app/scientific/sampling/candidate_generator.py`
- Sampling decisions and traces: `backend/app/scientific/sampling/engine.py`
- Reinvestigation orchestration: `backend/app/services/investigation_service.py`
- One Health pathway: `backend/app/services/one_health_service.py`
- GBIF adapter: `backend/app/context/providers/gbif.py`
- Urbanization adapter: `backend/app/context/providers/urbanization.py`
- Weather adapter: `backend/app/context/providers/weather.py`
- Runtime context wiring: `backend/app/api/routes/context.py`

| Application result | Immediate source | Method | Root source |
| --- | --- | --- | --- |
| Site A identity | `site_a.json` plus H001 loader | Source validation and HydroRIVERS snap | `RUN_MODEL.m`, `eDNA_data.mat`, HydroRIVERS |
| Observation date/concentration/state | Case historical metadata | Direct MATLAB extraction; positive-value encoding | `Date.S1[4]`, `Fs.S1[4]` |
| River reach details | `RiverReach` | Lookup by HYRIV_ID | Wigger HydroRIVERS subset |
| Upstream reaches | Hydrology API/engine | Reverse-graph BFS | `upstream_edges.csv`, HydroRIVERS `NEXT_DOWN` |
| Downstream path | Hydrology engine | Follow `NEXT_DOWN` | HydroRIVERS subset |
| Network distance | Hydrology engine | Sum `LENGTH_KM` with fractions | HydroRIVERS lengths and snap fraction |
| Candidate zone | Database/demo seed | Load validated GeoJSON membership | `candidate_zones_real.geojson` |
| Compatibility claim | Evidence engine | `hydrorivers.directed_contribution.v1` | Directed hydrological evidence and graph validation |
| Evidence strength | Evidence engine | `hydrorivers.directed_connectivity_strength.v1` | Mapping/topology validation metadata |
| Hypothesis state | Resolver | Validated support/contradiction semantics | Rule-tagged evidence assessments |
| Candidate representative | Candidate generator | Signature class then nearest network distance | Zones plus HydroRIVERS graph |
| Candidate score | Sampling engine | `r × (n-r)` | Reachability signature |
| Sampling decision | Sampling engine | Winner/tie/abstention rules | Candidate scores and completeness |
| Decision explanation | Decision trace | Collect evidence IDs, rules, checks, assumptions and limits | Same run inputs and engine outputs |
| One Health pathway | `OneHealthService` | Fixed claim-status framework | H001 plus two cited papers |
| GBIF context | Context service | Live API query and compact mapping | GBIF occurrence API response |
| Historical candidate comparison | Historical validation | Accepted crosswalk exact HYRIV_ID match | Carraro observations plus reviewed mapping |

### Example: recommended or tied site

```text
Sampling decision
  ← strict maximum or tied pair-separation scores
  ← binary reachability signatures
  ← zone-root → candidate reach connectivity
  ← HydrologyEngine
  ← HydroRIVERS NEXT_DOWN graph
```

### Example: reach 20450127

```text
HYRIV_ID 20450127
  ← candidate representative in signature class [0,1,0]
  ← nearest network distance within that class
  ← upstream reach set and zone roots
  ← HydroRIVERS geometry, NEXT_DOWN and LENGTH_KM
```

---

# 10. Currently used external resources

## HydroRIVERS

```text
HydroRIVERS v1.0 Europe
  → reach IDs, geometry, NEXT_DOWN, LENGTH_KM and attributes
  → Wigger preflight subset
  → HydrologyEngine
  → connectivity, paths, distances, candidates and decisions
  → API/UI-ready structured results and DecisionTrace
```

## Carraro/Wigger research data

```text
Carraro MATLAB files and scripts
  → station coordinates, dates, Fs/Tb concentrations, Carraro topology
  → loaders and preflight validation
  → historical case, station inventory and crosswalk review
  → case evidence and historical-validation report
```

## GBIF

```text
Case taxon + coordinate + radius
  → live GBIF occurrence search adapter
  → compact occurrence context with provenance and limitations
  → stored context evidence
  → UNKNOWN compatibility / UNASSESSED strength
```

GBIF is operational code connected to the context endpoint. The repository does not bundle a verified production response, so it is not part of the frozen Wigger decision result.

---

# 11. Available, planned, and disconnected data

| Resource | Repository state | Classification |
| --- | --- | --- |
| Carraro `Q_ZOF` mean daily discharge | Present in `data_wigger.mat` and documented | ⚪ AVAILABLE BUT UNUSED |
| Carraro DTM/elevation | Present in `data_wigger.mat` | ⚪ AVAILABLE BUT UNUSED |
| Carraro geology classes | Present in `data_wigger.mat` | ⚪ AVAILABLE BUT UNUSED |
| Carraro reach width, celerity, drainage/subcatchment area | Present in `data_wigger.mat` | ⚪ AVAILABLE BUT UNUSED by current topology decision |
| Carraro MATLAB Bayesian model and posterior analysis | Source scripts present, auxiliary functions/results absent from listed local package | ⚪ AVAILABLE IN PART, NOT IMPLEMENTED |
| GHSL-derived built-up metrics | Provider interface exists; API injects `UnavailableSpatialClient` | 🟡 PLANNED / NOT CONNECTED |
| Historical temperature and precipitation | Provider interface exists; API injects `UnavailableSpatialClient` | 🟡 PLANNED / NOT CONNECTED |
| Citizen science | No provider or data source found | 🔴 MISSING |
| Follow-up sampling | Schema, persistence and API exist; no bundled real observations | 🟡 READY FOR FUTURE DATA |

Unavailable providers return `UNAVAILABLE`; they do not contribute fabricated values or scientific conclusions.

---

# 12. One Health audit

| Dimension | Current evidence/use | Classification |
| --- | --- | --- |
| Freshwater biodiversity | Real Fs historical eDNA observation and optional GBIF context | 🟢 Real observation/context |
| Animal health | Papers link Fs as Tb host and Tb with PKD in salmonids | 🟡 Conceptual, literature-supported relevance |
| Ecosystem health | River topology and monitoring relevance only | 🟡 Conceptual connection |
| Human health | Explicitly UNKNOWN | 🔴 No implemented evidence or inference |
| Community exposure | No exposure dataset or model | 🔴 Not implemented |
| Urban freshwater systems | Generic context architecture only | 🔴 No operational urban dataset |

The One Health component is a conservative narrative framework. It produces no aggregate score, risk percentage, diagnosis, causal inference, or prediction. Fs eDNA does not establish local Tb presence, salmonid infection, or PKD.

---

# 13. Urban freshwater data

| Variable | Status | Evidence |
| --- | --- | --- |
| Urban land cover / built-up surface | PLANNED | GHSL-derived adapter; unavailable runtime client |
| Population density | NOT USED | No dataset or field found |
| Wastewater infrastructure | NOT USED | No dataset or provider found |
| Stormwater | NOT USED | No dataset or provider found |
| Combined sewer overflow | NOT USED | No dataset or provider found |
| Road runoff | NOT USED | No dataset or provider found |
| Impervious surface | PLANNED/UNVERIFIED | Could be represented by generic built-up metric, but no live source exists |
| Industrial discharge | NOT USED | No dataset or model found |
| Agricultural runoff | NOT USED | No dataset or model found |
| Human activity | NOT USED | No operational proxy beyond planned built-up context |
| Urban biodiversity observations | PARTIAL | GBIF can query occurrence context, but records are not specifically validated as urban |

Analyzing a river does not by itself establish an urban freshwater context.

---

# 14. Scientific claim-to-evidence map

| Scientific claim | Supporting data | Method | Scientific source | Strength |
| --- | --- | --- | --- | --- |
| S1 historical Fs eDNA concentration was positive on 2014-06-25 | `eDNA_data.mat` | Direct indexed extraction | Carraro dataset | VALIDATED observation |
| S1 is represented by HYRIV_ID 20446064 | Carraro coordinate and HydroRIVERS geometry | CRS transform, snap and independent regression | Carraro + HydroRIVERS | VERIFIED mapping |
| A mapped reach is upstream of another | `NEXT_DOWN` graph | Directed traversal | HydroRIVERS | Strong within loaded graph |
| A zone can hydrologically contribute to a site | Zone root and directed network | Same-reach/upstream check | HydroRIVERS | Topology-supported only |
| Candidate X separates source hypotheses | Zone roots and candidate reach | Binary signature and `r × (n-r)` | Explicit project method | Deterministic topology claim |
| A candidate is the class representative | Equivalent signature members and distances | Nearest-to-A selection | Explicit project criterion | Deterministic engineering claim |
| Multiple candidates tie | Candidate scores | Maximum comparison | Sampling engine | Deterministic under criterion |
| Validated support changes a hypothesis to SUPPORTED | Rule-tagged assessments | Conservative resolver | Project rule semantics | Validated logic, not biological certainty |
| Follow-up eDNA changes a source hypothesis | None | No validated rule | None | NOT SUPPORTED |
| Fs is a host relevant to Tb biology | Literature | Citation-backed narrative | Morris & Adams 2007 | General supported relationship |
| Tb causes PKD in salmonids | Literature | Citation-backed narrative | Sudhagar et al. 2020 | General supported relationship |
| Tb or PKD is present in this case | None | No local assay/model | None | UNKNOWN |
| GBIF occurrence proves current site presence | None | Explicitly rejected by provider limitation | GBIF context only | NOT SUPPORTED |
| S14 historically overlaps one generated candidate | Accepted S14 crosswalk and HYRIV_ID 20450127 | Exact reach-ID comparison | Carraro + reviewed crosswalk | SUPPORTED observational overlap |
| The recommended site improves biological detection | No counterfactual experiment or calibrated model | None | None | NOT VALIDATED |

---

# 15. What the system does not know

| Missing or unused factor | Consequence |
| --- | --- |
| eDNA transport rate | Connectivity cannot quantify how much DNA reaches a site |
| eDNA decay/persistence | Distance cannot be converted into surviving signal |
| Calibrated concentration model | Historical concentration is recorded but not predicted |
| Detection probability | A reachable source does not imply detection |
| Sampling-day flow/discharge | Network decisions cannot account for event-specific flow; `DIS_AV_CMS` is not sampling-day flow |
| Water velocity and travel time | The engine cannot estimate arrival timing |
| Dilution/mixing | It cannot compare expected concentration among branches |
| PCR error | False amplification or inhibition is not modeled |
| False-positive/false-negative rates | Detection/nondetection cannot be probabilistically corrected |
| Species shedding rate | Occupancy or abundance cannot be inferred from concentration |
| Temperature effects on eDNA | Weather is unavailable and no validated effect rule exists |
| Biological occupancy | Hydrological plausibility does not identify where organisms live |
| Field accessibility | Candidate `field_accessibility` remains `NOT_EVALUATED` |
| Road access, safety and land ownership | Proposed sites may be impractical or inaccessible |
| Sampling and laboratory cost | Pair separation does not optimize cost |
| Restoration interventions/outcomes | No effectiveness comparison is possible |

---

# 16. Complete resource-flow diagram

```text
SCIENTIFIC SOURCES

Carraro/Wigger research package                 HydroRIVERS v1.0 Europe
├── eDNA_data.mat                               ├── HYRIV_ID
├── data_wigger.mat                             ├── NEXT_DOWN
├── RUN_MODEL.m                                 ├── LENGTH_KM
├── data_explanation.xlsx                       ├── network attributes
└── research README/scripts                     └── line geometry
              │                                           │
              ├────────────── DATA PREFLIGHT ──────────────┤
              │                                           │
              ▼                                           ▼
 historical observations, station inventory      Wigger 49-reach graph
 Site A coordinate and station topology           edges, geometry, zones
              │                                           │
              └──────────────────┬────────────────────────┘
                                 ▼
                         HYDROLOGY ENGINE
                    upstream/downstream traversal
                     paths and network distance
                                 │
                  ┌──────────────┴──────────────┐
                  ▼                             ▼
          EVIDENCE ENGINE               CANDIDATE GENERATOR
       validated direction/strength     reachability signatures
                  │                     equivalence classes
                  ▼                             │
         HYPOTHESIS RESOLVER                    ▼
       conservative eligible zones     representative candidates
                  │                             │
                  └──────────────┬──────────────┘
                                 ▼
                    SAMPLING DECISION ENGINE
                      score = r × (n-r)
                                 │
                                 ▼
              RECOMMEND / TIE / ABSTAIN / INSUFFICIENT_DATA
                                 │
                                 ▼
                DecisionTrace + InvestigationRun snapshots

OPTIONAL CONTEXT
GBIF live occurrence API ──► context evidence ──► UNKNOWN / UNASSESSED
GHSL and weather adapters ──► UNAVAILABLE (no operational clients)

ONE HEALTH
H001 Fs observation + two cited papers
  ──► monitoring relevance narrative
  ──► local parasite, disease and human-health status remain UNKNOWN
```

---

# 17. Final resource inventory

## 🟢 Real datasets currently used

### HydroRIVERS v1.0 Europe

- **Provider:** HydroSHEDS / WWF.
- **Purpose:** mapped river topology and geometry.
- **Fields:** `HYRIV_ID`, `NEXT_DOWN`, `LENGTH_KM`, catchment/upstream areas, average discharge, stream orders, basin ID and geometry.
- **Backend:** `WiggerPreflightLoader`, `HydrologyEngineImpl`, candidate generator and sampling engine.
- **Results:** upstream graph, connectivity, paths, distance, signatures, candidates and decisions.

### Carraro/Wigger research package

- **Provider:** Carraro et al.
- **Purpose:** historical eDNA case, stations and comparative catchment topology.
- **Fields:** dates, Fs/Tb concentration, station coordinates, Carraro reach indices and network/catchment variables.
- **Backend:** `CarraroHistoricalLoader`, `CarraroV4Extractor`, demo and historical-validation modules.
- **Results:** H001, station inventory, observation table, crosswalk review and historical overlap.

### GBIF occurrence API

- **Provider:** GBIF.
- **Purpose:** optional nearby species-occurrence context.
- **Fields retained:** occurrence ID, latitude, longitude, date and dataset ID.
- **Backend:** `GbifOccurrenceProvider`.
- **Result:** provenance-bearing contextual evidence; no source-hypothesis change.

## 🟢 Real scientific methods currently implemented

- Directed river graph traversal.
- HydroRIVERS network path and length calculation.
- Coordinate transformation and network snapping.
- Zone-to-site hydrological reachability.
- Rule-based evidence direction and topology-specific strength.
- Conservative hypothesis-state resolution.
- Reachability signatures and topology equivalence classes.
- Deterministic representative selection.
- Pair-separation score `r × (n-r)`.
- Explicit recommendation, tie, abstention and insufficient-data rules.
- Append-only reinvestigation snapshots and DecisionTrace.
- Conservative historical overlap classification.

These methods are supported by the supplied databases, standard graph/GIS operations, and explicit project-defined criteria. The original Carraro Bayesian biological model is not among the implemented methods.

## 🟡 Planned or incomplete resources

- GHSL-derived urbanization data.
- Historical temperature and precipitation source.
- Real follow-up sampling records.
- Field access, safety, ownership and cost sources.
- Broader One Health evidence beyond the literature relevance pathway.
- Use of available Wigger DTM, geology, discharge, celerity and reach-width variables.

## 🔴 Missing scientific inputs

- Calibrated transport, decay, dilution and detection models.
- Sampling-day discharge, velocity and travel time.
- PCR performance and false-result probabilities.
- Species shedding and occupancy ground truth.
- Operational urban, wastewater, stormwater, runoff, population and exposure data.
- Citizen-science provider.
- Counterfactual outcomes at unsampled candidates.
- Restoration intervention and effectiveness data.

---

# 18. Simple summary for judges

### My project currently uses

Real HydroRIVERS river-network data and the Carraro/Wigger research package containing historical station, date, and Fs/Tb eDNA concentration data. It can also request optional GBIF occurrence context.

### From those datasets, it derives

The mapped detection reach, upstream river graph, directed connectivity, network distance, possible source zones, candidate-site reachability signatures, topology equivalence classes, pair-separation scores, sampling decisions, and full decision traces.

### The main scientific resources are

HydroRIVERS, Carraro et al.’s Wigger dataset/publication, standard directed graph and GIS operations, and two peer-reviewed papers supporting a limited Fs–Tb–salmonid health relevance pathway.

### The system scientifically supports

Traceable historical observations, mapped hydrological plausibility, deterministic topology-based source discrimination, conservative evidence states, and auditable sampling decisions under a defined pair-separation objective.

### The system does NOT yet claim

Species occupancy at an exact source, biological absence from nondetection, eDNA transport or decay, detection probability, abundance inference, disease diagnosis, human-health risk, an improved biological detection rate, or restoration effectiveness.

### Future data integrations are

Operational urbanization and weather providers, real follow-up samples, field feasibility/cost data, and scientifically validated transport or detection models. These integrations must remain separate from current results until real sources and validated interpretation rules are connected.
