# MVP Release Readiness v0.1

## Executive status

**MVP STATUS: READY WITH KNOWN GAPS.** The repository is ready for an isolated local demonstration.
It is not yet a production deployment approval because real YouTube/OpenAI provider calls and the
target Supabase/Vercel/container topology were not exercised in this environment.

## Completed capabilities

The tested product path covers official YouTube collection adapters, RAW persistence, AI relevance
and extraction with fake providers, FACT signals, opportunity normalization, deterministic trend
aggregation and scoring, transactional human review, Radar and opportunity reads, Signals, and
user-owned Watchlists. Demo data is synthetic and explicitly labeled.

## Test summary

- PostgreSQL 16.15: all 12 migrations applied from an empty database; demo seed applied successfully;
  88 public indexes observed.
- API: 148 tests passed against an isolated temporary PostgreSQL instance, including all Watchlist,
  Review Workflow, RLS, auth, YouTube, AI pipeline, Radar, scoring, and migration integration tests.
- Shared schemas: 44 tests passed; Ruff and lock consistency passed.
- Workers: 16 tests passed; scheduler bounds, queue names, actors, and stale recovery passed.
- Frontend: 60 tests passed; typecheck, ESLint, frozen install, and production build passed.
- Dependencies: `pnpm audit --audit-level high` and `pip-audit` reported no known
  vulnerabilities after upgrading the development-only pytest dependency to 9.1.1.
- Redis 8.10.1: real broker enqueue verified for discovery, metadata, comments, and relevance queues;
  an isolated Dramatiq worker consumed a real Redis message.

Critical frontend journeys are covered through deterministic component/API tests rather than
Playwright. Playwright was not introduced because real Supabase browser authentication is not
available locally and a mocked browser layer would duplicate the existing component fixtures.

## Live integrations

- OpenAI: **NOT RUN — `OPENAI_API_KEY` unavailable.** Model, request, and token usage are therefore
  not claimed.
- YouTube Data API: **NOT RUN — `YOUTUBE_API_KEY` unavailable.** No live quota was consumed.
- Redis/Dramatiq: run successfully against an isolated localhost instance.
- Supabase Auth/PostgreSQL and Vercel/container deployment: not exercised against target managed
  services.
- A bounded localhost-only live-validation CLI is available in
  `docs/local-live-validation.md`; no real provider call is claimed until the user explicitly runs
  its non-dry commands and reviews the generated report.

## Security and privacy review

No private-key, OpenAI-key, or YouTube-key patterns were found in tracked files. Frontend source does
not reference server-only database, Redis, service-role, JWT-secret, YouTube, or OpenAI environment
variables. Auth tests cover missing, invalid, expired, profile-less, user, and admin boundaries.
Actual PostgreSQL RLS tests confirm RAW/review restrictions, personal Watchlist ownership, and no
self-role escalation. Signal and evidence responses exclude comment author identity and raw AI
output.

## Known limitations and deployment gaps

- Live provider structured-output compatibility and official YouTube quota behavior remain
  environment-specific gaps.
- Production container definitions, CI release gates, managed Redis connectivity, Supabase migration
  rehearsal, observability, backup/restore, and recovery procedures are not yet implemented.
- Dramatiq provides at-least-once delivery but no durable job-status API or worker heartbeat.
- Scheduler overlap prevention is process-local; production needs single-scheduler ownership.
- Signals pagination has no total; Watchlist v0.1 exposes one logical personal list.
- API tests retain two upstream Starlette/httpx and AnyIO deprecation warnings. Python dependency
  audit skips the two unpublished local workspace packages themselves; their declared third-party
  dependencies were audited. No unrelated major dependency upgrade was attempted.

## Go/no-go recommendation

**GO for local MVP demo and continued staging work. NO-GO for production traffic** until live
YouTube/OpenAI smoke tests, managed Supabase Auth/RLS rehearsal, deployment artifacts, secrets
management, observability, and rollback/backup procedures pass in a staging environment.

## Recommended post-MVP backlog

1. Add a staging deployment pipeline with container images, CI gates, migrations, and rollback.
2. Run minimal official YouTube and OpenAI provider contract tests with budget limits.
3. Add durable job monitoring, worker heartbeat, queue depth alerts, and scheduler leadership.
4. Export checked-in OpenAPI and generate TypeScript response types.
5. Add Playwright against a local/staging Supabase Auth stack.
6. Consider taxonomy endpoints, pgvector candidate retrieval, charts, and multi-list Watchlists.
7. Keep external evidence sources, notifications, billing, and teams in the explicit post-MVP scope.
