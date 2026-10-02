# eDNA Evidence Investigator v4 Upgrade Report

## Outcome

The V4 scientific backend update is complete. Automatic reinvestigation is operational, conservative, append-only, and traceable. The scientifically supportable portion of Carraro multi-station validation is complete. Unsupported biological and counterfactual claims remain explicitly unresolved.

## Automatic reinvestigation

The explicit reinvestigation route executes:

1. current evidence assessment;
2. conservative hypothesis resolution;
3. eligible-zone selection;
4. deterministic candidate regeneration;
5. sampling decision;
6. decision trace and immutable run snapshots.

Previous decisions and completed runs remain preserved. A failed run rolls back its result changes safely. Responses expose before/after hypotheses, representative HYRIV_IDs, and decision state, plus component change flags and an overall semantic-change flag.

## Scientific behavior

`hypothesis.validated_direction_only.v1` accepts directional assessments only from `hydrorivers.directed_contribution.v1`. It returns `SUPPORTED`, `CONFLICTING`, `WEAKENED`, or `UNKNOWN` according to the presence of validated support and contradiction. It never returns `ELIMINATED` in V4.

No follow-up eDNA interpretation rule was introduced. A recorded follow-up sample remains `UNKNOWN` and `UNASSESSED`; it initiates reinvestigation but does not force a hypothesis, candidate, or decision change. When all hypotheses are unknown, the complete candidate set is retained.

## Carraro historical validation

- Reconstructed 15 stations, 301 Fs observations, and 301 Tb observations across 21 dates.
- Independently reviewed every S2–S15 proposed crosswalk using coordinate transformation, snap distance, alternatives, provenance, Carraro topology, and HydroRIVERS relationship to S1.
- Final mapping counts: 1 VERIFIED, 7 SUPPORTED, 1 AMBIGUOUS, 6 NOT_VERIFIED.
- Confirmed one accepted historical candidate overlap: generated HYRIV_ID 20450127 and supported station S14.
- Classified generated HYRIV_IDs 20451169, 20446568, and 20447392 as counterfactual with no accepted historical outcome.

The analysis validates reconstruction, deterministic mapping review, and coarse topology checks. It does not validate biological detection prediction or improved biological detection from the sampling recommendation.

## Verification

- Full suite: 130 passed, 0 failed, 112 warnings.
- Coverage: 87%.
- Wigger regression: 7 passed.
- Carraro H001 regression: 3 passed.
- Candidate generation: 1 passed, 6 deselected.
- Evidence strength: 5 passed, 7 deselected.
- V3 scientific boundaries: 8 passed.
- V4 focused suite: 10 passed.
- V1–V3 freeze checksum verification: passed.

## Remaining scientific limits

The backend has no calibrated biological detection model, validated negative-to-absence rule, counterfactual outcome data, or evidence that its recommended next site improves biological detection. Historical overlap at S14 is descriptive and does not confirm an algorithmic prediction.
