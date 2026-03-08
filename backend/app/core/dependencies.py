"""
FastAPI dependencies for dependency injection.
Currently re-exports database session dependency from db.base
"""
from app.db.base import get_db

__all__ = ["get_db"]
