# eDNA Evidence Investigator API Documentation

This document provides comprehensive documentation for the eDNA Evidence Investigator API endpoints, including request/response formats, examples, and usage guidance.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: Configure based on deployment

## Authentication

Currently, no authentication is required. Future versions will implement authentication.

## Interactive Documentation

The API provides auto-generated interactive documentation:

- **Swagger UI**: `http://localhost:8000/docs` - Interactive API exploration and testing
- **ReDoc**: `http://localhost:8000/redoc` - Clean, readable documentation

## Response Format

All responses follow consistent JSON structure:

### Success Response

```json
{
  "id": "uuid",
  "field1": "value1",
  "field2": "value2",
  "created_at": "2024-06-15T10:30:00Z"
}
```

### Error Response

```json
{
  "error": {
    "type": "ErrorType",
    "message": "Human-readable error description",
    "details": {
      "additional": "context"
    }
  }
}
```

## HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful GET request |
| 201 | Created | Successful POST request creating a resource |
| 400 | Bad Request | Invalid input, validation failure |
| 404 | Not Found | Resource not found (case, reach, file) |
| 500 | Internal Server Error | System error, data integrity violation |
| 503 | Service Unavailable | Engine not initialized, database unavailable |

---

## Endpoints

### Health Check

#### GET /health

Check system operational status and verify preflight data availability.

**Response**: `200 OK`

```json
{
  "status": "healthy",
  "preflight_data_loaded": true,
  "preflight_data_dir": "data_preflight/outputs",
  "missing_files": []
}
```

**Response Fields**:
- `status`: "healthy" or "degraded"
- `preflight_data_loaded`: Whether all required files are present
- `preflight_data_dir`: Path to preflight data directory
- `missing_files`: List of missing required files (empty if all present)

---

### Case Management

#### POST /cases

Create a new eDNA detection investigation case.

**Request Body**:

```json
{
  "target_taxon": "Salmo trutta",
  "observation_date": "2024-06-15",
  "detection_site_latitude": 47.2345,
  "detection_site_longitude": 7.8901,
  "detection_site_hyriv_id": 20449905,
  "metadata": {
    "collector": "Field Team A",
    "sample_id": "WT-001"
  }
}
```

**Request Fields**:
- `target_taxon` (string, required): Scientific name of detected taxon
- `observation_date` (date, required): Detection date (YYYY-MM-DD)
- `detection_site_latitude` (float, required): Latitude in decimal degrees (-90 to 90)
- `detection_site_longitude` (float, required): Longitude in decimal degrees (-180 to 180)
- `detection_site_hyriv_id` (int, required): HydroRIVERS reach ID (must exist in network)
- `metadata` (object, optional): Additional case-specific metadata

**Response**: `201 Created`

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "target_taxon": "Salmo trutta",
  "observation_date": "2024-06-15",
  "detection_site_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "status": "ACTIVE",
  "created_at": "2024-06-15T10:30:00Z",
  "updated_at": "2024-06-15T10:30:00Z",
  "metadata": {
    "collector": "Field Team A",
    "sample_id": "WT-001"
  }
}
```

**Response Fields**:
- `id`: Unique case identifier (UUID)
- `target_taxon`: Scientific name
- `observation_date`: Detection date
- `detection_site_id`: UUID of the detection site
- `status`: Case status (ACTIVE, UNDER_REVIEW, COMPLETED, ARCHIVED)
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `metadata`: Additional metadata

**Errors**:
- `400`: Invalid input (missing fields, invalid coordinates, invalid date)
- `404`: HYRIV_ID not found in loaded network

---

#### GET /cases/{case_id}

Retrieve a specific case by ID.

**Path Parameters**:
- `case_id` (UUID, required): Case identifier

**Response**: `200 OK`

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "target_taxon": "Salmo trutta",
  "observation_date": "2024-06-15",
  "detection_site_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "status": "ACTIVE",
  "created_at": "2024-06-15T10:30:00Z",
  "updated_at": "2024-06-15T10:30:00Z",
  "metadata": {}
}
```

**Errors**:
- `404`: Case not found

---

#### GET /cases

List all cases with optional filtering.

