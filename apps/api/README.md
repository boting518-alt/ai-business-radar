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

Repository methods share a caller-owned `AsyncSession`, flush or execute changes, and never commit. Application services own commit/rollback boundaries. RLS policies live in `database/migrations/0002_rls_baseline.sql`.

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

Hosted Supabase Auth should configure `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, and
`SUPABASE_JWT_AUDIENCE`. `SUPABASE_JWT_SECRET` is optional legacy HS256 compatibility and must
remain server-only. See `docs/supabase-setup-checklist.md` for the hosted setup and RLS drill.

The API is available under `/api/v1`. Redis, YouTube collection orchestration, AI-provider integration, and review business workflows are not implemented yet.

## Authentication

Protected routes accept a Supabase access token as `Authorization: Bearer <token>`. v0.1 verifies legacy Supabase HS256 tokens locally using the server-only `SUPABASE_JWT_SECRET`, with optional issuer and `authenticated` audience validation. No Supabase network request occurs per API request.

JWT identity is resolved to `user_profiles.auth_user_id`; the application role always comes from `user_profiles`, never a client-controlled JWT role claim. A valid JWT without a profile receives HTTP 403. Profile provisioning is intentionally separate.

`SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_JWT_SECRET` must remain server-side. The service role bypasses RLS, so FastAPI role checks and repository/service validation remain mandatory.

## YouTube Data API client

Set the server-only `YOUTUBE_API_KEY` to use the official YouTube Data API v3 adapter. Optional settings control the official base URL, HTTP timeout, and bounded retry attempts. The adapter supports `search.list`, `videos.list`, `channels.list`, and `commentThreads.list`; it does not scrape YouTube or fetch unofficial transcripts, and it performs no persistence or worker orchestration.

Automated tests use `httpx.MockTransport` and never require a real key or network. A manual smoke test is optional: with `YOUTUBE_API_KEY` set locally, instantiate `YouTubeClient` in an async Python shell and make one small `search_videos` request followed by `get_videos` for one returned ID. Never print the key or store the response. Live calls are not a CI requirement.

For the bounded, repeatable YouTube/OpenAI validation workflow, see
`../../docs/local-live-validation.md` and start with:

```bash
uv run python scripts/live_validation.py preflight
uv run python scripts/live_validation.py full --query "AI dental receptionist" --dry-run
```

The non-dry commands require the dedicated localhost database
`ai_business_radar_live_test`; they never start the scheduler.
