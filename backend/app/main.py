"""
eDNA Evidence Investigator Backend - FastAPI Application

Main application entry point for the eDNA Evidence Investigator system.
Provides RESTful API for case management, evidence assessment, hydrology
analysis, and sampling site recommendation.
"""
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError

from config import config
from app.api.dependencies import initialize_engines
from app.api.routes import (
    health,
    cases,
    evidence,
    hydrology,
    sampling,
    demo,
    context,
    follow_up_samples,
    one_health,
)


# Exception classes for custom error handling
class NotFoundError(Exception):
    """Raised when a requested resource is not found."""
    def __init__(self, message: str, resource_type: str = None, resource_id: str = None):
        self.message = message
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(self.message)


class ValidationError(Exception):
    """Raised when input validation fails."""
    def __init__(self, message: str, details: dict[str, Any] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    
    Handles startup and shutdown events:
    - Startup: Initialize engines and validate configuration
    - Shutdown: Cleanup resources (if needed)
    """
    # Startup: Validate configuration
    try:
        config.validate()
    except ValueError as e:
        # Log error and re-raise to prevent application startup
        print(f"Configuration validation failed: {e}")
        raise
    
    # Startup: Initialize scientific engines
    try:
        initialize_engines()
        print("Scientific engines initialized successfully")
    except FileNotFoundError as e:
        print(f"Failed to initialize engines - missing preflight data: {e}")
        raise
    except Exception as e:
        print(f"Failed to initialize engines: {e}")
        raise
    
    print(f"Application startup complete - environment: {config.ENVIRONMENT}")
    
    yield
    
    # Shutdown: Cleanup (none required currently)
    print("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="eDNA Evidence Investigator API",
    description=(
        "Backend API for investigating environmental DNA detections in river networks.\n\n"
        "## Features\n\n"
        "- **Case Management**: Create and manage eDNA detection investigation cases\n"
        "- **Evidence Assessment**: Add evidence and assess compatibility with hypotheses\n"
        "- **Hydrology Analysis**: Query river network relationships using HydroRIVERS data\n"
        "- **Sampling Decisions**: Evaluate and recommend sampling sites\n"
        "- **Decision Traceability**: Audit trails for all decisions\n\n"
        "## Scientific Boundaries\n\n"
        "This backend provides engineering infrastructure without implementing unvalidated "
        "scientific methodology. Scientific engines return safe defaults (UNKNOWN, INSUFFICIENT_DATA) "
        "when validated logic is not yet implemented.\n\n"
        "## Data Sources\n\n"
        "The system uses validated preflight data from the Wigger River case study:\n"
        "- HydroRIVERS v1.0 Europe for river network data\n"
        "- Verified sampling site locations and candidate zones\n"
        "- Network distance calculations and validation metadata\n\n"
        "## Authentication\n\n"
        "Currently no authentication is required. Future versions will implement user authentication.\n\n"
        "## Error Responses\n\n"
        "All errors return consistent JSON structure:\n"
        "```json\n"
        '{"error": {"type": "ErrorType", "message": "Description", "details": {}}}\n'
        "```\n\n"
        "HTTP Status Codes:\n"
        "- 200: Success\n"
        "- 201: Created\n"
        "- 400: Bad Request (invalid input)\n"
        "- 404: Not Found\n"
        "- 500: Internal Server Error\n"
        "- 503: Service Unavailable\n"
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "eDNA Evidence Investigator Team",
        "url": "https://github.com/your-org/edna-investigator",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check and system status endpoints"
        },
        {
            "name": "cases",
            "description": "Case management operations - create, retrieve, and list investigation cases"
        },
        {
            "name": "evidence",
            "description": "Evidence management - add evidence items and assess compatibility with hypotheses"
        },
        {
            "name": "hydrology",
            "description": "River network analysis - query reaches, paths, distances using HydroRIVERS data"
        },
        {
            "name": "sampling",
            "description": "Sampling site management - register sites, define zones, evaluate candidates"
        },
        {
            "name": "demo",
            "description": "Demo data loading - load the Wigger case study preflight data"
        },
        {
            "name": "root",
            "description": "Root endpoint with API information"
        }
    ]
)


# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure based on deployment environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers for custom errors
@app.exception_handler(NotFoundError)
async def not_found_error_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    """
    Handle NotFoundError exceptions with 404 response.
    
    Args:
        request: The incoming request
        exc: The NotFoundError exception
        
    Returns:
        JSONResponse with 404 status and error details
    """
    error_response = {
        "error": {
            "type": "NotFoundError",
            "message": exc.message,
            "details": {}
        }
    }
    
    if exc.resource_type:
        error_response["error"]["details"]["resource_type"] = exc.resource_type
    if exc.resource_id:
        error_response["error"]["details"]["resource_id"] = exc.resource_id
    
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=error_response
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    Handle ValidationError exceptions with 400 response.
    
    Args:
        request: The incoming request
        exc: The ValidationError exception
        
    Returns:
        JSONResponse with 400 status and validation details
    """
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "type": "ValidationError",
                "message": exc.message,
                "details": exc.details
            }
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """
    Handle ValueError exceptions (often from invalid HYRIV_IDs).
    
    Args:
        request: The incoming request
        exc: The ValueError exception
        
    Returns:
        JSONResponse with 404 or 400 status depending on error message
    """
    error_message = str(exc)
    
    # Check if this is a HYRIV_ID not found error
    if "HYRIV_ID" in error_message and "not found" in error_message:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "type": "InvalidHyrivIdError",
                    "message": error_message,
                    "details": {}
                }
            }
        )
    
    # Otherwise treat as validation error
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "type": "ValidationError",
                "message": error_message,
                "details": {}
            }
        }
    )


