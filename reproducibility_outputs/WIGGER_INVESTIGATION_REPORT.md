# Reproduced Wigger River Investigation

## Investigation summary

The frozen Wigger case evaluates the historical Fredericella sultana eDNA observation at S1 and compares upstream source-zone hypotheses. The registered-site sampling decision is **TIE**.

## Original eDNA detection

- Station: S1 (Site A)
- Species: Fredericella sultana (Fs)
- Observation index: 4
- Date: 2014-06-25
- Concentration: 1.2983219767633366e-17 mol/L
- State: DETECTED
- Replicate results and laboratory assay metadata: unavailable in the verified H001 record.

## Hydrological investigation

- Site A HydroRIVERS reach: 20446064
- Reaches including Site A: 49
- Loaded network length: 145.23 km

## Source hypotheses

| Zone | Root reach | Reaches | Length km | Validation |
| --- | ---: | ---: | ---: | --- |
| Z1 | 20447392 | 3 | 12.4 | VERIFIED |
| Z2 | 20450127 | 21 | 59.8 | VERIFIED |
| Z3 | 20451169 | 11 | 31.98 | VERIFIED |

Hydrological connection establishes a possible mapped transport pathway. It does not confirm the biological source.

## Evidence assessment

| Zone | Supports | Contradicts | Neutral | Unknown |
| --- | ---: | ---: | ---: | ---: |
| Z1 | 1 | 0 | 2 | 1 |
| Z2 | 1 | 0 | 2 | 1 |
| Z3 | 1 | 0 | 2 | 1 |

The historical eDNA measurement remains UNKNOWN because no validated compatibility rule applies to that evidence type. Directed connectivity is assessed with `hydrorivers.directed_contribution.v1`.

## Candidate comparison

| Reach | Signature | Distinguished pairs | Pair-separation score | Network distance km | Validation |
| ---: | --- | --- | ---: | ---: | --- |
| 20451169 | [0, 0, 1] | Z1 vs Z3, Z2 vs Z3 | 2 | 23.935939 | VERIFIED |
| 20450127 | [0, 1, 0] | Z1 vs Z2, Z2 vs Z3 | 2 | 19.225939 | VERIFIED |
| 20446568 | [0, 1, 1] | Z1 vs Z2, Z1 vs Z3 | 2 | 2.285939 | VERIFIED |
| 20447392 | [1, 0, 0] | Z1 vs Z2, Z1 vs Z3 | 2 | 3.585939 | VERIFIED |

## Sampling decision

**TIE** — Multiple sites share the maximum topology-only pair separation score (2 pairs): Site B, Site C, Site D

Eligible registered sites: Site B, Site C, Site D.

## Decision audit trail

- Rules: sampling.topology_pair_separation.v1
- Assumptions:
  - The supplied zones are the remaining hypotheses.
  - Each hypothesis is represented by its validated root reach.
  - A site outcome is binary directed reachability at HydroRIVERS reach resolution.
- Limitations:
  - Reachability is a mapped-network relation, not eDNA detection probability.
  - The criterion compares binary outcomes and does not model transport, decay, abundance, field access, or analytical error.

## Follow-up sampling

Sites tied or recommended by the topology criterion remain eligible for a field investigation. A follow-up record should preserve its site/reach, time, assay, controls, replicate counts, concentration when measured, collector source, and provenance. A negative result does not prove absence, and a positive result does not by itself prove the exact source.

## Environmental and One Health context

No environmental context records were collected during this deterministic reproduction.
The One Health pathway is literature-linked monitoring relevance. It does not establish local parasite presence, fish disease, or human-health impact.

## Provenance

All required inputs passed their recorded SHA-256 checksums. Full hashes and API provenance are stored in `wigger_result.json`.

## Scientific limitations

- No calibrated eDNA transport, decay, dilution, or detection-probability model.
- No verified replicate or laboratory assay metadata for H001.
- Historical eDNA evidence remains UNKNOWN under the current compatibility catalog.
- The pair-separation score measures topology-based discrimination only.
- Counterfactual candidate outcomes are unknown.
- Environmental providers are not invoked by this reproduction.
