# eDNA Evidence Investigator Backend

Production-quality backend foundation for the eDNA Evidence Investigator system. This backend provides infrastructure for investigating environmental DNA (eDNA) detections in river networks by managing cases, evaluating evidence, analyzing hydrology, and recommending sampling sites.

## Table of Contents

- [Overview](#overview)
- [Setup](#setup)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Scientific Engine Boundaries](#scientific-engine-boundaries)
- [Limitations](#limitations)
- [Development Notes](#development-notes)

## Overview

The eDNA Evidence Investigator helps investigators analyze eDNA detections by:

- **Managing investigation cases** for detected taxa at specific sites
- **Evaluating evidence compatibility** with candidate source zone hypotheses
- **Analyzing river network hydrology** using HydroRIVERS data
- **Recommending sampling sites** to discriminate between competing hypotheses

### Key Design Principles

1. **Separation of concerns**: Clean layered architecture (API → Services → Repositories/Engines → Data)
2. **Scientific boundary enforcement**: Backend provides infrastructure without inventing scientific methodology
3. **Data immutability**: Preflight artifacts are read-only; the system never modifies source data
4. **Traceability**: All decisions include audit trails showing evidence, rules, and assumptions used

## Setup

### Prerequisites

- **Python**: 3.12 or higher
- **PostgreSQL**: 14 or higher
- **Validated preflight data**: Must be present in `data_preflight/outputs/`

### Installation

1. **Create and activate a virtual environment**:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:

```bash
pip install -r requirements.txt
```

3. **Configure environment variables**:

```bash
cp .env.example .env
# Edit .env with your database credentials and data directory path
```

4. **Initialize the database**:

```bash
# Create the database
createdb edna_investigator

# Run migrations to create tables
alembic upgrade head
```

5. **Verify preflight data**:

Ensure the following files exist in `data_preflight/outputs/`:
- `site_a.json` - Detection site (Site A) data
- `upstream_reaches_real.csv` - River reach metadata
- `upstream_edges.csv` - Network connectivity
- `candidate_zones_real.geojson` - Candidate source zones
- `candidate_sampling_sites.csv` - Sampling site candidates
- `sampling_design_validation.json` - Validation metadata

## Configuration

Configuration is managed through environment variables defined in `.env` file.

### Environment Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/edna_investigator` | Yes |
| `PREFLIGHT_DATA_DIR` | Path to validated preflight data | `data_preflight/outputs` | Yes |
| `HOST` | Server host address | `0.0.0.0` | No (default: `0.0.0.0`) |
| `PORT` | Server port | `8000` | No (default: `8000`) |
| `ENVIRONMENT` | Deployment environment | `development` or `production` | No (default: `development`) |
| `DEBUG` | Enable debug mode | `true` or `false` | No (default: `false`) |

### Example .env File

```bash
# Database
DATABASE_URL=postgresql://edna_user:edna_pass@localhost:5432/edna_investigator

# Data directory (relative to project root)
PREFLIGHT_DATA_DIR=data_preflight/outputs

# Server
HOST=0.0.0.0
PORT=8000

# Environment
ENVIRONMENT=development
DEBUG=true
```

## Running the Application

### Development Server

Start the development server with auto-reload:

```bash
uvicorn app.main:app --reload
```

The API will be available at:
- **API Base**: `http://localhost:8000`
- **Interactive Docs (Swagger)**: `http://localhost:8000/docs`
- **Alternative Docs (ReDoc)**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/health`

### Production Server

For production deployment:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or use the configuration from your `.env`:

```bash
python -m app.main
```

## API Endpoints

The API is organized into several resource groups:

### Health Check

- **GET** `/health` - System health and data availability status

### Case Management

- **POST** `/cases` - Create a new investigation case
- **GET** `/cases/{case_id}` - Retrieve a specific case
- **GET** `/cases` - List all cases (with optional filtering)

### Evidence Management

- **POST** `/cases/{case_id}/evidence` - Add evidence to a case
- **GET** `/cases/{case_id}/evidence` - Retrieve all evidence for a case
- **GET** `/cases/{case_id}/evidence-assessment` - Assess evidence compatibility with zones

### Hydrology Analysis

- **GET** `/hydrology/reaches/{hyriv_id}` - Get reach metadata
- **GET** `/hydrology/upstream/{hyriv_id}` - Query upstream reaches
- **GET** `/hydrology/downstream/{hyriv_id}` - Query downstream path
- **GET** `/hydrology/distance?from_hyriv_id={id}&to_hyriv_id={id}` - Calculate network distance

### Sampling Site Management

- **POST** `/cases/{case_id}/sites` - Register a sampling site
- **GET** `/cases/{case_id}/sites` - Retrieve sampling sites for a case
- **POST** `/cases/{case_id}/zones` - Create a candidate zone
- **GET** `/cases/{case_id}/zones` - Retrieve candidate zones
- **POST** `/cases/{case_id}/sampling-decision` - Evaluate sampling candidates
- **GET** `/cases/{case_id}/decision-trace` - Retrieve decision audit trail

### Demo Data

- **GET** `/demo/wigger` - Load Wigger case demo data

### API Documentation

Full interactive API documentation with request/response schemas and examples is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Testing

### Run All Tests

```bash
pytest
```

### Run with Coverage Report

```bash
pytest --cov=app --cov-report=html
```

View coverage report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Run Specific Test Types

**Unit tests only**:
```bash
pytest tests/unit/
```

**Property-based tests only**:
```bash
pytest tests/property/
```

**Specific test file**:
```bash
pytest tests/unit/test_wigger_loader.py
```

### Testing Commands Summary

| Command | Description |
|---------|-------------|
| `pytest` | Run all tests |
| `pytest -v` | Verbose output |
| `pytest -x` | Stop at first failure |
| `pytest --cov=app` | Run with coverage |
| `pytest tests/unit/` | Run unit tests only |
| `pytest tests/property/` | Run property tests only |
| `pytest -k "test_name"` | Run tests matching pattern |

### Test Organization

- **Unit tests** (`tests/unit/`): Test specific components, examples, and edge cases
- **Property tests** (`tests/property/`): Validate universal properties across generated inputs (100+ iterations each)
- Both types are complementary and necessary for comprehensive coverage

## Project Structure

```
backend/
├── app/                                    # Application package
│   ├── main.py                            # FastAPI application entry point
│   ├── api/                               # API layer
│   │   ├── dependencies.py                # Dependency injection
│   │   └── routes/                        # Route handlers
│   │       ├── health.py                  # Health check endpoint
│   │       ├── cases.py                   # Case management
│   │       ├── evidence.py                # Evidence management
│   │       ├── hydrology.py               # Hydrology queries
│   │       ├── sampling.py                # Sampling site management
│   │       └── demo.py                    # Demo data loader
│   ├── domain/                            # Domain layer
│   │   ├── models.py                      # Domain models (Case, Site, etc.)
│   │   └── enums.py                       # Enumerations (Status values)
│   ├── schemas/                           # API schemas (Pydantic)
│   │   ├── cases.py                       # Case request/response schemas
│   │   ├── evidence.py                    # Evidence schemas
│   │   ├── hydrology.py                   # Hydrology schemas
│   │   └── sampling.py                    # Sampling schemas
│   ├── db/                                # Database layer
│   │   ├── base.py                        # SQLAlchemy base
│   │   ├── models.py                      # Database models
│   │   └── session.py                     # Session management
│   ├── repositories/                      # Data access layer
│   │   ├── cases.py                       # Case repository
│   │   ├── evidence.py                    # Evidence repository
│   │   └── sampling.py                    # Sampling repository
│   ├── services/                          # Business logic layer
│   │   ├── case_service.py                # Case orchestration
│   │   ├── evidence_service.py            # Evidence assessment
│   │   ├── hydrology_service.py           # Hydrology analysis
│   │   └── sampling_service.py            # Sampling decisions
│   └── scientific/                        # Scientific engine layer
│       ├── interfaces.py                  # Engine protocol definitions
│       ├── data_loader.py                 # Preflight data loader
│       ├── evidence/
│       │   └── engine.py                  # Evidence compatibility engine
│       ├── hydrology/
│       │   └── engine.py                  # Hydrology network engine
│       └── sampling/
│           └── engine.py                  # Sampling decision engine
├── tests/                                 # Test suite
│   ├── conftest.py                        # Shared fixtures
│   ├── unit/                              # Unit tests
│   └── property/                          # Property-based tests
├── alembic/                               # Database migrations
│   ├── versions/                          # Migration scripts
│   └── env.py                             # Alembic configuration
├── config.py                              # Configuration module
├── requirements.txt                       # Python dependencies
└── .env                                   # Environment configuration (create from .env.example)
```

## Scientific Engine Boundaries

The backend separates engineering infrastructure from scientific methodology. Scientific engines provide interfaces that return safe defaults when logic is not yet validated:

### Evidence Compatibility Engine

- **When validated rules exist**: Applies rules to assess evidence compatibility (SUPPORTS/CONTRADICTS/NEUTRAL)
- **When no rules apply**: Returns `UNKNOWN` compatibility status
- **Purpose**: Ensures the system never invents scientific interpretations

### Sampling Decision Engine

- **When criteria are defined**: Evaluates candidates and recommends sites
- **When criteria are undefined**: Returns `INSUFFICIENT_DATA` status
- **Purpose**: Prevents hardcoded recommendations; requires explicit scientific validation

### Hydrology Engine

- **Fully implemented**: Provides deterministic graph operations and distance calculations
- **Data source**: Uses validated preflight artifacts from HydroRIVERS
- **Guarantees**: Network queries are reproducible and traceable

### Scientific Review Requirements

The following areas require review and implementation by scientific experts:

1. **Evidence compatibility rules** (`app/scientific/evidence/engine.py`)
   - Define validated rules for interpreting evidence types
   - Implement rule application logic
   - Current state: Returns `UNKNOWN` for all evidence

2. **Sampling decision criteria** (`app/scientific/sampling/engine.py`)
   - Define discrimination power scoring methodology
   - Implement site evaluation algorithms
   - Current state: Returns `INSUFFICIENT_DATA` for all evaluations

3. **Evidence type definitions**
   - Define valid evidence types and their expected formats
   - Specify quality indicators and thresholds
   - Current state: Accepts arbitrary evidence types

## Limitations

### Current System Limitations

1. **No LLM integration**: System is designed for deterministic, auditable scientific decisions
2. **Scaffold scientific engines**: Evidence and sampling engines return safe defaults until validated logic is implemented
3. **Single river system**: Currently optimized for the Wigger River case study
4. **File-based hydrology**: Network data loaded from files rather than persisted to database
5. **No user authentication**: Authentication/authorization not implemented
6. **No real-time updates**: Polling-based; no websocket support

### Data Constraints

1. **Preflight data required**: System depends on validated preflight artifacts
2. **HYRIV_ID validation**: Only reaches in loaded network data are valid
3. **Read-only source data**: Preflight files must not be modified during operation
4. **Network completeness**: Upstream analysis limited to loaded reach set

### Scientific Constraints

1. **Rule-based only**: No machine learning or statistical inference implemented
2. **Manual evidence assessment**: Automated assessment requires scientific rule implementation
3. **No uncertainty quantification**: Confidence intervals and error propagation not implemented
4. **Decision transparency**: All decisions require audit trails; "black box" approaches prohibited

## Development Notes

### Architecture Principles

- **Clean separation**: API → Services → Repositories/Engines → Data
- **Dependency injection**: Services and engines injected via FastAPI dependencies
- **Domain-driven design**: Domain models independent of frameworks
- **Protocol-based interfaces**: Scientific engines defined as protocols for flexibility

### Error Handling

The system implements comprehensive error handling:

- **404 Not Found**: Case/reach/file not found
- **400 Bad Request**: Invalid input, validation failures
- **500 Internal Server Error**: System errors, data integrity violations
- **503 Service Unavailable**: Engine not initialized, database unavailable

All errors return consistent JSON structure with error type, message, and details.

### Data Integrity

- **Foreign key constraints**: Enforced at database level
- **Validation**: Pydantic schemas validate all API inputs
- **Transactions**: Database operations wrapped in transactions
- **Migration safety**: Alembic manages schema versioning

### Testing Strategy

- **Unit tests**: Validate specific examples and component behavior
- **Property tests**: Validate universal properties across randomized inputs (100+ iterations)
- **Integration tests**: Test API endpoints end-to-end
- **Anti-bias tests**: Ensure system doesn't hardcode recommendations

### Contributing Guidelines

1. **Never modify preflight data**: Source files in `data_preflight/` are immutable
2. **Maintain scientific boundaries**: Don't implement unvalidated scientific logic
3. **Include tests**: All new features require both unit and property tests
4. **Document decisions**: Add comments explaining scientific review requirements
5. **Preserve traceability**: All decisions must include audit trails

### Future Enhancements

Areas for future development (requires scientific validation):

1. **Evidence compatibility rules**: Implement validated interpretation rules
2. **Sampling decision algorithms**: Implement validated scoring methodology
3. **Network database persistence**: Move hydrology data from files to database
4. **Multi-case support**: Optimize for multiple concurrent investigations
5. **Real-time monitoring**: Add websocket support for live updates
6. **Authentication**: Implement user authentication and authorization
7. **Expanded networks**: Support multiple river systems beyond Wigger

---

**For questions or issues**, please refer to the design document at `.kiro/specs/edna-backend-foundation/design.md` or the requirements document at `.kiro/specs/edna-backend-foundation/requirements.md`.