**Query Parameters**:
- `status` (CaseStatus, optional): Filter by case status
- `target_taxon` (string, optional): Filter by taxon name
- `limit` (int, optional): Maximum results (1-1000)
- `offset` (int, optional): Skip N results (default: 0)

**Response**: `200 OK`

```json
{
  "cases": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "target_taxon": "Salmo trutta",
      "observation_date": "2024-06-15",
      "detection_site_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "status": "ACTIVE",
      "created_at": "2024-06-15T10:30:00Z",
      "updated_at": "2024-06-15T10:30:00Z",
      "metadata": {}
    }
  ],
  "total": 1
}
```

**Response Fields**:
- `cases`: Array of case objects
- `total`: Total number of cases

---

### Evidence Management

#### POST /cases/{case_id}/evidence

Add evidence to a case.

**Path Parameters**:
- `case_id` (UUID, required): Case identifier

**Request Body**:

```json
{
  "evidence_type": "water_temperature",
  "source": "sensor_station_A",
  "value": 18.5,
  "observed_at": "2024-06-15T14:30:00Z",
  "quality": "high",
  "provenance": {
    "sensor_id": "TS-001",
    "calibration_date": "2024-06-01"
  }
}
```

**Request Fields**:
- `evidence_type` (string, required): Type/category of evidence
- `source` (string, required): Origin of the evidence
- `value` (any, required): The evidence value (flexible type)
- `observed_at` (datetime, optional): When evidence was observed
- `quality` (string, optional): Quality indicator
- `provenance` (object, optional): Provenance tracking metadata

**Response**: `201 Created`

```json
{
  "id": "c3d4e5f6-a7b8-9012-cdef-123456789abc",
  "case_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "evidence_type": "water_temperature",
  "source": "sensor_station_A",
  "value": 18.5,
  "observed_at": "2024-06-15T14:30:00Z",
  "quality": "high",
  "provenance": {
    "sensor_id": "TS-001"
  },
  "created_at": "2024-06-15T15:00:00Z"
}
```

**Errors**:
- `400`: Invalid input
- `404`: Case not found

---

#### GET /cases/{case_id}/evidence

Retrieve all evidence for a case.

**Path Parameters**:
- `case_id` (UUID, required): Case identifier

**Response**: `200 OK`

```json
[
  {
    "id": "c3d4e5f6-a7b8-9012-cdef-123456789abc",
    "case_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "evidence_type": "water_temperature",
    "source": "sensor_station_A",
    "value": 18.5,
    "observed_at": "2024-06-15T14:30:00Z",
    "quality": "high",
    "provenance": {},
    "created_at": "2024-06-15T15:00:00Z"
  }
]
```

---

#### GET /cases/{case_id}/evidence-assessment

Assess evidence compatibility with candidate zone hypotheses.

**Path Parameters**:
- `case_id` (UUID, required): Case identifier

**Response**: `200 OK`

```json
[
  {
    "zone_id": "d4e5f6a7-b8c9-0123-def0-123456789bcd",
    "zone_label": "Z1",
    "assessments": [
      {
        "evidence_id": "c3d4e5f6-a7b8-9012-cdef-123456789abc",
        "compatibility": "UNKNOWN",
        "rule_id": null,
        "reason": "No validated scientific rule applies to this evidence type",
        "provenance": {
          "engine_status": "incomplete_ruleset"
        }
      }
    ],
    "summary": {
      "supports": 0,
      "contradicts": 0,
      "neutral": 0,
      "unknown": 1
    }
  }
]
```

**Response Fields**:
- `zone_id`: UUID of the candidate zone
- `zone_label`: Human-readable zone label (e.g., "Z1")
- `assessments`: Array of evidence assessments
  - `evidence_id`: UUID of evidence item
  - `compatibility`: SUPPORTS, CONTRADICTS, NEUTRAL, or UNKNOWN
  - `rule_id`: Scientific rule ID (null if no rule applies)
  - `reason`: Explanation of assessment
  - `provenance`: Provenance metadata
- `summary`: Counts by compatibility status

**Notes**:
- Returns `UNKNOWN` compatibility when no validated scientific rule applies
- Ensures system never invents scientific interpretations

---

### Hydrology Analysis

#### GET /hydrology/reaches/{hyriv_id}

