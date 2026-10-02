# Historical Validation V4

## Scope

This validation evaluates reproducible data reconstruction, provisional station-to-HydroRIVERS alignment, and topology-only comparisons. The backend has no calibrated biological detection model. Historical detections are reported as observations and are not treated as predictions or proof of source-zone biology.

## Level A — Data reconstruction: VALIDATED

- Source stations reconstructed from `RUN_MODEL.m`: 15 (S1–S15).
- Taxa reconstructed from `eDNA_data.mat`: Fs and Tb.
- Non-missing observations: 602 total; 301 Fs and 301 Tb.
- Dates: 21 distinct dates spanning 2014-05-28 through 2015-05-15.
- Observed positive concentrations: 132 Fs and 70 Tb, encoded only as `concentration_mol_l > 0`.
- Missing concentration values are omitted rather than converted to nondetections.
- Station, taxon, one-based observation index, date, concentration, source variable, and source file are preserved.
- Carraro H001 remains S1 / Fs / observation 4 / 2014-06-25 / 1.29832198e-17 mol/L / detected.

This validates extraction and encoding only. A zero concentration is not interpreted as biological absence.

## Level B — Network mapping: PARTIALLY VALIDATED

Coordinates were transformed deterministically from CH1903/LV03 (EPSG:21781) to WGS84 and distances were measured in EPSG:2056. Nearest candidates were compared with the Carraro station reach relationship to reach 1 and the HydroRIVERS relationship to validated S1.

| Review status | Count | Meaning |
| --- | ---: | --- |
| VERIFIED | 1 | S1 reproduces the existing independently validated HYRIV_ID 20446064 crosswalk. |
| SUPPORTED | 7 | S3, S6, S8, S10, S11, S13, and S14 each have one candidate within 250 m and their upstream relationship to S1 agrees across networks. Independent watercourse identity validation is absent. |
| AMBIGUOUS | 1 | S9 has multiple candidates within 250 m. |
| NOT_VERIFIED | 6 | S2, S4, S5, S7, S12, and S15 have nearest reaches beyond the 250 m review radius. |

All proposed nearest candidates reproduce the coarse expected upstream relationship to S1. This agreement does not resolve branch identity, multiple nearby candidates, coarse HydroRIVERS geometry, or stations beyond the review radius. No S2–S15 mapping is labeled VERIFIED.

## Level C — Held-out topology checks: SUPPORTED

- Crosswalk generation and review are deterministic.
- Carraro and HydroRIVERS agree that the reviewed station candidates are upstream of S1 at the tested coarse relationship.
- Candidate generation remains deterministic when evaluated independently of historical concentration outcomes.
- No station concentration was used to accept a network mapping.

These are topology checks. They do not predict eDNA detection or source presence.

## Candidate/history comparison

The four generated representatives were compared only with `VERIFIED` or `SUPPORTED` station mappings.

| Candidate HYRIV_ID | Pair-separation score | Historical classification | Historical observation summary |
| ---: | ---: | --- | --- |
| 20451169 | 2 | COUNTERFACTUAL — NO HISTORICAL OUTCOME | No accepted historical station mapping. |
| 20450127 | 2 | HISTORICAL OVERLAP AVAILABLE | S14; 21 Fs observations (15 detected) and 21 Tb observations (9 detected), 2014-05-28 to 2015-05-15. |
| 20446568 | 2 | COUNTERFACTUAL — NO HISTORICAL OUTCOME | S2's nearest candidate is this reach, but S2 is NOT_VERIFIED because its snap exceeds 250 m. |
| 20447392 | 2 | COUNTERFACTUAL — NO HISTORICAL OUTCOME | No accepted historical station mapping. |

The S14 overlap is an observational comparison. It does not confirm an algorithmic biological prediction, and the historical sampling design did not follow this algorithm.

## Temporal validation: SUPPORTED FOR DATA CONSISTENCY

Repeated observations allow date, concentration, and detection-pattern consistency checks. They do not support accuracy, precision, recall, AUC, disease probability, or a claim that the current topology algorithm predicts biological detections. No such metric was calculated.

## Explicit answers

### A. Are S2–S15 mapped reliably?

PARTIALLY. Seven are SUPPORTED, one is AMBIGUOUS, and six are NOT_VERIFIED. None is VERIFIED.

### B. Can station-level topology be validated?

PARTIALLY. The coarse upstream relationship to S1 is reproducible and agrees across the two network representations. Exact branch and reach equivalence is not validated for every station.

### C. Can candidate locations be compared with historical stations?

YES, observationally where an accepted crosswalk overlaps. One generated candidate, HYRIV_ID 20450127, overlaps supported station S14.

### D. Can biological outcomes at unsampled candidates be validated?

NO. Counterfactual sites have no historical measurement and receive no fabricated outcome.

### E. Can the system claim its next-site recommendation improves biological detection?

NO. Pair separation measures topology-based hypothesis discrimination. The historical study did not follow this algorithm, and no calibrated detection model or counterfactual biological outcome exists.

## Classification summary

### VALIDATED

- Source-faithful extraction of stations, dates, Fs/Tb concentrations, and observation indices.
- Carraro H001 values.
- S1 to HYRIV_ID 20446064.

### SUPPORTED

- Seven provisional station mappings.
- Coarse upstream topology agreement to S1.
- One historical candidate overlap at S14.

### PARTIALLY VALIDATED

- Multi-station HydroRIVERS crosswalk.
- Station-level topology beyond the coarse relationship to S1.
- Historical comparison of generated candidates.

### NOT VALIDATED

- Biological detection prediction.
- Absence inferred from nondetection.
- Improved biological detection from a recommended next site.
- Exact network equivalence for all S2–S15 stations.

### COUNTERFACTUAL / UNTESTABLE

- Biological outcomes at generated candidates without an accepted historical station overlap.
- Whether the algorithm would have outperformed the historical sampling design.
