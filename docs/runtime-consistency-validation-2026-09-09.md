# Runtime Consistency Validation — 2026-09-09

## Diagnosis

The failed batch `2a6ab6fe-aee4-47af-95a9-4f6f5cb0e5d5` had 12 pending children.
The API loaded `apps/api/.env`, while a worker launched from `workers/` tried to load the
cwd-relative `workers/.env`, which lacked database and Redis settings. `WorkerSettings()` raised
before the job entered its guarded execution path, so no run identity was available to finalize.
The 12 children were explicitly finalized and the batch now has status `failed`.

## Runtime proof

- Profile: `live_validation`
- Database target: `localhost:5432/ai_business_radar_live_test`
- Redis target: `localhost:6379/0`
- API/worker/scheduler fingerprint: `fc14318718f5ebde`
- Redis: PONG
- PostgreSQL: accepting connections
- Web `/admin/discovery`: reachable and redirects unauthenticated requests to login
- API health: HTTP 200

## Discovery proof

- Canonical Micro Duck batch: `448dbb36-5faa-4185-bcd1-a37172708620`
- Limits: 5 videos/query, 1 page/query, 10 comments/video
- Result: `completed`, 12/12 terminal children, quota estimate 12
- Invalid-payload batch: `ebdada24-f30f-436c-9bd2-b953d518c45c`
- Injected condition: `max_pages=99`
- Result: `failed`, 2/2 terminal children, quota estimate 0
- Worker error metadata: validation location `max_pages`, safe constraint message, correlated run/query IDs

## Automated validation

- API: 176 passed, 69 integration tests skipped without their opt-in database fixture
- Workers: 21 passed
- Web: ESLint passed; 70 tests passed; production build passed
- Ruff: API and worker source/tests passed

## Security observation

During the first live run, the default `httpx` INFO logger emitted a provider URL containing the
YouTube API key. Runtime logging now forces `httpx` and `httpcore` to WARNING. The exposed key must
be rotated again; no credential is included in this report or committed files.
