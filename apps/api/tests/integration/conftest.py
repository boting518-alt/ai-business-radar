import os
import re
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)

MIGRATION = Path(__file__).parents[4] / "database/migrations/0001_initial_schema.sql"


def _with_database(url: str, database: str) -> str:
    return re.sub(r"/[^/?]+(?=\?|$)", f"/{database}", url)


@pytest_asyncio.fixture(scope="session")
async def postgres_url() -> AsyncIterator[str]:
    admin_url = os.getenv("POSTGRES_TEST_ADMIN_URL")
    if not admin_url:
        import pytest

        pytest.skip("POSTGRES_TEST_ADMIN_URL is required for PostgreSQL integration tests")
    database = f"radar_test_{uuid4().hex}"
    admin = await asyncpg.connect(admin_url)
    await admin.execute(f'CREATE DATABASE "{database}"')
    test_url = _with_database(admin_url, database)
    try:
        connection = await asyncpg.connect(test_url)
        try:
            await connection.execute(MIGRATION.read_text())
        finally:
            await connection.close()
        yield test_url
    finally:
        await admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1",
            database,
        )
        await admin.execute(f'DROP DATABASE "{database}"')
        await admin.close()


@pytest_asyncio.fixture
async def db_session(postgres_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        yield session
    await engine.dispose()
