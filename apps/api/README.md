# YouTube AI Business Radar API

Runnable FastAPI service with an async SQLAlchemy 2.x/asyncpg repository layer. The checked-in SQL migration remains the database schema authority; ORM metadata is persistence mapping only.

## Requirements

- Python 3.12+
- uv

## Setup and test

```bash
uv sync
uv run pytest
uv run ruff check .
```

The shared schema package is installed as an editable local dependency from `../../packages/schemas/python`.

## PostgreSQL

Set `DATABASE_URL` to either `postgresql://...` or `postgresql+asyncpg://...`; the former is normalized internally to the asyncpg dialect. URLs are never logged. The API and health liveness endpoint start without this value. A database operation without configuration fails explicitly, and readiness reports `database: not_configured`.

Repository methods share a caller-owned `AsyncSession`, flush or execute changes, and never commit. Application services own commit/rollback boundaries. RLS is intentionally deferred to TASK-009.

Real PostgreSQL integration tests create a random temporary database, apply `database/migrations/0001_initial_schema.sql`, run the tests, and drop it:

```bash
POSTGRES_TEST_ADMIN_URL=postgresql://user@127.0.0.1:5432/postgres uv run pytest tests/integration
```

The admin URL must point to a disposable local/test PostgreSQL role allowed to create databases. Never use production credentials. Without this variable, integration tests are skipped; SQLite is not used.

## Run locally

From `apps/api`:

```bash
uv run uvicorn ai_business_radar_api.main:app --reload
```

The API is available under `/api/v1`. Redis, YouTube, AI-provider integration, and review business workflows are not implemented yet.

## Authentication

Protected routes accept a Supabase access token as `Authorization: Bearer <token>`. v0.1 verifies legacy Supabase HS256 tokens locally using the server-only `SUPABASE_JWT_SECRET`, with optional issuer and `authenticated` audience validation. No Supabase network request occurs per API request.

JWT identity is resolved to `user_profiles.auth_user_id`; the application role always comes from `user_profiles`, never a client-controlled JWT role claim. A valid JWT without a profile receives HTTP 403. Profile provisioning is intentionally separate.

`SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_JWT_SECRET` must remain server-side. The service role bypasses RLS, so FastAPI role checks and repository/service validation remain mandatory.
