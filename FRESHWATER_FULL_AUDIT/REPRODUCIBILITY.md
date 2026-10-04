# Wigger River investigation reproducibility

## Scope

This procedure reproduces the frozen Wigger River investigation through the
public FastAPI endpoints. It verifies the source files, loads the historical
Carraro H001 observation, evaluates evidence and hydrology, generates
topology based candidates, records the sampling decision and audit trace, and
writes both machine readable and human readable results.

The runner does not alter the source artifacts. Its normalized result omits
database identifiers, timestamps, and checkout specific path prefixes.

This is functional reproducibility of the implemented workflow. Synthetic
tests verify software properties using generated or mocked inputs. The H001
record is a real historical observation. Neither reproducibility nor historical
agreement constitutes prospective real-world validation of source attribution,
sampling efficiency, cost, or biological accuracy.

## Required environment

- Python 3.12
- The packages in `backend/requirements.txt`
- A working local checkout containing the files listed below
- For a persistent run, a configured database accepted by the existing
  backend and a running FastAPI service

The isolated command uses a temporary SQLite database and starts a local
Uvicorn process. SQLite is used only for this reproducibility run; the normal
application configuration remains PostgreSQL.

## Required datasets

The script verifies SHA-256 checksums before invoking the application:

| Input | SHA-256 |
| --- | --- |
| `data_preflight/raw/carraro/eDNA_data.mat` | `9938c931402a902d686e26acca93fbc3a2cf78e061919ffebe416d7a61a536c2` |
| `data_preflight/raw/carraro/RUN_MODEL.m` | `c05f3cd49e0519029314357cb27d6c6265dd1067ff77633e2418f3b2e53b41eb` |
| `data_preflight/outputs/upstream_reaches_real.csv` | `f767d1068d7ee911a1a3cab07ff27db417858d611ae6951a629312be81ce449b` |
| `data_preflight/outputs/upstream_edges.csv` | `1811d989f680273729c2d4d24a3ad990e7a81ba7424c5336079b8f2004fcf312` |
| `data_preflight/outputs/candidate_zones_real.geojson` | `b19b025efdb5e918f340796a51f0f04d6b3adf2cbf3cc8af5e425e8289bd0368` |
| `data_preflight/outputs/candidate_sampling_sites.csv` | `8f296900d430587f01656ba9d3f82fa0ba54225d3434e74cade6ec9128f2ae59` |

The API also loads the corresponding reach geometry, Site A validation, and
sampling design artifacts from `data_preflight/outputs`.

## Run in an isolated database

From the repository root:

```bash
./venv/bin/python scripts/reproduce_wigger.py --isolated
```

The command starts the API on an available loopback port, creates a temporary
database, calls the public endpoints, shuts the service down, and writes:

- `reproducibility_outputs/wigger_result.json`
- `reproducibility_outputs/WIGGER_INVESTIGATION_REPORT.md`

The temporary database is removed after the run.

## Run against an existing backend

Start the configured backend in one terminal:

```bash
cd backend
../venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then run:

```bash
./venv/bin/python scripts/reproduce_wigger.py --base-url http://127.0.0.1:8000
```

`GET /demo/wigger` is idempotent for the frozen H001 demonstration. Repeated
execution locates the same case and evidence records instead of creating a
duplicate case.

## Expected validation checks

The checked result must contain:

- H001, station S1, *Fredericella sultana* (`Fs`), observation 4
- 2014-06-25, `1.2983219767633366e-17 mol/L`, `DETECTED`
- Carraro coordinate `634537.17, 240447.56`, reach index 1
- Site A HydroRIVERS reach 20446064 and snap distance about 64.81 m
- 49 network reaches including Site A and 145.23 km total loaded length
- zone roots Z1 20447392, Z2 20450127, and Z3 20451169
- generated reachability signatures and pair scores from the current
  `CandidateSiteGenerator`
- the actual registered site decision `TIE` for Sites B, C, and D
- rule IDs `hydrorivers.directed_contribution.v1` and
  `sampling.topology_pair_separation.v1`

Two clean isolated runs must produce byte identical `wigger_result.json`
files. The regression suite also runs the application workflow twice and
compares normalized scientific outputs.

## Verification commands

```bash
cd backend
../venv/bin/pytest -q tests/unit/test_wigger_reproducible_workflow.py \
  tests/unit/test_wigger_map_api.py \
  tests/unit/test_carraro_validation.py
../venv/bin/pytest -q
```

```bash
cd frontend
npm run lint
npm run build
npm run test:e2e
```

## Interpretation

The historical eDNA measurement is an observed record. Sites B, C, D and the
automatically generated candidates are counterfactual follow-up locations.
Directed connectivity supports a possible mapped transport path; it does not
identify a biological source. The pair-separation score is a topology measure
and is not detection probability, confidence, or expected information gain.

The historical measurement remains `UNKNOWN` in the compatibility assessment
because no validated compatibility rule exists for that evidence type. The
registered sites tie under the implemented topology criterion, so the result
does not select a unique site.

## Known limitations

- Replicate observations and laboratory assay metadata are unavailable for
  H001 in the verified record exposed by this application.
- No calibrated eDNA transport, decay, dilution, abundance, analytical error,
  or detection probability model is implemented.
- Field access, safety, land ownership, and cost are not evaluated.
- A positive follow-up result does not prove the exact source, and a negative
  result does not prove absence.
- Follow-up eDNA records can be stored and retrieved, but no validated rule
  currently lets every such record alter source hypotheses.
- Environmental providers are not invoked by the deterministic reproduction.
- One Health output expresses literature linked monitoring relevance and does
  not establish local parasite presence, fish disease, or human health impact.

## Verification recorded on 2026-10-02

- Complete backend suite: 174 passed, with 149 non-failing warnings.
- Frontend ESLint and production build: passed.
- Playwright: 18 passed and 6 intentionally skipped by viewport configuration.
- Two clean isolated Wigger runs: `PASS`; registered decision `TIE` for Sites
  B, C, and D.
- Both runs produced byte-identical `wigger_result.json` with SHA-256
  `55d0fb847f53f49efc8c44ab80b5ea1170fab529b45d5bb12f3524db3eb1d634`.
- The synthetic execution benchmark records software timing only. The workflow
  measurement summary is `NO_MEASUREMENTS`, so no field-time, cost, savings, or
  accuracy claim is made.

See `FINAL_PROJECT_COMPLETION_REPORT.md` for the tested scope, benchmark
conditions, unavailable data, and remaining field-validation requirements.
