# Scientific Backend Freeze v3

## Freeze date

2026-10-01

## Test baseline

- Full suite: 120 passed, 0 failed, 39 warnings.
- Coverage: 75% overall.
- Wigger regression: 7 passed.
- Carraro H001 regression: 3 passed.
- Candidate-generation regression: 1 passed, 6 deselected.
- Evidence-strength regression: 5 passed, 7 deselected.
- V3 scientific-boundary and Light infrastructure tests: 18 passed.

## New in v3

- GBIF species-occurrence context through the official occurrence API adapter.
- Generic GHSL-derived urbanization context provider interface.
- Generic historical temperature and precipitation provider interface.
- Provider-isolated case context collection and retrieval APIs with provenance and limitations.
- Structured FollowUpSample persistence, validation, API, and linked `follow_up_edna_sample` evidence.
- Generic evidence-linked One Health relevance framework.
- A literature-sourced Fredericella sultana / Tetracapsuloides bryosalmonae demonstration pathway.

## One Health claim boundary

The pathway distinguishes `OBSERVED`, `SUPPORTED_RELATIONSHIP`, `POSSIBLE_RELEVANCE`, and `UNKNOWN` statements. Carraro H001 establishes an F. sultana eDNA observation. Peer-reviewed literature supports the general biological host relationship between F. sultana and T. bryosalmonae and the general relationship between T. bryosalmonae and proliferative kidney disease in salmonids.

For an Fs-only case:

- parasite presence is `UNKNOWN`;
- fish disease status is `UNKNOWN`;
- human-health impact is `UNKNOWN`;
- targeted parasite and fish-health monitoring is a possible action, not a diagnosis or risk prediction.

The pathway has no One Health score, disease probability, numeric confidence, or direct human-health claim.

## Evidence strength boundary

The validated rule `hydrorivers.directed_connectivity_strength.v1` remains limited to directed hydrological-connectivity claims. GBIF, urbanization, historical weather, and follow-up eDNA evidence remain `UNKNOWN` for compatibility and `UNASSESSED` for strength unless a later explicitly validated rule applies. No replicate, occurrence, urban, temperature, precipitation, or disease-strength thresholds were introduced.

## Unchanged scientific semantics

- HydrologyEngine directed network and distance semantics.
- Evidence direction: SUPPORTS, CONTRADICTS, NEUTRAL, UNKNOWN.
- Hydrological-connectivity strength rule and its HIGH / MEDIUM / LOW criteria.
- Sampling criterion: pair-separation score `r × (n-r)`.
- Candidate generation and deterministic equivalence-class representative selection.
- Carraro H001: S1, Fredericella sultana, observation 4, 2014-06-25, 1.29832198e-17 mol/L, DETECTED.
- Wigger Site A mapping: HYRIV_ID 20446064.
- All v1 and v2 freeze files and frozen inputs.

## Limitations

- GBIF occurrence context does not prove current biological presence at the case site.
- Urbanization context does not imply pollution, degradation, or health risk.
- Rainfall context does not prove eDNA transport.
- F. sultana evidence does not prove T. bryosalmonae presence.
- F. sultana evidence does not prove PKD or salmonid infection.
- Temperature context does not diagnose or predict PKD and does not create a disease probability.
- One Health output expresses monitoring relevance, not causal health prediction.
- Follow-up sample submission creates evidence but does not trigger automatic re-investigation, hypothesis updates, candidate regeneration, or a sampling decision.
- GHSL-derived and historical-weather values require configured provider adapters; unavailable sources return `UNAVAILABLE` rather than inferred values.

## Change policy

Any later scientific change requires scientific justification, all frozen regressions, focused tests for the new claim boundary, the full test suite, a new checksum manifest, and a new freeze version.

The authoritative v3 file list and hashes are recorded in `SCIENCE_FREEZE_v3.sha256`.
