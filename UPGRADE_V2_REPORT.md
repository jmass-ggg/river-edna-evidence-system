# eDNA Evidence Investigator v2 Upgrade Report

## Outcome

The v2 backend upgrade is verified. The v1 checksum manifest passed before implementation. No raw or frozen input artifact and neither `SCIENCE_FREEZE_v1` file was edited.

## Demo and path handling

- Default preflight and Carraro paths resolve from the repository root, independent of the process working directory.
- Explicit `PREFLIGHT_DATA_DIR` and `CARRARO_DATA_DIR` values take priority.
- `/demo/wigger` now reads historical observation H001 directly from `eDNA_data.mat` and `RUN_MODEL.m` while keeping Site A network metadata in its separate preflight role.
- The stale `sampling_date_status` field in frozen `site_a.json` remains unchanged and is no longer treated as the authority for the historical observation.
- Demo regression verifies the date, taxon, concentration, state, provenance, four sites, three zones, and generated-candidate API response.

## Automatic candidate generation

- Eligible validated upstream reaches: 48; Site A is excluded.
- Hypothesis order is deterministic and generalized from supplied zone labels: Z1, Z2, Z3.
- Equivalence classes:

| Signature | Score | Reach count | Representative |
| --- | ---: | ---: | ---: |
| [0, 0, 0] | 0 | 39 | none |
| [0, 0, 1] | 2 | 1 | 20451169 (C) |
| [0, 1, 0] | 2 | 1 | 20450127 (B) |
| [0, 1, 1] | 2 | 6 | 20446568 |
| [1, 0, 0] | 2 | 1 | 20447392 |

- The generator naturally reproduces B and C. D (20448315) belongs to the [0, 1, 1] class but is not selected because 20446568 is nearer to Site A under the neutral representative rule.
- Representative selection does not imply greater ecological value.
- Generated representatives are evaluated by the unchanged `ScaffoldSamplingDecisionEngine`; the Wigger result is a four-way TIE under the unchanged pair-separation criterion.
- Road access, safety, land ownership, cost, and field accessibility are explicitly `NOT_EVALUATED`.

## Evidence strength

- Existing direction values remain unchanged: SUPPORTS, CONTRADICTS, NEUTRAL, UNKNOWN.
- One claim-specific rule was added: `hydrorivers.directed_connectivity_strength.v1`.
- HIGH requires validated mapping, validated zone metadata, a complete topology result, and explicit validated graph coverage.
- MEDIUM applies when mapping, zone, and topology results are validated but explicit graph-coverage metadata is absent.
- LOW applies when validation or topology completeness is missing.
- Unsupported evidence types remain UNASSESSED with the reason: “No validated strength rule exists for this evidence type.”
- Strength is explanatory metadata and does not affect sampling scores.
- No numeric confidence or biological occurrence probability is produced.

## Verification

- Full suite: 102 passed, 0 failed, 15 warnings.
- Wigger regression: 7 passed.
- Carraro regression: 3 passed.
- Sampling properties: 12 passed.
- Evidence properties: 12 passed.
- Coverage: 75% overall.
- Scientific coverage: hydrology 96%, evidence 97%, sampling 93%, candidate generator 93%, rule catalog 100%.

## Remaining limitations

- Topology score is not eDNA detection probability.
- Candidate optimization is limited to topology-based hypothesis discrimination.
- Field accessibility, cost, transport, decay, and abundance are not modeled.
- Evidence strength is claim-specific; unsupported evidence remains UNASSESSED.
- Counterfactual follow-up sites are not historical measurements.

