"""Explicit, testable SQLAlchemy engine construction."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


class DatabaseConfigurationError(RuntimeError):
    """Raised when database access is requested without valid configuration."""


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    raise DatabaseConfigurationError("DATABASE_URL must be a PostgreSQL URL")


def create_database_engine(database_url: str | None, **kwargs: object) -> AsyncEngine:
    if not database_url:
        raise DatabaseConfigurationError("DATABASE_URL is not configured")
    return create_async_engine(normalize_database_url(database_url), pool_pre_ping=True, **kwargs)
