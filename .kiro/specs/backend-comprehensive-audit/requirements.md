# Requirements Document: Backend Comprehensive Audit

## Introduction

This specification covers the need for a comprehensive technical audit and documentation of the eDNA Evidence Investigator backend system. The audit must verify actual implementation details, trace data flows from frontend to database, and clearly distinguish between implemented functionality versus placeholders or mocked components.

## Glossary

- **Backend_System**: The FastAPI-based server application that processes API requests
- **Scientific_Engine**: Components that implement domain-specific logic for hydrology, evidence assessment, and sampling decisions
- **Preflight_Data**: Immutable validated reference data loaded from files (HydroRIVERS, Wigger case study)
- **API_Endpoint**: HTTP route that accepts requests and returns responses
- **Domain_Model**: Python dataclass representing core business entities
- **Repository**: Data access layer for database operations
- **Service_Layer**: Business logic orchestration between repositories and engines

## Requirements

### Requirement 1: Complete Backend Documentation

**User Story:** As a backend engineer, I want comprehensive documentation of the entire backend system, so that I can understand how it works without reading all the code.

#### Acceptance Criteria

1. THE Backend_System SHALL document all API endpoints with methods, paths, purposes, authentication, requests, and responses
2. THE Documentation SHALL trace every API call from request receipt through service layer, repository, engine, database, and back to response
3. THE Documentation SHALL identify the actual file and function names where logic is implemented
4. THE Documentation SHALL distinguish between fully implemented features, partially implemented features, and mocked/placeholder functionality
5. THE Documentation SHALL explain the database schema with all tables, relationships, and constraints

### Requirement 2: API Endpoint Inventory

**User Story:** As an API consumer, I want a complete inventory of all available endpoints, so that I know what operations the backend supports.

#### Acceptance Criteria

1. THE API_Inventory SHALL list every GET, POST, PUT, PATCH, and DELETE endpoint
2. FOR EACH API_Endpoint, THE Documentation SHALL specify the HTTP method, path, authentication requirements, request format, and response format
3. THE API_Inventory SHALL include HTTP status codes that each endpoint can return
4. THE Documentation SHALL provide example requests and responses for each endpoint

### Requirement 3: Data Flow Tracing

**User Story:** As a developer, I want to trace how data flows through the system, so that I can debug issues and understand processing logic.

#### Acceptance Criteria

1. FOR EACH API_Endpoint, THE Documentation SHALL trace the complete execution path from router → service → repository/engine → database → response
2. THE Documentation SHALL identify which database tables are read or written by each operation
3. THE Documentation SHALL identify which scientific engines are invoked and what they calculate versus what they mock
4. THE Documentation SHALL show how preflight data files are loaded and used

### Requirement 4: Scientific Logic Documentation

**User Story:** As a scientist, I want to understand what scientific calculations are actually implemented, so that I can validate the methodology.

#### Acceptance Criteria

1. THE Documentation SHALL identify all Scientific_Engine components and their purposes
2. FOR EACH Scientific_Engine, THE Documentation SHALL explain the algorithm, inputs, processing logic, and outputs
3. THE Documentation SHALL clearly mark which engines return REAL calculations versus safe defaults (UNKNOWN, INSUFFICIENT_DATA)
4. THE Documentation SHALL identify which scientific rules are implemented versus placeholder

### Requirement 5: Schema Documentation

**User Story:** As a frontend developer, I want complete documentation of all request and response schemas, so that I can build correct API calls.

#### Acceptance Criteria

1. THE Documentation SHALL list all Pydantic request schemas with field names, types, validation rules, and required/optional status
2. THE Documentation SHALL list all Pydantic response schemas with field names and types
3. THE Documentation SHALL provide example JSON for all request and response types
4. THE Documentation SHALL document all enumeration values and their meanings

### Requirement 6: Database Schema Documentation

**User Story:** As a database administrator, I want complete documentation of the database schema, so that I can manage the database effectively.

#### Acceptance Criteria

1. THE Documentation SHALL list all database tables with their columns, types, and constraints
2. THE Documentation SHALL document all foreign key relationships and cascade rules
3. THE Documentation SHALL explain the purpose of each table in the domain model
4. THE Documentation SHALL identify which tables use JSONB fields and what structure they contain

### Requirement 7: Error Handling Documentation

**User Story:** As a developer, I want to understand how errors are handled, so that I can write proper error handling in clients.

#### Acceptance Criteria

1. THE Documentation SHALL list all custom exception types and when they are raised
2. THE Documentation SHALL explain the global exception handlers and what HTTP status codes they return
3. THE Documentation SHALL document the error response format
4. THE Documentation SHALL identify which errors are logged versus silently handled

### Requirement 8: Implementation Status Report

**User Story:** As a project manager, I want to know what is actually implemented versus mocked, so that I can plan development priorities.

#### Acceptance Criteria

1. THE Documentation SHALL categorize all features as REAL/IMPLEMENTED, PARTIAL, or MOCKED/PLACEHOLDER
2. THE Documentation SHALL identify which API endpoints return hardcoded data versus calculated results
3. THE Documentation SHALL identify which scientific engines implement validated logic versus safe defaults
4. THE Documentation SHALL list critical functionality that has NO test coverage

### Requirement 9: Security Assessment

**User Story:** As a security engineer, I want to identify security issues in the backend, so that I can address vulnerabilities.

#### Acceptance Criteria

1. THE Documentation SHALL identify all endpoints that lack authentication
2. THE Documentation SHALL check for hardcoded secrets or credentials in code
3. THE Documentation SHALL identify potential SQL injection risks
4. THE Documentation SHALL review CORS configuration for security issues
5. THE Documentation SHALL identify any sensitive data that is logged or exposed

### Requirement 10: Performance Analysis

**User Story:** As a performance engineer, I want to identify potential performance bottlenecks, so that I can optimize the system.

#### Acceptance Criteria

1. THE Documentation SHALL identify endpoints that load entire datasets into memory
2. THE Documentation SHALL identify N+1 query patterns in repository code
3. THE Documentation SHALL identify blocking operations in async endpoints
4. THE Documentation SHALL identify expensive calculations that lack caching

### Requirement 11: External Dependencies

**User Story:** As a DevOps engineer, I want to understand all external dependencies, so that I can manage the deployment environment.

#### Acceptance Criteria

1. THE Documentation SHALL list all Python packages with versions and purposes
2. THE Documentation SHALL list all required environment variables
3. THE Documentation SHALL identify all preflight data files that must be present
4. THE Documentation SHALL document database connection requirements

### Requirement 12: Test Coverage Report

**User Story:** As a quality assurance engineer, I want to understand test coverage, so that I can identify untested functionality.

#### Acceptance Criteria

1. THE Documentation SHALL list all test files and what they test
2. THE Documentation SHALL identify unit tests versus property-based tests versus integration tests
3. THE Documentation SHALL identify critical functionality without test coverage
4. THE Documentation SHALL explain the property-based testing strategy

