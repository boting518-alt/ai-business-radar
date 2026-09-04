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

MIGRATIONS = sorted((Path(__file__).parents[4] / "database/migrations").glob("[0-9]*.sql"))


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
            await connection.execute(
                """
                DO $$ BEGIN CREATE ROLE anon NOLOGIN;
                    EXCEPTION WHEN duplicate_object THEN NULL; END $$;
                DO $$ BEGIN CREATE ROLE authenticated NOLOGIN;
                    EXCEPTION WHEN duplicate_object THEN NULL; END $$;
                DO $$ BEGIN CREATE ROLE service_role NOLOGIN BYPASSRLS;
                    EXCEPTION WHEN duplicate_object THEN NULL; END $$;
                CREATE SCHEMA IF NOT EXISTS auth;
                CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID LANGUAGE SQL STABLE AS $$
                    SELECT NULLIF(current_setting('request.jwt.claim.sub', TRUE), '')::UUID
                $$;
                GRANT USAGE ON SCHEMA auth TO authenticated, service_role;
                GRANT EXECUTE ON FUNCTION auth.uid() TO authenticated, service_role;
                """
            )
            for migration in MIGRATIONS:
                await connection.execute(migration.read_text())
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


@pytest_asyncio.fixture(scope="session")
async def rls_postgres_url(postgres_url: str) -> str:
    return postgres_url
