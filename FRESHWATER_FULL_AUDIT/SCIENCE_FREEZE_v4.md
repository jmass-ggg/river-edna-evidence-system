# Scientific Backend Freeze v4

## Freeze date

2026-10-01

## Verification baseline

- V3 freeze documents: checksum verification passed before and after V4 work.
- Light V4 starting suite: 126 passed, 0 failed, 84 warnings.
- Final suite: 130 passed, 0 failed, 112 warnings.
- Final coverage: 87% overall.

## New in v4

- Append-only `InvestigationRun` history with hypothesis-state and generated-candidate snapshots.
- Conservative hypothesis resolver `hypothesis.validated_direction_only.v1`.
- Explicit automatic reinvestigation through the evidence, hypothesis, candidate-generation, and sampling-decision engines.
- Before/after result reporting and an explicit semantic-change result.
- Decision traces containing run identity, evidence, rules, hypothesis reasoning, hydrology checks, candidate criterion, assumptions, and limitations.
- Carraro S1–S15 inventory, observation table, provisional HydroRIVERS crosswalk, and independent scientific review.
- Tiered historical validation and candidate/history overlap classification.

## Hypothesis resolver

Only assessments produced by the validated `hydrorivers.directed_contribution.v1` rule can alter a hypothesis state.

- one or more `SUPPORTS` and no `CONTRADICTS`: `SUPPORTED`;
- both `SUPPORTS` and `CONTRADICTS`: `CONFLICTING`;
- one or more `CONTRADICTS` and no `SUPPORTS`: `WEAKENED`;
- no validated directional assessment: `UNKNOWN`.

`ELIMINATED` is not emitted because V4 defines no validated elimination rule. Evidence counts are not treated as strength. If every state is `UNKNOWN`, all zones remain eligible so the system preserves the conservative candidate set.

## Follow-up evidence boundary

No new biological interpretation rule was added. `follow_up_edna_sample`, historical eDNA, GBIF, weather, urbanization, and One Health context remain `UNKNOWN` compatibility and `UNASSESSED` strength unless a separately validated rule applies. A newly recorded follow-up sample therefore triggers a reproducible reinvestigation run but cannot itself alter source hypotheses in V4.

## Historical validation boundary

- Carraro reconstruction contains 15 stations and 602 non-missing observations: 301 Fs and 301 Tb.
- Mapping review yields 1 `VERIFIED`, 7 `SUPPORTED`, 1 `AMBIGUOUS`, and 6 `NOT_VERIFIED` stations.
- S1 remains `VERIFIED` as HYRIV_ID 20446064.
- One generated candidate, HYRIV_ID 20450127, overlaps the supported S14 mapping. Its historical observations are reported only as an observational comparison.
- The other three generated candidates are counterfactual and have no historical outcome.

The authoritative details and limitations are in `HISTORICAL_VALIDATION_V4.md`.

## Unchanged scientific semantics

- HydrologyEngine directed graph and distance semantics.
- Evidence direction: `SUPPORTS`, `CONTRADICTS`, `NEUTRAL`, `UNKNOWN`.
- `hydrorivers.directed_connectivity_strength.v1` and its HIGH / MEDIUM / LOW criteria.
- Pair-separation score `r × (n-r)`.
- Deterministic equivalence-class representative selection.
- Carraro H001: S1, Fredericella sultana, observation 4, 2014-06-25, 1.29832198e-17 mol/L, DETECTED.
- Wigger Site A: HYRIV_ID 20446064.
- V1, V2, and V3 freeze documents and manifests.

## Limitations

- There is no calibrated eDNA detection probability model.
- A negative sample does not prove biological absence.
- Unsupported evidence cannot alter hypotheses.
- Counterfactual candidate outcomes remain unknown.
- The historical sampling design did not follow this algorithm.
- The biological benefit of a recommended site is not proven; direct historical overlap permits observation only.
- No restoration-effectiveness claim is supported.
- Provisional station crosswalks do not establish exact reach equivalence for every station.

## Change policy

Any later scientific change requires explicit justification, focused tests, all frozen regressions, the full suite, a new versioned report, and a new checksum manifest.
