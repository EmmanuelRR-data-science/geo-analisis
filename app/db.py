"""Database connection module for PostgreSQL."""

import os
from sqlalchemy import create_engine

_engine = None


def get_database_url() -> str:
    """Build PostgreSQL connection URL from environment variables."""
    user = os.getenv("POSTGRES_USER", "admin")
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise ValueError("POSTGRES_PASSWORD environment variable is required")
    db = os.getenv("POSTGRES_DB", "geoanalisis")
    host = os.getenv("DB_HOST", "geo-db")
    return f"postgresql://{user}:{password}@{host}:5432/{db}"


def get_engine():
    """Return a singleton SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(get_database_url(), pool_size=5, max_overflow=10)
    return _engine
