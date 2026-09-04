import pytest

from ai_business_radar_api.infrastructure.database import (
    DatabaseConfigurationError,
    create_database_engine,
    normalize_database_url,
)


def test_normalizes_standard_postgresql_url() -> None:
    assert normalize_database_url("postgresql://user:pass@localhost/db") == (
        "postgresql+asyncpg://user:pass@localhost/db"
    )


def test_rejects_missing_database_url() -> None:
    with pytest.raises(DatabaseConfigurationError, match="not configured"):
        create_database_engine(None)
