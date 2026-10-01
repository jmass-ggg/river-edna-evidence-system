"""
Configuration module for eDNA Evidence Investigator Backend.

Loads configuration from environment variables with sensible defaults.
"""
import os
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def _configured_path(environment_name: str, default_relative: str) -> Path:
    """Resolve explicit paths as supplied and defaults from the repository root."""
    configured = os.getenv(environment_name)
    if configured:
        return Path(configured).expanduser().resolve()
    return (REPOSITORY_ROOT / default_relative).resolve()


class Config:
    """Application configuration with environment variable support."""
    
    # Database configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://edna_user:edna_pass@localhost:5432/edna_investigator"
    )
    
    # Preflight data directory
    PREFLIGHT_DATA_DIR: Path = _configured_path(
        "PREFLIGHT_DATA_DIR", "data_preflight/outputs"
    )
    CARRARO_DATA_DIR: Path = _configured_path(
        "CARRARO_DATA_DIR", "data_preflight/raw/carraro"
    )
    
    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    @classmethod
    def validate(cls) -> None:
        """
        Validate required configuration on startup.
        
        Raises:
            ValueError: If required configuration is missing or invalid.
        """
        if not cls.DATABASE_URL:
            raise ValueError(
                "DATABASE_URL configuration is required. "
                "Set DATABASE_URL environment variable."
            )
        
        if not cls.PREFLIGHT_DATA_DIR.exists():
            raise ValueError(
                f"PREFLIGHT_DATA_DIR does not exist: {cls.PREFLIGHT_DATA_DIR}. "
                f"Ensure preflight data directory is available."
            )


# Global config instance
config = Config()
