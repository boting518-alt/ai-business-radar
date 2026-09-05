# Local MVP Runbook

This runbook starts a local demonstration with synthetic data. It does not enable fake production
behavior and must not use a production Supabase project or production business data.

## Prerequisites

- PostgreSQL 16
- Redis
- Python 3.12+ and `uv`
- Node.js LTS and `pnpm`
- A local Supabase Auth-compatible issuer, or development JWTs mapped to the placeholder auth UUIDs
  below

Copy `.env.example` to local, uncommitted environment files. Demo mode requires `DATABASE_URL`,
`REDIS_URL`, `SUPABASE_JWT_SECRET`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE`,
`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_API_BASE_URL`.

Live ingestion additionally requires `YOUTUBE_API_KEY`, `AI_PROVIDER=openai`, `OPENAI_API_KEY`, and
the four `AI_MODEL_*` values. Demo browsing does not require YouTube or OpenAI credentials.

## 1. PostgreSQL and migrations

Start an isolated PostgreSQL 16 instance and create a development database. Apply migrations once,
in numeric order:

```bash
for migration in database/migrations/[0-9]*.sql; do
  psql -X -v ON_ERROR_STOP=1 "$DATABASE_URL" -f "$migration"
done
```

The initial migration supplies a local `auth.uid()` compatibility function only when the host does
not already provide it. It never replaces Supabase's implementation.

## 2. Synthetic demo seed

```bash
psql -X -v ON_ERROR_STOP=1 "$DATABASE_URL" -f database/seeds/demo_mvp.sql
```

All seeded names begin with `Demo:` or are otherwise explicitly described as synthetic. Placeholder
auth mappings are:

- admin auth UUID `00000000-0000-0000-0000-000000000101`
- analyst auth UUID `00000000-0000-0000-0000-000000000102`

Configure local Auth/JWT subjects to match these UUIDs; the seed contains no login credentials.

## 3. Redis

Start Redis locally and set, for example, `REDIS_URL=redis://127.0.0.1:6379/0`. Do not expose an
unauthenticated development Redis port beyond localhost.

## 4. FastAPI

```bash
cd apps/api
uv sync
uv run uvicorn ai_business_radar_api.main:app --reload
```

The API listens on the configured `API_HOST`/`API_PORT`, normally `http://localhost:8000`.

## 5. Workers and scheduler

Use two terminals:

```bash
cd workers
uv sync
uv run dramatiq ai_business_radar_workers.worker
```

```bash
cd workers
uv run python -m ai_business_radar_workers.scheduler
```

Collection jobs require a YouTube key only when executed. AI actors also require their provider,
model, and OpenAI configuration. Trend, scoring, and maintenance actors do not call an LLM.

## 6. Next.js

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm dev
```

Open `http://localhost:3000`, authenticate as a locally mapped analyst or admin, and use Radar,
Opportunity Detail, Signals, Watchlist, and Admin Review. The seed is repeatable through conflict-safe
inserts, but a clean database gives the most predictable demonstration.

## Validation and shutdown

Run component validation from each workspace using its README commands. Stop the web, scheduler,
worker, API, Redis, and PostgreSQL processes after the demo. Never copy placeholder JWT subjects or
development secrets into production configuration.

## Local Live Validation

For bounded validation against the official YouTube and OpenAI APIs, use the explicit CLI described
in `docs/local-live-validation.md`. It requires a separate localhost database named
`ai_business_radar_live_test`, never starts the scheduler, and writes ignored reports under
`artifacts/live-validation/`. Start with config-only preflight and dry-run; real API calls occur only
after you explicitly run a non-dry command.
