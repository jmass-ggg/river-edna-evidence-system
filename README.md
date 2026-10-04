# FreshWater — eDNA Evidence Investigator

**An explainable research prototype for investigating uncertain freshwater eDNA detections and planning more informative follow-up sampling.**

FreshWater helps freshwater researchers record environmental DNA (eDNA) observations, explore plausible upstream source regions using river-network topology, compare sampling locations, and preserve the evidence and reasoning behind each investigation. Its reproducible reference case is based on a historical *Fredericella sultana* observation in the **Wigger River, Switzerland**.

> **Project status:** Reproducible Wigger River research prototype; scientific-review status **Draft**. The software supports topology-based investigation and sampling decisions. It does **not** establish the true biological source of an eDNA detection, estimate species abundance, predict DNA transport, or claim proven field efficiency or accuracy improvements.

## Contents

- [The problem](#the-problem)
- [What FreshWater does](#what-freshwater-does)
- [How it works](#how-it-works)
- [Scientific methodology](#scientific-methodology)
- [Wigger River demonstration](#wigger-river-demonstration)
- [Technology and architecture](#technology-and-architecture)
- [Getting started](#getting-started)
- [API overview](#api-overview)
- [Testing and reproducibility](#testing-and-reproducibility)
- [Datasets and integrations](#datasets-and-integrations)
- [One Health relevance and potential impact](#one-health-relevance-and-potential-impact)
- [Scope and limitations](#scope-and-limitations)
- [Further documentation](#further-documentation)

## The problem

eDNA analysis can identify genetic material released by organisms into water, but a detection at a sampling site does not necessarily tell researchers **where an organism lives or where the DNA originated**. In connected rivers, DNA may be transported downstream; replicate results may also be uncertain, and several upstream regions may be compatible with the same observation.

This creates practical questions for freshwater monitoring:

1. What evidence supports or limits the interpretation of a detection?
2. Which upstream regions have a valid hydrological connection to the sampling site?
3. Where could researchers sample next to distinguish competing source hypotheses?
4. How can the assumptions, decisions, and follow-up records remain transparent and reproducible?

FreshWater provides a structured workflow for investigating these questions without treating hydrological compatibility as proof of biological presence.

## What FreshWater does

| Capability | Description |
| --- | --- |
| Investigation management | Create and review freshwater eDNA investigations, including multiple target species and detection contexts within one parent investigation. |
| Observation records | Store sampling dates, replicate results, assay metadata, source, and provenance. |
| Location matching | Match and explicitly confirm sampling coordinates against the prepared Wigger river geometry. |
| Hydrological analysis | Traverse directed upstream/downstream connections and calculate along-network distances using prepared HydroRIVERS data. |
| Source hypotheses | Define source zones and assess validated network connectivity to detection or candidate sites. |
| Evidence assessment | Classify evidence as `SUPPORTS`, `CONTRADICTS`, `NEUTRAL`, or `UNKNOWN` under applicable rules. |
| Sampling candidate generation | Find eligible reaches whose connectivity signatures distinguish competing source-zone hypotheses. |
| Explainable decisions | Record a `RECOMMEND`, `TIE`, `ABSTAIN`, or `INSUFFICIENT_DATA` result with candidate scores and decision traces. |
| Field-planning notes | For tied candidates, record a practical site choice and constraints without altering the scientific score. |
| Follow-up and history | Record subsequent samples and preserve versioned reinvestigation runs. |
| Scientific workspace | Inspect investigations using interactive maps, evidence panels, sampling comparisons, and reports. |
| Environmental context | Retrieve optional GBIF occurrence and historical weather context, subject to provider availability. |
| One Health context | Display evidence-bounded ecological and fish-health relevance for the verified historical reference pathway. |

### Intended users

Freshwater ecologists, eDNA researchers, biodiversity-monitoring teams, environmental agencies, and researchers planning follow-up field investigations.

## How it works

```text
Register species, location, sampling event, and observations
                           |
                           v
            Match to the supported river network
                           |
                           v
                Inspect upstream connectivity
                           |
                           v
            Define and evaluate source hypotheses
                           |
                           v
           Generate and compare sampling candidates
                           |
                           v
            Review the decision and its audit trace
                           |
                           v
       Record field choices, follow-up samples, and history
```

A scientist starts an investigation with a target species, location, collection date, relevant HydroRIVERS reach, and any available eDNA observations. The application stores the observations in an appropriate species/site/event **detection context**, preserving separation when an investigation includes multiple species or sampling events.

It then examines the directed river network and the connectivity of proposed upstream source zones. The candidate generator compares eligible sampling reaches and produces distinct connectivity signatures. The decision engine scores the candidates, explains ties or insufficient evidence, and saves the evaluation. Researchers can subsequently record field observations and create versioned reinvestigations.

**Inputs** include scientific names, coordinates, reach identifiers, dates, replicate results, observation provenance, proposed zones, and follow-up sampling information. **Outputs** include persisted investigation records, mapped river reaches and sites, hypothesis/evidence assessments, candidate comparisons, sampling decisions, decision traces, and printable reports.

## Scientific methodology

### 1. Directed river-network analysis

The `HydrologyEngine` represents the prepared Wigger HydroRIVERS reaches as a directed graph. It supports upstream queries, downstream paths, reachability tests, common-downstream identification, and network-distance calculations. A directed path establishes **topological compatibility**, not observed DNA transport.

The scientific rule `hydrorivers.directed_contribution.v1` assesses whether a proposed source-zone root can contribute to a given reach **in the represented river network**. The rules retain `UNKNOWN` or unassessed outcomes when evidence cannot be interpreted using a validated method.

### 2. Candidate-site discrimination

Each candidate site receives a binary signature indicating which source-zone roots can reach it. For `n` competing hypotheses, if `r` roots can reach the candidate, its topology-only pair-separation score is:

```text
score = r × (n − r)
```

The score counts hypothesis pairs that have different connectivity outcomes at that site. It is **not** a detection probability, an ecological suitability score, or a validated measure of expected information gain in field conditions.

The decision engine produces:

- `RECOMMEND` when one candidate has the uniquely highest positive score;
- `TIE` when multiple candidates share the highest positive score;
- `ABSTAIN` when no candidate meaningfully distinguishes the hypotheses;
- `INSUFFICIENT_DATA` when the evaluation lacks required validated inputs.

### 3. Traceable evidence and reinvestigation

Assessments record the rule applied, evidence references, status, scientific limits, and decision rationale. Follow-up observations can be stored, and subsequent investigation runs are versioned. **New positive or negative follow-up observations do not currently trigger a validated biological rule that updates source-hypothesis probabilities or confirms a source.**

Relevant implementations are in `backend/app/scientific/`, including `hydrology/engine.py`, `evidence/engine.py`, `rules/catalog.py`, `hypothesis.py`, and `sampling/`.

## Wigger River demonstration

The packaged reference investigation uses a historical eDNA record from the Wigger River:

| Reference property | Value |
| --- | --- |
| Historical case | Carraro H001, station S1 |
| Target species | *Fredericella sultana* |
| Sampling date | 2014-06-25 |
| Original coordinates | 47.31400039098192, 7.895400745863826 |
| Matched HydroRIVERS reach | `20446064` |
| Prepared upstream network | 49 reaches, including the detection reach |
| Competing source regions | Z1, Z2, Z3 |
| Registered sampling alternatives | Sites B, C, D |
| Registered-site result | `TIE` — all three sites score 2 |

Sites B, C, and D have the following zone-reachability signatures:

| Site | Z1 / Z2 / Z3 | Pair-separation score |
| --- | --- | ---: |
| B | `010` | 2 |
| C | `001` | 2 |
| D | `011` | 2 |

All three sites separate two hypothesis pairs under the implemented topology-only criterion. The application correctly preserves the **tie** rather than inventing a uniquely superior site. Automatically generated representatives are a separate candidate set and also produce a tie in the frozen reproduction.

To load the demonstration from a running backend, request `GET /demo/wigger`, or use the **Wigger demo** option in the frontend.

## Technology and architecture

| Layer | Technologies / responsibility |
| --- | --- |
| Frontend | React 18, Vite 6, React Router 7, MapLibre GL, Lucide icons |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| Persistence | PostgreSQL, SQLAlchemy 2, Alembic |
| Scientific processing | Python, pandas, GeoPandas, Shapely, SciPy, rule-based graph and sampling engines |
| Testing | pytest, Hypothesis, Node's test runner, Playwright, ESLint |
| Reference data | Prepared HydroRIVERS v1.0 Europe data, Wigger GeoJSON/CSV artifacts, historical Carraro research data |

```text
React frontend / scientific map / reports
                 |
                 v
         FastAPI + Pydantic
                 |
         Application services
              /     \
             v       v
    Scientific engines   SQLAlchemy repositories
             |                   |
    Wigger reference data     PostgreSQL
```

### Repository layout

```text
eDna/
├── frontend/
│   ├── src/pages/             # Home, dashboard, investigations, workspace, sites, reports
│   ├── src/components/        # Scientific map, location matcher, context manager, etc.
│   ├── src/services/api.js    # Backend API client
│   └── tests/                 # Frontend API and browser tests
├── backend/
│   ├── app/api/routes/        # FastAPI endpoints
│   ├── app/services/          # Application workflows
│   ├── app/scientific/        # Hydrology, evidence, hypothesis, sampling logic
│   ├── app/repositories/      # Persistence logic
│   ├── app/db/                # SQLAlchemy database models and sessions
│   ├── app/schemas/           # Pydantic request/response models
│   ├── alembic/               # Database migrations
│   └── tests/                 # Unit, property, and integration tests
├── data_preflight/
│   ├── raw/                   # Historical source datasets (if distributed locally)
│   ├── scripts/               # Network/data-preparation scripts
│   └── outputs/               # Validated Wigger artifacts (required at runtime)
├── scripts/                   # Reproduction, validation, and benchmark tools
├── reproducibility_outputs/   # Generated Wigger audit and result artifacts
├── SCIENCE_FREEZE_v*.sha256   # Reference-data provenance/checksums
└── FINAL_PROJECT_COMPLETION_REPORT.md
```

> Large/raw datasets and some generated outputs are ignored by the repository's `.gitignore`. A Git checkout may therefore require the prepared `data_preflight/outputs/` artifacts to be supplied separately. Do not commit credentials or redistribute third-party scientific datasets without checking their licenses and attribution requirements.

## Getting started

### Prerequisites

- Python **3.12+** and `pip`
- Node.js and npm compatible with the Vite 6 toolchain (Node.js **20+** recommended)
- PostgreSQL **14+**
- The prepared `data_preflight/outputs/` Wigger artifacts

Commands below assume a local development checkout with `backend/`, `frontend/`, and `data_preflight/` inside the same repository directory.

### 1. Configure and start the backend

From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate     # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env          # On Windows, copy the file manually if needed
```

Create a PostgreSQL database and edit `backend/.env` to match your local credentials:

```bash
createdb edna_investigator
```

Example values in `backend/.env`:

```dotenv
DATABASE_URL=postgresql://YOUR_USER:YOUR_PASSWORD@localhost:5432/edna_investigator
PREFLIGHT_DATA_DIR=../data_preflight/outputs
HOST=127.0.0.1
PORT=8000
ENVIRONMENT=development
DEBUG=true
```

**Path note:** The application resolves an explicitly set `PREFLIGHT_DATA_DIR` relative to the process working directory. `../data_preflight/outputs` is correct when Uvicorn is started from `backend/`. Alternatively, remove that variable to use the application's built-in repository-root default, or set an absolute path. Do not use the placeholder database credentials unchanged.

Apply the database migrations and start the server:

```bash
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend is available at:

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health/data check: `http://localhost:8000/health`

### 2. Start the frontend

In a separate terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open the local URL displayed by Vite (typically `http://localhost:5173`). The frontend defaults to `http://localhost:8000` for API calls. If your backend runs elsewhere, set `VITE_API_BASE_URL` in the frontend's environment.

### 3. Explore the application

Open the dashboard, load the Wigger demonstration, and inspect the investigation workspace. You can view observations, river-network geometry, competing source zones, site comparisons, evidence classifications, decision traces, and reports. Creating other species or detection contexts is supported **within the geographic and scientific scope of the prepared network**.

## API overview

The FastAPI Swagger UI contains the definitive, executable request/response schemas. Major endpoint groups include:

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Service and preflight-data status |
| `GET /demo/wigger` | Load or retrieve the reference investigation |
| `GET /demo/wigger/map` | Obtain reference map data |
| `GET /cases` and `POST /cases` | List and create investigations |
| `POST /cases/multi-detection` | Create a multi-detection investigation |
| `GET/POST /cases/{case_id}/detection-contexts` | Work with species/site/event contexts |
| `GET/POST /cases/{case_id}/evidence` | Inspect or add scientific evidence |
| `GET /cases/{case_id}/evidence-assessment` | Assess evidence compatibility |
| `GET /hydrology/upstream/{hyriv_id}` | Explore upstream reaches |
| `POST /hydrology/match-location` | Find a candidate Wigger reach for a location |
| `GET/POST /cases/{case_id}/generated-candidates` | Inspect or persist candidate sites |
| `GET/POST /cases/{case_id}/sampling-decision` | Retrieve or evaluate a sampling decision |
| `GET /cases/{case_id}/decision-trace` | Inspect a decision's rationale |
| `GET/POST /cases/{case_id}/follow-up-samples` | Manage follow-up observations |
| `POST /cases/{case_id}/reinvestigate` | Create a versioned investigation run |
| `GET /cases/{case_id}/one-health` | Read bounded One Health interpretation |

See [`backend/API_DOCUMENTATION.md`](backend/API_DOCUMENTATION.md) for additional API guidance.

## Testing and reproducibility

### Run the automated checks

Backend (from `backend/`, with the virtual environment active):

```bash
python -m pytest
```

Frontend (from `frontend/`):

```bash
npm test
npm run lint
npm run build
npm run test:e2e
```

Browser tests require the Playwright browser dependencies and the test configuration's backend setup. Review `frontend/playwright.config.js` before running them. PostgreSQL-specific integration tests require their documented disposable-database configuration; ordinary backend tests also use isolated SQLite.

### Reproduce the frozen Wigger investigation

From the repository root, with backend dependencies installed:

```bash
python scripts/reproduce_wigger.py --isolated
```

The isolated mode starts a local API against a temporary SQLite database, verifies the reference-data checksums, executes the Wigger workflow, and writes results to `reproducibility_outputs/`. It does not require your development PostgreSQL database; **the frozen raw and prepared reference files must still be available**.

### Recorded verification status

The repository's [`FINAL_PROJECT_COMPLETION_REPORT.md`](FINAL_PROJECT_COMPLETION_REPORT.md), dated **October 2, 2026**, records:

| Check | Recorded outcome |
| --- | --- |
| Backend pytest | 174 passed; 149 non-failing warnings |
| Frontend lint and production build | Passed |
| Playwright browser workflow | 18 passed; 6 intentionally skipped |
| Isolated Wigger reproduction | Passed on two consecutive runs |
| Registered-site and generated-site decisions | Both `TIE` |

These are results recorded for the tested repository state, **not a claim that every newer revision or deployment has been independently retested**. Reproducibility and automated functional tests also do not substitute for prospective scientific field validation.

## Datasets and integrations

| Data source | Use and availability |
| --- | --- |
| [HydroRIVERS](https://www.hydrosheds.org/products/hydrorivers) | The prepared Wigger graph provides directed reach connectivity, geometry, and reach lengths. |
| Historical Carraro research material | Supplies documented historical eDNA observations for the Wigger reference case. |
| [GBIF](https://www.gbif.org/) | Optional species-occurrence context through an integrated API adapter; occurrence records do not prove present-day presence at the investigated site. |
| [Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api) | Optional gridded historical weather context; not an on-site water-quality measurement. |
| GHSL built-up surface | Urbanization adapter is present, but reproducible spatial raster extraction is not operational in the current application. |

The frozen Wigger reproduction uses prepared local scientific data; it does not depend on a successful live GBIF or weather request.

## One Health relevance and potential impact

FreshWater's immediate contribution is **transparent environmental evidence and more structured monitoring decisions**. For the verified *Fredericella sultana* historical pathway, the application explains the established host relationship with *Tetracapsuloides bryosalmonae*, a parasite relevant to proliferative kidney disease in salmonid fish.

This relationship motivates ecological and animal-health monitoring, but a detection of *F. sultana* does **not** establish local parasite presence, fish infection, disease, or human-health consequences. The full evidence-backed One Health interpretation is limited to the provenance-linked historical reference case; it is not automatically transferred to arbitrary species or investigations.

The platform could help scientists organize evidence, compare monitoring options, and document field decisions. Improvements in cost, field efficiency, accuracy, and environmental outcomes remain **potential benefits**, not measured results of the current prototype.

## Scope and limitations

- **Geographic scope:** Scientific hydrology and location matching are based on the prepared Wigger network, not a general worldwide river-data service.
- **Evidence scope:** Hydrological connectivity is assessed; source abundance, DNA transport/decay, detectability, ecological suitability, and species-distribution probabilities are not modeled or scientifically validated.
- **Follow-up scope:** New samples and investigation runs can be recorded, but there is no validated biological update rule that converts follow-up results into source probabilities or ground truth.
- **Context scope:** GBIF and weather are contextual inputs and do not change the validated biological hypothesis classification. GHSL spatial urbanization calculations are not operational.
- **Scientific-review status:** **Draft**. Prospective field sampling, independent source-reference standards, reviewed geographic crosswalks, and external scientific review are still needed.
- **Deployment scope:** Authentication, authorization, and production-specific hardening are not implemented. Do not deploy this research prototype publicly with sensitive data as-is.

## Further documentation

- [`backend/README.md`](backend/README.md) — backend setup, service design, and API fundamentals.
- [`backend/API_DOCUMENTATION.md`](backend/API_DOCUMENTATION.md) — API documentation.
- [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) — reproduction and checksum guidance.
- [`SCIENTIFIC_VALIDATION_REPORT.md`](SCIENTIFIC_VALIDATION_REPORT.md) — scientific checks and boundaries.
- [`HISTORICAL_VALIDATION_V4.md`](HISTORICAL_VALIDATION_V4.md) — historical observation validation.
- [`FINAL_PROJECT_COMPLETION_REPORT.md`](FINAL_PROJECT_COMPLETION_REPORT.md) — dated software-verification outcomes and remaining field-validation requirements.

---

**FreshWater's central idea:** turn an uncertain freshwater eDNA observation into a transparent, reproducible investigation and an explainable next-sampling decision—without claiming conclusions the evidence cannot support.
