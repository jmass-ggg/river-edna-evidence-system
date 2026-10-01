"""
Database session management and dependency injection.

Provides session factory and FastAPI dependency for database access.
"""
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config import config


# Create database engine
engine = create_engine(
    config.DATABASE_URL,
    echo=config.DEBUG,  # Log SQL queries in debug mode
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=5,  # Connection pool size
    max_overflow=10,  # Max connections beyond pool_size
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.
    
    Usage in FastAPI routes:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    
    Yields:
        Session: SQLAlchemy database session
        
    The session is automatically closed after the request completes,
    even if an exception occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """
    Create all tables defined in SQLAlchemy models.
    
    This is primarily for testing. In production, use Alembic migrations.
    """
    from app.db.base import Base
    Base.metadata.create_all(bind=engine)


def drop_tables() -> None:
    """
    Drop all tables defined in SQLAlchemy models.
    
    WARNING: This will delete all data. Use only in testing.
    """
    from app.db.base import Base
    Base.metadata.drop_all(bind=engine)