@app.exception_handler(FileNotFoundError)
async def file_not_found_error_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
    """
    Handle FileNotFoundError exceptions (missing preflight data).
    
    Args:
        request: The incoming request
        exc: The FileNotFoundError exception
        
    Returns:
        JSONResponse with 500 status indicating system error
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "MissingDataError",
                "message": f"Required preflight data file not found: {str(exc)}",
                "details": {
                    "file_path": str(exc).split(": ")[-1] if ": " in str(exc) else str(exc)
                }
            }
        }
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """
    Handle SQLAlchemy IntegrityError (database constraint violations).
    
    Args:
        request: The incoming request
        exc: The IntegrityError exception
        
    Returns:
        JSONResponse with 400 status for constraint violations
    """
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "type": "IntegrityError",
                "message": "Database constraint violation",
                "details": {
                    "database_error": str(exc.orig) if hasattr(exc, 'orig') else str(exc)
                }
            }
        }
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    """
    Handle RuntimeError exceptions (often engine initialization issues).
    
    Args:
        request: The incoming request
        exc: The RuntimeError exception
        
    Returns:
        JSONResponse with 503 status for service unavailable
    """
    error_message = str(exc)
    
    # Check if this is an engine initialization error
    if "Engine not initialized" in error_message or "not initialized" in error_message:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "type": "ServiceUnavailableError",
                    "message": error_message,
                    "details": {
                        "reason": "Scientific engine not properly initialized"
                    }
                }
            }
        )
    
    # Otherwise treat as internal server error
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "RuntimeError",
                "message": error_message,
                "details": {}
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle any unhandled exceptions with 500 response.
    
    Args:
        request: The incoming request
        exc: The exception
        
    Returns:
        JSONResponse with 500 status for internal server error
    """
    # In production, log this error without exposing details
    error_message = str(exc) if config.DEBUG else "Internal server error"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "InternalServerError",
                "message": error_message,
                "details": {}
            }
        }
    )


# Include routers
app.include_router(health.router)
app.include_router(cases.router)
app.include_router(evidence.router)
app.include_router(hydrology.router)
app.include_router(sampling.router)
app.include_router(demo.router)
app.include_router(context.router)
app.include_router(follow_up_samples.router)
app.include_router(one_health.router)


@app.get("/", tags=["root"])
def read_root() -> dict[str, str]:
    """
    Root endpoint with API information.
    
    Returns:
        dict: API name and documentation links
    """
    return {
        "name": "eDNA Evidence Investigator API",
        "version": "0.1.0",
        "documentation": "/docs",
        "health_check": "/health"
    }


# For running with uvicorn directly (development)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG
    )
