# eDNA Evidence Investigator v3 Upgrade Report

## Outcome

The v3 backend scientific review and Light infrastructure verification are complete. The v1 and v2 frozen semantics and artifacts remain preserved. No frontend or automatic investigation update was implemented.

## Context infrastructure

- GBIF uses an injectable client for the official occurrence search API and stores compact occurrence metadata, retrieval provenance, radius, and limitations.
- Urbanization supports GHSL-derived built-up metrics with source year, resolution, spatial window, source version, temporal alignment, and provenance.
- Weather supports historical temperature and precipitation with requested coordinates, date window, source/model, retrieval time, and provenance.
- Provider outcomes are isolated as `SUCCESS`, `PARTIAL`, `UNAVAILABLE`, or `ERROR`.
- GBIF is species-occurrence context, urbanization is built-environment context, precipitation is meteorological context, and temperature is environmental context. These records do not make biological, degradation, transport, or disease claims.

## Evidence boundary

- `hydrorivers.directed_connectivity_strength.v1` remains the only validated strength rule and remains claim-specific.
- Context and follow-up evidence assess as compatibility `UNKNOWN` and strength `UNASSESSED`.
- No new strength thresholds, confidence percentages, or probabilities were added.

## Follow-up sample workflow

- Structured samples validate replicate counts, concentration/unit pairing, case/site ownership, and HYRIV_ID validity.
- Persistence creates and links one `follow_up_edna_sample` EvidenceItem in the same transaction.
- The response reports `reanalysis_required=true`.
- Submission does not run evidence assessment, update hypotheses, regenerate candidates, or create a sampling decision.

## One Health framework

The response follows:

1. Monitoring Finding
2. Ecological Relevance
3. Animal-Health Relevance
4. Community / Management Relevance
5. Possible Monitoring Action

Each statement is labeled `OBSERVED`, `SUPPORTED_RELATIONSHIP`, `POSSIBLE_RELEVANCE`, or `UNKNOWN`. There is no aggregate score.

For the Wigger Fs demonstration:

- Carraro H001 is the observed F. sultana eDNA finding.
- Peer-reviewed sources support F. sultana as a bryozoan host relevant to T. bryosalmonae biology.
- Peer-reviewed sources support T. bryosalmonae as the cause of PKD in salmonids generally.
- The allowed case conclusion is that F. sultana evidence establishes potential relevance for targeted parasite/fish-health monitoring.
- Local parasite presence, PKD status, salmonid infection, and human-health impact remain `UNKNOWN`.
- Historical weather can be displayed as context without producing a diagnosis, disease probability, or risk score.

## Peer-reviewed source metadata

- Morris, D. J. and Adams, A. (2007). “Sacculogenesis and sporogony of Tetracapsuloides bryosalmonae within the bryozoan host Fredericella sultana.” *Parasitology Research*. DOI: 10.1007/s00436-006-0371-0. PMID: 17205353.
- Sudhagar, A., Kumar, G., and El-Matbouli, M. (2020). “The Malacosporean Myxozoan Parasite Tetracapsuloides bryosalmonae: A Threat to Wild Salmonids.” *Pathogens*. DOI: 10.3390/pathogens9010016. PMID: 31877926.

## Verification

- Full suite with coverage: 120 passed, 0 failed, 39 warnings; 75% coverage.
- Wigger regression: 7 passed.
- Carraro regression: 3 passed.
- Candidate-generation focused regression: 1 passed, 6 deselected.
- Evidence-strength focused regression: 5 passed, 7 deselected.
- V3 scientific-boundary and Light infrastructure focused suite: 18 passed.
- Alembic follow-up migration is the single migration head.

## Remaining limitation

Automatic investigation update remains deferred to Step 7. New follow-up evidence is persisted and marked for reanalysis without changing the current investigation state.
