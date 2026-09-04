# YouTube AI Business Radar

Repository skeleton for a business-intelligence system that detects emerging AI business opportunities from YouTube signals.

The repository includes the frozen v0.1 intelligence pipeline, FastAPI product API, workers, and
a runnable authenticated Next.js application shell.

## Structure

- `apps/` — web and API applications
- `workers/` — YouTube ingestion, extraction, and aggregation workers
- `packages/` — shared schemas and deterministic scoring code
- `prompts/` — versioned AI prompt assets
- `database/` — migrations and seed data
- `tests/` — cross-project tests
- `docs/` — product, architecture, and development documentation

See `AGENTS.md` for project constraints and working conventions.

## Backend development

```bash
cd apps/api
uv sync
uv run uvicorn ai_business_radar_api.main:app --reload
```

Run API tests with `uv run pytest` and lint with `uv run ruff check .` from `apps/api`.

## Frontend development

```bash
cd apps/web
pnpm install
pnpm dev
```

The frontend runs on `http://localhost:3000`. See `apps/web/README.md` for required public
environment variables and validation commands.
