# Scientific Backend Freeze v2

## Freeze date

2026-10-01

## Test baseline

- Full suite: 102 passed, 0 failed, 15 warnings.
- Coverage: 75% overall.
- Wigger regression: 7 passed.
- Carraro H001 regression: 3 passed.
- Sampling property tests: 12 passed.
- Evidence property tests: 12 passed.

## New in v2

- Stable repository-root preflight path handling with explicit environment override priority.
- Working Wigger demo using independently loaded Carraro H001 historical metadata.
- Automatic candidate generation across validated upstream reaches.
- Deterministic topology equivalence classes and neutral representative selection.
- Claim-specific evidence strength metadata for directed hydrological connectivity.

## Unchanged scientific semantics

- HydrologyEngine directed network and distance semantics.
- Evidence direction: SUPPORTS, CONTRADICTS, NEUTRAL, UNKNOWN.
- Sampling criterion: pair-separation score `r × (n-r)`.
- Carraro H001: S1, Fredericella sultana (Fs), observation 4, 2014-06-25, 1.29832198e-17 mol/L, DETECTED.
- Wigger Site A mapping: HYRIV_ID 20446064.
- `SCIENCE_FREEZE_v1.md`, `SCIENCE_FREEZE_v1.sha256`, and all frozen v1 input/source data remain unedited. Scientific code is versioned forward under v2, so the v1 manifest continues to describe the v1 code state rather than the v2 working tree.

## Wigger v2 candidate-generation reference

- Eligible upstream reaches: 48.
- Equivalence classes: [0,0,0] (39 reaches, score 0), [0,0,1] (1, score 2), [0,1,0] (1, score 2), [0,1,1] (6, score 2), [1,0,0] (1, score 2).
- Representatives: 20451169, 20450127, 20446568, 20447392.
- B and C are reproduced. D remains in the [0,1,1] class; 20446568 is the deterministic nearest-to-A representative.
- Existing decision engine result for generated representatives: TIE.

## Evidence strength reference

- Rule: `hydrorivers.directed_connectivity_strength.v1`, version 1.0.0.
- Strength states: HIGH, MEDIUM, LOW, UNASSESSED.
- Strength describes the hydrological-connectivity evidence claim only.
- Unsupported evidence remains UNASSESSED.
- Strength does not change sampling scoring.

## Limitations

- Topology score is not eDNA detection probability.
- Candidate optimization is only under the stated topology criterion.
- Field accessibility, road access, safety, land ownership, and cost are not modeled.
- Transport and decay are not modeled.
- Evidence strength is claim-specific.
- Unsupported evidence remains UNASSESSED.
- Counterfactual sites are not historical measurements.
- Representative selection does not imply greater ecological value.

## Change policy

Any later scientific change requires scientific justification, Wigger and Carraro regressions, candidate-generation and evidence-strength regressions, the full test suite, a new checksum manifest, and a new freeze version.

The authoritative v2 file list and hashes are recorded in `SCIENCE_FREEZE_v2.sha256`.
