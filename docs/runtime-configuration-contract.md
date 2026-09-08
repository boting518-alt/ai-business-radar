# Runtime Configuration Contract

Status: v0.1 baseline for TASK-044C.

## Source and precedence

`apps/api/.env` is the canonical local server-side environment file for the API, worker, and
scheduler. Its path is resolved from the repository location, never the current working directory.
Real process environment variables override that file. Browser-safe frontend variables remain in
`apps/web/.env.local`; server secrets must never be copied there.

`RUNTIME_PROFILE` selects `local`, `live_validation`, `staging`, or `production`.
`live_validation` requires and selects `LIVE_VALIDATION_DATABASE_URL`; other profiles use
`DATABASE_URL`. Workers additionally require database, Redis, and YouTube configuration and fail
before consuming messages if any is absent.

## Process identity

API, worker, and scheduler log the selected profile, database host/port/name, Redis host/port/db,
and a deterministic fingerprint. Credentials and URL query strings are excluded. The admin
discovery status endpoint exposes the same safe fields. Stop startup if fingerprints differ.
Provider HTTP client loggers run at WARNING or above because INFO request URLs can contain API
keys in query parameters.

## Startup

`scripts/dev-runtime.sh` is the canonical local entry point. It starts Web, API, Dramatiq workers,
and APScheduler as one process group and terminates children together.
Local Next.js development and production builds use webpack because Turbopack's persistence
database is unreliable on the project's external filesystem.

## Discovery failure terminality

Every discovery message has an envelope containing `discovery_run_id`, optional `topic_run_id`,
and `query_id`, plus a nested business payload. Permanent validation failures and exhausted retries
finalize the child run and recompute the parent batch, giving frontend polling a terminal state.
Downstream metadata, comments, relevance, extraction, and normalization messages retain
`topic_run_id`. Their exhausted-retry callback finalizes the separate intelligence status with a
safe error while preserving already persisted RAW and FACT data. No additional environment file or
secret is introduced by this orchestration.
