"""
Health check endpoint for system status monitoring.

Provides operational status and data load indicators for monitoring
and diagnostics.
"""
from pathlib import Path
from fastapi import APIRouter, status
from pydantic import BaseModel

from config import config


router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """
    Response schema for health check.
    
    Attributes:
        status: Operational status of the system
        preflight_data_loaded: Whether required preflight data files are accessible
        preflight_data_dir: Path to preflight data directory
        missing_files: List of missing required files (empty if all present)
    """
    status: str
    preflight_data_loaded: bool
    preflight_data_dir: str
    missing_files: list[str]


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    description="Check system operational status and verify preflight data availability"
)
def health_check() -> HealthResponse:
    """
    Health check endpoint returning system status.
    
    Returns operational status and indicates whether required preflight
    data files are loaded and accessible. Responds within 1 second.
    
    Returns:
        HealthResponse: System health status
        
    **Validates: Requirements 12.1, 12.2, 12.5**
    """
    # Define required preflight files
    required_files = [
        "site_a.json",
        "upstream_reaches_real.csv",
        "upstream_edges.csv",
        "candidate_zones_real.geojson",
        "candidate_sampling_sites.csv",
        "sampling_design_validation.json"
    ]
    
    # Check which files are missing
    missing_files = []
    preflight_dir = config.PREFLIGHT_DATA_DIR
    
    for filename in required_files:
        filepath = preflight_dir / filename
        if not filepath.exists():
            missing_files.append(filename)
    
    # Determine if all data is loaded
    preflight_data_loaded = len(missing_files) == 0
    
    # Determine overall status
    system_status = "healthy" if preflight_data_loaded else "degraded"
    
    return HealthResponse(
        status=system_status,
        preflight_data_loaded=preflight_data_loaded,
        preflight_data_dir=str(preflight_dir),
        missing_files=missing_files
    )