Get river reach metadata by HYRIV_ID.

**Path Parameters**:
- `hyriv_id` (int, required): HydroRIVERS reach identifier

**Response**: `200 OK`

```json
{
  "hyriv_id": 20449905,
  "next_down": 20449906,
  "length_km": 2.5,
  "upland_skm": 450.3,
  "dis_av_cms": 12.7
}
```

**Response Fields**:
- `hyriv_id`: Unique reach identifier
- `next_down`: Downstream reach ID (null if terminal)
- `length_km`: Reach length in kilometers
- `upland_skm`: Upstream contributing area in square kilometers
- `dis_av_cms`: Average discharge in cubic meters per second

**Errors**:
- `404`: HYRIV_ID not found in loaded network

---

#### GET /hydrology/upstream/{hyriv_id}

Query all reaches upstream of the specified reach.

**Path Parameters**:
- `hyriv_id` (int, required): Target reach identifier

**Response**: `200 OK`

```json
{
  "target_hyriv_id": 20449905,
  "upstream_reach_ids": [20450127, 20451169, 20449904, 20449903],
  "count": 4
}
```

**Response Fields**:
- `target_hyriv_id`: The queried reach
- `upstream_reach_ids`: List of all reaches that flow toward target
- `count`: Number of upstream reaches

**Errors**:
- `404`: HYRIV_ID not found in loaded network

---

#### GET /hydrology/downstream/{hyriv_id}

Query the downstream path from a starting reach.

**Path Parameters**:
- `hyriv_id` (int, required): Starting reach identifier

**Query Parameters**:
- `stop_hyriv_id` (int, optional): Stopping reach identifier

**Response**: `200 OK`

```json
{
  "start_hyriv_id": 20450127,
  "stop_hyriv_id": 20449905,
  "path": [20450127, 20449906, 20449905],
  "length": 3
}
```

**Response Fields**:
- `start_hyriv_id`: Starting reach
- `stop_hyriv_id`: Stopping reach (null if path to terminus)
- `path`: Ordered list of reach IDs
- `length`: Number of reaches in path

**Errors**:
- `404`: HYRIV_ID not found in loaded network
- `400`: Stop reach not downstream of start reach

---

#### GET /hydrology/distance

Calculate network distance between two reaches.

**Query Parameters**:
- `from_hyriv_id` (int, required): Source reach identifier
- `to_hyriv_id` (int, required): Target reach identifier

**Response**: `200 OK`

```json
{
  "from_hyriv_id": 20450127,
  "to_hyriv_id": 20449905,
  "distance_km": 8.3,
  "path": [20450127, 20449906, 20449905]
}
```

**Response Fields**:
- `from_hyriv_id`: Source reach
- `to_hyriv_id`: Target reach
- `distance_km`: Network distance in kilometers (null if not connected)
- `path`: Ordered path (null if not connected)

**Errors**:
- `404`: HYRIV_ID not found in loaded network
- `400`: Reaches not connected (from not upstream of to)

---

### Sampling Site Management

#### POST /cases/{case_id}/sites

Register a sampling site for a case.

**Path Parameters**:
- `case_id` (UUID, required): Case identifier

**Request Body**:

```json
{
  "label": "Site B",
  "latitude": 47.2456,
  "longitude": 7.8912,
  "hyriv_id": 20450127,
  "site_type": "BRANCH_SPECIFIC",
  "validation_status": "VERIFIED",
  "network_latitude": 47.2457,
  "network_longitude": 7.8913,
  "snap_distance_m": 15.2,
  "role": "Z1_discriminator",
  "metadata": {}
}
```

**Request Fields**:
- `label` (string, required): Human-readable label
- `latitude` (float, required): Site latitude (-90 to 90)
- `longitude` (float, required): Site longitude (-180 to 180)
- `hyriv_id` (int, required): HydroRIVERS reach ID
- `site_type` (SiteType, required): DETECTION_SITE, BRANCH_SPECIFIC, SHARED_TRUNK, or FOLLOW_UP
- `validation_status` (ValidationStatus, required): VERIFIED, MATCHED, SUPPORTED, or NOT_VERIFIED
- `network_latitude` (float, optional): Snapped network latitude
- `network_longitude` (float, optional): Snapped network longitude
- `snap_distance_m` (float, optional): Distance from observation to network in meters
- `role` (string, optional): Functional role in sampling strategy
- `metadata` (object, optional): Additional metadata

