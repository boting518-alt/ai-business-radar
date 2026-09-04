# YouTube AI Business Radar API

Runnable FastAPI skeleton for the v0.1 backend. It currently provides application-level health checks, environment-backed configuration, request correlation IDs, CORS configuration, and package boundaries. It does not connect to PostgreSQL, Redis, YouTube, Supabase Auth, or an AI provider.

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

## Run locally

From `apps/api`:

```bash
uv run uvicorn ai_business_radar_api.main:app --reload
```

The API is available under `/api/v1`. No external service credentials are required for skeleton startup or health checks.
