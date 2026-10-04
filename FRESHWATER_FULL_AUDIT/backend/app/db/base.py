"""
SQLAlchemy declarative base configuration.

This module provides the base class for all SQLAlchemy models.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    
    All database models should inherit from this class to be tracked
    by SQLAlchemy's declarative system.
    """
    pass