**Response**: `201 Created`

```json
{
  "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "case_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "label": "Site B",
  "latitude": 47.2456,
  "longitude": 7.8912,
  "hyriv_id": 20450127,
  "site_type": "BRANCH_SPECIFIC",
  "validation_status": "VERIFIED",
  "network_latitude": 47.2457,
  "network_longitude": 7.8913,
  "snap_distance_m": 15.2,
  "role": "Z1_discriminator",
  "metadata": {}
}
```

**Errors**:
- `400`: Invalid input
- `404`: Case or HYRIV_ID not found

---

#### GET /cases/{case_id}/sites

Retrieve all sampling sites for a case.

**Path Parameters**:
- `case_id` (UUID, required): Case identifier

**Response**: `200 OK` - Array of sampling site objects

---

#### POST /cases/{case_id}/zones

Create a candidate source zone for a case.

**Path Parameters**:
- `case_id` (UUID, required): Case identifier

**Request Body**:

```json
{
  "label": "Z1",
  "root_hyriv_id": 20450127,
  "reach_ids": [20450127, 20450128, 20450129],
  "validation_status": "VERIFIED",
  "metadata": {
    "area_sqkm": 125.3
  }
}
```

**Request Fields**:
- `label` (string, required): Human-readable zone label
- `root_hyriv_id` (int, required): Zone root reach ID
- `reach_ids` (array[int], required): List of reach IDs in zone
- `validation_status` (ValidationStatus, required): Validation status
- `metadata` (object, optional): Additional metadata

**Response**: `201 Created`

```json
{
  "id": "d4e5f6a7-b8c9-0123-def0-123456789bcd",
  "case_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "label": "Z1",
  "root_hyriv_id": 20450127,
  "reach_ids": [20450127, 20450128, 20450129],
  "validation_status": "VERIFIED",
  "metadata": {
    "area_sqkm": 125.3
  }
}
```

**Errors**:
- `400`: Invalid input
- `404`: Case or HYRIV_ID not found

---

#### GET /cases/{case_id}/zones

Retrieve all candidate zones for a case.

**Path Parameters**:
- `case_id` (UUID, required): Case identifier

**Response**: `200 OK` - Array of candidate zone objects

---

#### POST /cases/{case_id}/sampling-decision

Evaluate sampling site candidates and make recommendation.

**Path Parameters**:
- `case_id` (UUID, required): Case identifier

**Response**: `201 Created`

```json
{
  "id": "e5f6a7b8-c9d0-1234-ef01-23456789cdef",
  "case_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "INSUFFICIENT_DATA",
  "recommended_site_ids": [],
  "rationale": "Final scientific scoring criteria are not yet defined",
  "created_at": "2024-06-15T16:00:00Z"
}
```

**Response Fields**:
- `id`: Decision UUID
- `case_id`: Associated case UUID
- `status`: RECOMMEND, TIE, ABSTAIN, or INSUFFICIENT_DATA
- `recommended_site_ids`: List of recommended site UUIDs
- `rationale`: Explanation for decision
- `created_at`: Decision timestamp

**Notes**:
- Returns `INSUFFICIENT_DATA` when scientific criteria are not yet validated
- Ensures system never invents recommendations

---

#### GET /cases/{case_id}/decision-trace

Retrieve decision audit trail.

**Path Parameters**:
- `case_id` (UUID, required): Case identifier

**Response**: `200 OK`

```json
{
  "decision_id": "e5f6a7b8-c9d0-1234-ef01-23456789cdef",
  "evidence_used": ["c3d4e5f6-a7b8-9012-cdef-123456789abc"],
  "rules_applied": [],
  "hydrology_checks": [
    {
      "operation": "network_distance",
      "from": 20450127,
      "to": 20449905,
      "result_km": 8.3
    }
  ],
  "assumptions": ["Zone definitions represent realistic source regions"],
  "limitations": ["Scientific scoring criteria not yet validated"],
  "created_at": "2024-06-15T16:00:00Z"
}
```

