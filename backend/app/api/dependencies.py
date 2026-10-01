"""
Dependency injection for FastAPI application.

Provides factory functions for database sessions and scientific engines
that can be used across API routes via FastAPI's dependency injection.
"""
from sqlalchemy.orm import Session

from app.db.session import get_db as _get_db
from app.scientific.hydrology.engine import HydrologyEngine
from app.scientific.evidence.engine import EvidenceCompatibilityEngineImpl
from app.scientific.sampling.engine import ScaffoldSamplingDecisionEngine
from app.scientific.data_loader import WiggerPreflightLoader
from config import config


# Database session dependency (re-export from session module)
def get_db() -> Session:
    """
    Get database session dependency.
    
    This is a re-export of the session factory from app.db.session
    for convenient import in route modules.
    
    Yields:
        Session: SQLAlchemy database session
        
    Note:
        The session is automatically committed or rolled back based on
        whether an exception occurred during request handling.
    """
    yield from _get_db()


# Global engine instances (initialized on startup)
_hydrology_engine: HydrologyEngine | None = None
_evidence_engine: EvidenceCompatibilityEngineImpl | None = None
_sampling_engine: ScaffoldSamplingDecisionEngine | None = None


def initialize_engines() -> None:
    """
    Initialize scientific engines with preflight data.
    
    This function is called during application startup to load
    preflight data and construct engine instances. It validates
    that required data files exist.
    
    Raises:
        FileNotFoundError: If required preflight files are missing
        ValueError: If data validation fails
    """
    global _hydrology_engine, _evidence_engine, _sampling_engine
    
    # Load preflight data for hydrology engine
    loader = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
    reaches = loader.load_reaches()
    edges = loader.load_edges()
    
    # Initialize engines
    _hydrology_engine = HydrologyEngine(reaches, edges)
    _evidence_engine = EvidenceCompatibilityEngineImpl()
    _sampling_engine = ScaffoldSamplingDecisionEngine()


def get_hydrology_engine() -> HydrologyEngine:
    """
    Get hydrology engine dependency.
    
    Returns:
        HydrologyEngine: Initialized hydrology engine
        
    Raises:
        RuntimeError: If engine not initialized (call initialize_engines first)
    """
    if _hydrology_engine is None:
        raise RuntimeError(
            "HydrologyEngine not initialized. "
            "Call initialize_engines() during application startup."
        )
    return _hydrology_engine


def get_evidence_engine() -> EvidenceCompatibilityEngineImpl:
    """
    Get evidence compatibility engine dependency.
    
    Returns:
        EvidenceCompatibilityEngineImpl: Initialized evidence engine
        
    Raises:
        RuntimeError: If engine not initialized (call initialize_engines first)
    """
    if _evidence_engine is None:
        raise RuntimeError(
            "EvidenceCompatibilityEngine not initialized. "
            "Call initialize_engines() during application startup."
        )
    return _evidence_engine


def get_sampling_engine() -> ScaffoldSamplingDecisionEngine:
    """
    Get sampling decision engine dependency.
    
    Returns:
        ScaffoldSamplingDecisionEngine: Initialized sampling engine
        
    Raises:
        RuntimeError: If engine not initialized (call initialize_engines first)
    """
    if _sampling_engine is None:
        raise RuntimeError(
            "SamplingDecisionEngine not initialized. "
            "Call initialize_engines() during application startup."
        )
    return _sampling_engine
