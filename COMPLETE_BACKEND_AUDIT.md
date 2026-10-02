# eDNA Evidence Investigator - Complete Backend Technical Audit

**Audit Date:** October 1, 2026  
**Auditor:** Senior Backend Engineer & API Auditor  
**Repository:** eDNA Evidence Investigator Backend  
**Purpose:** Complete technical documentation of backend architecture, APIs, data flow, and implementation status

---

## TABLE OF CONTENTS

1. [Backend Overview](#1-backend-overview)
2. [Complete API Endpoint Inventory](#2-complete-api-endpoint-inventory)
3. [Detailed API Documentation](#3-detailed-api-documentation)
4. [API Response Report](#4-api-response-report)
5. [Request/Response Schemas](#5-requestresponse-schemas)
6. [Database Report](#6-database-report)
7. [Backend Module Report](#7-backend-module-report)
8. [Business / Scientific Logic](#8-business--scientific-logic)
9. [External Data / API Integrations](#9-external-data--api-integrations)
10. [Authentication and Authorization](#10-authentication-and-authorization)
11. [Frontend ↔ Backend Connection](#11-frontend--backend-connection)
12. [Complete User Flow](#12-complete-user-flow)
13. [Backend Dependencies](#13-backend-dependencies)
14. [Environment Variables](#14-environment-variables)
15. [Error Handling](#15-error-handling)
16. [Test Report](#16-test-report)
17. [Security Review](#17-security-review)
18. [Performance Review](#18-performance-review)
19. [What is REAL vs MOCKED](#19-what-is-real-vs-mocked)
20. [API Inventory Table](#20-api-inventory-table)
21. [System Architecture](#21-system-architecture)
22. [Final Backend Status](#22-final-backend-status)
23. [Critical Questions Answered](#23-critical-questions-answered)

---

## 1. BACKEND OVERVIEW

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Language** | Python | 3.12 |
| **Framework** | FastAPI | 0.115.0 |
| **ASGI Server** | Uvicorn | 0.31.0 |
| **Database** | PostgreSQL | 14+ |
| **ORM** | SQLAlchemy | 2.0.35 |
| **Database Driver** | psycopg2-binary | 2.9.9 |
| **Validation** | Pydantic | 2.9.2 |
| **Migrations** | Alembic | 1.13.3 |
| **Testing** | pytest | 8.3.3 |
| **Property Testing** | Hypothesis | 6.112.1 |
| **Data Processing** | pandas, geopandas | 2.2.3, 1.0.1 |
| **Geospatial** | Shapely | 2.0.6 |
| **Scientific Computing** | scipy | 1.14.1 |

### Main Application Entry Point

**File:** `backend/app/main.py`

- Creates FastAPI application instance
- Configures CORS middleware (currently allows all origins)
- Implements custom exception handlers
- Includes all API routers
- Provides lifespan management for startup/shutdown

### Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── api/                 # API layer
│   │   ├── dependencies.py  # Dependency injection
│   │   └── routes/          # API route handlers
│   ├── domain/              # Domain models and enums
│   ├── schemas/             # Pydantic request/response schemas
│   ├── db/                  # Database layer (models, session)
│   ├── repositories/        # Data access layer
│   ├── services/            # Business logic layer
│   └── scientific/          # Scientific engine layer
├── tests/                   # Test suite
├── alembic/                 # Database migrations
├── config.py                # Configuration module
└── requirements.txt         # Python dependencies
```

### API Configuration

- **Base URL**: `http://localhost:8000` (development)
- **API Prefix**: None (routes at root level)
- **API Versioning**: None currently implemented
- **Docs**: `/docs` (Swagger UI), `/redoc` (ReDoc)

### Database

- **Type**: PostgreSQL 14+
- **ORM**: SQLAlchemy 2.0 with declarative models
- **Connection**: Via SQLAlchemy engine
- **Migrations**: Alembic migration system

### Authentication

- **Current Status**: ❌ NOT IMPLEMENTED
- **Method**: None
- **Authorization**: None
- **Access Control**: All endpoints are publicly accessible

### External APIs

Currently **NO external APIs** are called by the backend. The system uses:
1. **HydroRIVERS data** - Loaded from preflight files (not API)
2. **Wigger case study data** - Loaded from preflight files (not API)

**Note**: Context providers are defined but return UNAVAILABLE status:
- GBIF API client exists but returns unavailable
- Urbanization provider returns unavailable
- Weather provider returns unavailable

### Background Workers/Jobs

❌ NOT IMPLEMENTED - No background workers, queues, or async jobs

### Cache

❌ NOT IMPLEMENTED - No caching layer

### File/Object Storage

✅ **File-based storage for preflight data**:
- Location: `data_preflight/outputs/`
- Type: JSON, CSV, GeoJSON files
- Purpose: Immutable validated reference data

###