**Response Fields**:
- `decision_id`: Decision UUID
- `evidence_used`: List of evidence item UUIDs
- `rules_applied`: List of scientific rule IDs
- `hydrology_checks`: List of hydrology operations performed
- `assumptions`: List of assumptions made
- `limitations`: List of known limitations
- `created_at`: Trace timestamp

---

### Demo Data

#### GET /demo/wigger

Load Wigger case study preflight data.

**Response**: `200 OK`

```json
{
  "case_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "target_taxon": "Salmo trutta",
  "observation_date": "2018-06-01",
  "detection_site_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "sites_created": 4,
  "zones_created": 3,
  "summary": {
    "sites": ["Site A (S1)", "Site B", "Site C", "Site D"],
    "zones": ["Z1", "Z2", "Z3"],
    "validation_status": "All data verified from preflight artifacts",
    "convergence_point": 20449905,
    "data_source": "data_preflight/outputs/"
  }
}
```

**Response Fields**:
- `case_id`: Created case UUID
- `target_taxon`: Taxon name
- `observation_date`: Detection date
- `detection_site_id`: Site A UUID
- `sites_created`: Number of sites created
- `zones_created`: Number of zones created
- `summary`: Summary of loaded data

**Errors**:
- `500`: Preflight files missing

---

## Data Types

### Enumerations

#### CaseStatus
- `ACTIVE`: Case is active and being investigated
- `UNDER_REVIEW`: Case is under review
- `COMPLETED`: Investigation completed
- `ARCHIVED`: Case archived

#### SiteType
- `DETECTION_SITE`: Location where eDNA was detected
- `BRANCH_SPECIFIC`: Site specific to one branch/zone
- `SHARED_TRUNK`: Site on shared trunk (downstream convergence)
- `FOLLOW_UP`: Additional follow-up sampling site

#### ValidationStatus
- `VERIFIED`: Manually verified as correct
- `MATCHED`: Matched to network within threshold
- `SUPPORTED`: Supported by evidence
- `ASSUMPTION`: Assumed based on methodology
- `NOT_VERIFIED`: Not yet verified

#### EvidenceCompatibility
- `SUPPORTS`: Evidence supports hypothesis
- `CONTRADICTS`: Evidence contradicts hypothesis
- `NEUTRAL`: Evidence is neutral
- `UNKNOWN`: Compatibility unknown (no rule applies)

#### SamplingDecisionStatus
- `RECOMMEND`: Specific site(s) recommended
- `TIE`: Multiple sites have equal value
- `ABSTAIN`: No basis for preference
- `INSUFFICIENT_DATA`: Cannot evaluate with available data

---

## Usage Examples

### Example 1: Create Case and Add Evidence

```bash
# 1. Create a case
curl -X POST http://localhost:8000/cases \
  -H "Content-Type: application/json" \
  -d '{
    "target_taxon": "Salmo trutta",
    "observation_date": "2024-06-15",
    "detection_site_latitude": 47.2345,
    "detection_site_longitude": 7.8901,
    "detection_site_hyriv_id": 20449905,
    "metadata": {}
  }'

# Response: {"id": "case-uuid", ...}

# 2. Add evidence to the case
curl -X POST http://localhost:8000/cases/case-uuid/evidence \
  -H "Content-Type: application/json" \
  -d '{
    "evidence_type": "water_temperature",
    "source": "sensor_A",
    "value": 18.5,
    "quality": "high"
  }'
```

### Example 2: Query Hydrology

```bash
# Get upstream reaches
curl http://localhost:8000/hydrology/upstream/20449905

# Calculate network distance
curl "http://localhost:8000/hydrology/distance?from_hyriv_id=20450127&to_hyriv_id=20449905"
```

### Example 3: Load Demo Data

```bash
# Load Wigger case study
curl http://localhost:8000/demo/wigger
```

---

## Rate Limiting

Currently no rate limiting is implemented. Future versions will add rate limiting for production use.

## Versioning

API version is included in the response headers and documentation. Current version: `0.1.0`

Future versions will use URL versioning (e.g., `/v1/cases`, `/v2/cases`).

---

**For more information, see the interactive documentation at `/docs` or `/redoc`.**
