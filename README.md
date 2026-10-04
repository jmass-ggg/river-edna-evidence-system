# FreshWater — eDNA Evidence Investigator

**From uncertain eDNA observations to clearer freshwater investigations.**

FreshWater is a research prototype that helps scientists examine environmental DNA (eDNA) observations, explore possible upstream sources, and compare locations for follow-up sampling. Its reproducible demonstration uses a historical *Fredericella sultana* observation from the **Wigger River, Switzerland**.

## The problem

Finding a species' DNA in a river raises three questions: **How reliable is the detection? Where could the DNA have come from? Where should we sample next?** Because DNA can travel downstream, a positive result does not necessarily identify the organism's exact location.

## What FreshWater does

- Records species, sampling locations, dates, replicate observations, and evidence provenance.
- Maps river connections and investigates possible upstream source zones.
- Compares candidate sampling sites and explains decisions, including ties and insufficient evidence.
- Keeps investigation history and produces scientific reports with limitations and One Health context.

## Project workflow

![FreshWater project workflow](/home/james/james/IEEE_Global/project/eDna/workflow)

**Input → River-network analysis → Source hypotheses → Sampling-site comparison → Explainable decision → Report**

In the Wigger reference demonstration, candidate sites **B, C, and D tie** under the project's topology-based scoring rule. FreshWater preserves that uncertainty instead of selecting an unsupported winner.

## Tech stack

**Frontend:** React, Vite, MapLibre GL  
**Backend:** Python, FastAPI  
**Database:** PostgreSQL, SQLAlchemy, Alembic  
**Scientific data:** Prepared HydroRIVERS Wigger network

## Run locally

You'll need **Python 3.12+**, **Node.js 20+**, **PostgreSQL**, and the prepared `data_preflight/outputs/` Wigger files.

**1. Backend** — from the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Create a PostgreSQL database and set `DATABASE_URL` in `backend/.env` to your local connection string. Then run:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

**2. Frontend** — in a second terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. The backend API documentation is at **http://localhost:8000/docs**.

## Scientific scope

FreshWater is a **draft research prototype**, not a field-validated source-identification tool. Its current hydrological analysis uses the prepared Wigger network. River connectivity indicates possible pathways, **not proof** of biological presence, DNA transport, disease, or improved field outcomes.
