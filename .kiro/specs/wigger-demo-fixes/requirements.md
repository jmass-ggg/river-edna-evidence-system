# Requirements Document

## Introduction

This spec addresses two blocking issues preventing the Wigger demo endpoint from functioning correctly:
1. The demo route's data loader uses incorrect path resolution
2. The frozen `site_a.json` artifact contains `sampling_date_status: "NOT VERIFIED"` which causes the route to reject the data, despite independent Carraro regression verification confirming the date

These fixes are CRITICAL because they block the reference UI flow for demonstrating the system with validated historical data.

## Glossary

- **Demo_Route**: The FastAPI endpoint `GET /demo/wigger` that loads the Wigger case
- **WiggerPreflightLoader**: Data loader class that reads preflight artifacts
- **Site_A_Artifact**: The frozen JSON file `data_preflight/outputs/site_a.json`
- **Preflight_Path**: Path to `data_preflight/outputs/` directory containing validated artifacts
- **PREFLIGHT_DATA_DIR**: Environment variable for configuring data directory path
- **Carraro_Regression**: Test suite that independently verifies historical observation data

## Requirements

### Requirement 1: Path Configuration

**User Story:** As a deployment engineer, I want the demo route to respect the PREFLIGHT_DATA_DIR configuration, so that the system works from any working directory.

#### Acceptance Criteria

1. WHEN the demo route is called, THE Demo_Route SHALL use the PREFLIGHT_DATA_DIR from Config
2. WHEN PREFLIGHT_DATA_DIR is set via environment variable, THE Demo_Route SHALL resolve paths correctly
3. WHEN the demo route creates a WiggerPreflightLoader, THE loader SHALL receive the configured data directory
4. THE Demo_Route SHALL NOT hardcode relative paths like `"../data_preflight/outputs"`
5. WHEN running from any working directory, THE Demo_Route SHALL locate preflight artifacts successfully

### Requirement 2: Date Verification Handling

**User Story:** As an API consumer, I want the demo route to load Wigger data despite the frozen artifact's outdated verification status, so that I can use the validated reference case.

#### Acceptance Criteria

1. WHEN Site_A_Artifact contains `sampling_date_status` not starting with "VERIFIED", THE Demo_Route SHALL still process the request
2. WHEN the Carraro regression independently verifies the date, THE Demo_Route SHALL trust that verification
3. THE Demo_Route SHALL add metadata indicating the verification source (Carraro regression vs. frozen artifact)
4. THE Demo_Route SHALL NOT modify the frozen Site_A_Artifact file
5. IF the date is unverified by BOTH sources, THEN THE Demo_Route SHALL return HTTP 422 with clear explanation

### Requirement 3: Backward Compatibility

**User Story:** As a system maintainer, I want changes to not break existing scientific validation, so that the frozen engines remain stable.

#### Acceptance Criteria

1. THE Demo_Route SHALL NOT modify any scientific engine logic
2. THE Demo_Route SHALL NOT change database models or migrations
3. THE Demo_Route SHALL NOT alter the frozen Site_A_Artifact file
4. WHEN Carraro regression tests run, THE tests SHALL continue to pass
5. WHEN Wigger regression tests run, THE tests SHALL continue to pass
