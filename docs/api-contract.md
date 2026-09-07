# YouTube AI Business Radar — API Contract Baseline v0.1

Status: Frozen for TASK-007
Version: 0.1
Last updated: 2026-09-04

## Scope

FastAPI owns the application API. This document freezes only the conventions and health endpoints implemented by the backend skeleton. Radar, opportunity, signal, watchlist, and admin-review resource contracts remain planned and must not be inferred from placeholders here.

## General conventions

- Base path: `/api/v1`
- Response media type: `application/json`
- API style: REST
- Request correlation header: `X-Request-ID`
- API version: application metadata version `0.1.0`

GraphQL and a public third-party API are not part of v0.1.

## Request correlation ID

Clients may supply `X-Request-ID` using 1–128 characters from letters, digits, `.`, `_`, `:`, and `-`. A safe supplied value is reused. If the header is absent or unsafe, the API generates a UUID.

The response includes `X-Request-ID`, and request-scoped application code can access the same value. This provides correlation only; it is not a distributed tracing system.

## Health endpoints

### `GET /api/v1/health`

Reports application identity and liveness. It does not query external dependencies.

Successful response, HTTP 200:

```json
{
  "status": "ok",
  "service": "api",
  "version": "0.1.0"
}
```

### `GET /api/v1/health/ready`

Reports application and PostgreSQL readiness. It does not check Supabase Auth, Redis, YouTube, or the AI provider.

Successful response, HTTP 200:

```json
{
  "status": "ready",
  "dependencies": {
    "database": "ready"
  }
}
```

When `DATABASE_URL` is absent (supported for development and liveness-only startup), HTTP 200 uses `database: not_configured`. When configured PostgreSQL is unreachable, HTTP 503 uses `status: not_ready` and `database: not_ready`. Future tasks may add dependency keys without changing liveness semantics.

## Error response direction

Future application-owned errors should use this envelope:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "request_id": "string-or-null"
  }
}
```

TASK-007 defines the typed envelope but does not add an exception hierarchy or replace FastAPI’s default 404/validation responses. Exact error codes and exception mapping remain deferred until business endpoints exist.

## Authentication direction

Protected endpoints require a Supabase access token:

```http
Authorization: Bearer <token>
```

The API verifies the JWT locally using the hosted project's JWKS for `RS256`/`ES256`, with optional
legacy `HS256` secret compatibility. It validates the configured issuer and audience, resolves `sub`
through `user_profiles.auth_user_id`, and takes the `user`/`admin` authorization role from that
database profile. JWT role claims are not authoritative. Missing, malformed, invalid, expired, or
unknown-key tokens return HTTP 401. A valid token without an application profile, or an
authenticated user lacking the required role, returns HTTP 403.

### `GET /api/v1/auth/me`

Returns the resolved authenticated user:

```json
{
  "auth_user_id": "uuid",
  "user_profile_id": "uuid",
  "role": "user",
  "email": "analyst@example.com"
}
```

Administrative routes use the same bearer-token boundary plus an application `admin` role check. `GET /api/v1/admin/health` is the v0.1 authorization verification endpoint; review business endpoints remain undefined.

### `POST /api/v1/admin/youtube/discovery`

Admin-only manual trigger for one bounded managed-query discovery run. The request accepts `search_query_id`, `max_pages` (1–5), optional `max_results` (1–250), optional timezone-aware `published_after`, and `order` (`date`, `relevance`, or `viewCount`). The response reports collection-run identity, requested/completed pages, unique staged discoveries, estimated quota units, continuation token, timestamps, and final status. It never returns raw YouTube JSON.

Missing queries return 404. Disabled or monitoring-mode queries return 409. External YouTube failures are converted into safe failed/partial discovery results rather than exposing provider exceptions.

### `POST /api/v1/admin/youtube/metadata`

Admin-only manual trigger for one bounded metadata collection. The request accepts optional `collection_run_id`, `limit` (1–250, default 50), and `include_snapshots` (default true). It claims pending discovery rows and returns a typed summary containing claim, success/failure, video/channel request and return counts, snapshots created, estimated quota units, timestamps, reason, and final collection-run status. External provider details and raw payloads are never returned.

### `POST /api/v1/admin/youtube/comments`

Admin-only manual trigger for bounded top-level comment collection. The request accepts optional canonical `video_ids`, `limit_videos` (1–100), `max_pages_per_video` (1–5), `max_comments_per_video` (1–500), and `order` (`relevance` or `time`). The response reports video/page/comment counts, estimated quota units, timestamps, safe reason, and final run status. Missing or ineligible explicit canonical video IDs return 404.

### Asynchronous collection jobs

`POST /api/v1/admin/youtube/discovery/jobs`, `/metadata/jobs`, and `/comments/jobs` accept the corresponding synchronous endpoint request model and return `202` with `job_id`, fixed `queue`, and `status: queued`. The job ID identifies the Dramatiq transport message; a collection run ID exists only after worker execution starts. Redis enqueue failure returns a safe 503. No durable job-status endpoint is defined in v0.1.

Roles remain the frozen `user` and `admin` roles described in ADR-003.

### AI relevance filter

`POST /api/v1/admin/ai/relevance/{video_id}` evaluates one canonical video and accepts
`force` (default false). `POST /api/v1/admin/ai/relevance` evaluates a bounded oldest-first
batch of new videos and accepts `limit` (1–100) and `force`. Responses expose extraction IDs,
safe status, relevance, score, and reuse information, but never raw provider output.

`POST /api/v1/admin/ai/relevance/jobs` enqueues the same batch request on `ai_relevance` and
returns HTTP 202. All three endpoints are admin-only. Missing AI credentials or model/provider
configuration returns a safe 503 without preventing application startup.

### Business signal extraction

`POST /api/v1/admin/ai/signals/{video_id}` extracts signals from one eligible canonical video and
accepts `force` (default false). `POST /api/v1/admin/ai/signals` processes an oldest-first bounded
batch of queued videos with `limit` (1–100). Responses include only safe extraction identity,
status, reuse, and signal counts. `POST /api/v1/admin/ai/signals/jobs` enqueues the batch on
`ai_extraction` and returns HTTP 202. All endpoints are admin-only; missing configuration returns
503, and raw provider output remains internal.

### Comment pain mining

`POST /api/v1/admin/ai/comment-pain/{comment_id}` mines one canonical comment with optional
`force`. `POST /api/v1/admin/ai/comment-pain` processes an oldest-first bounded batch with `limit`
from 1–200 (default 50). `POST /api/v1/admin/ai/comment-pain/jobs` enqueues the batch on
`ai_extraction` and returns HTTP 202. Responses expose only safe audit IDs, status, mined/reused
flags, signal counts, and empty-result counts. All routes are admin-only.

### Opportunity normalization

`POST /api/v1/admin/ai/opportunities/normalize/{signal_id}` normalizes one signal and accepts
optional `force`. `POST /api/v1/admin/ai/opportunities/normalize` processes review signals with
`limit` 1–200 (default 50). `POST /api/v1/admin/ai/opportunities/normalize/jobs` enqueues the batch
on `ai_extraction` and returns HTTP 202. Responses expose safe extraction, action, opportunity, and
review-task IDs but never prompts, provider raw output, or review context. All routes are admin-only.

### Trend aggregation

`POST /api/v1/admin/trends/{opportunity_id}` calculates one `7d`, `30d`, or `90d` trend snapshot.
It accepts an optional timezone-aware `period_end` and `force`; omitted ends use the current UTC hour
boundary. `POST /api/v1/admin/trends` processes up to 500 eligible opportunities (default 100).
`POST /api/v1/admin/trends/jobs` submits the batch to the non-AI `aggregation` queue. All routes are
admin-only and return persisted core metrics, the exact window, version, snapshot ID, and reuse flag.

### Opportunity scoring

`POST /api/v1/admin/scoring/{opportunity_id}` calculates one deterministic `score-v001` result and
accepts optional `force`. `POST /api/v1/admin/scoring` processes up to 500 eligible opportunities
(default 100). `POST /api/v1/admin/scoring/jobs` enqueues that bounded batch on `aggregation`.
Admin responses expose component, Confidence, Hype Risk, input hash, and reproducibility snapshot;
TASK-022 remains responsible for public/current-score reads.

### Administrative review workflow

`GET /api/v1/admin/reviews` lists review tasks ordered by priority descending, then creation time
and ID ascending. It supports `status`, `review_type`, `assigned_to`, exact `priority`, `offset`,
and bounded `limit` (1–200). `GET /api/v1/admin/reviews/{review_task_id}` returns one task.

`POST /api/v1/admin/reviews/{review_task_id}/claim` atomically claims a pending task for the current
admin. `POST /api/v1/admin/reviews/{review_task_id}/decision` accepts `ReviewDecisionRequest` and
executes the validated domain decision transactionally. Missing tasks/targets return 404,
assignment or lifecycle conflicts return 409, and invalid decision or merge semantics return 422.
All review routes are admin-only; no release endpoint is included in v0.1.

`GET /api/v1/admin/opportunities/{opportunity_id}/activation-readiness` returns six deterministic
checks, an advisory recommendation, duplicate candidates, and informational score/trend metrics.
`POST /api/v1/admin/opportunities/{opportunity_id}/activation-review` creates or reuses an open
`opportunity_activation` task for an eligible candidate with active supporting evidence. Neither
endpoint publishes. Publish/Defer/Invalid continue through the existing review decision endpoint
as `approve`/`defer`/`reject`, with decision-time hard-check revalidation.

The task detail response may enrich persisted `context` with a read-only presentation projection:
safe signal evidence plus bounded source, candidate, and canonical opportunity summaries. This
projection is resolved from current records, is never persisted back into workflow context, and is
not trusted for decisions. It excludes raw model output, provider data, input hashes, extraction
errors, scoring internals, and arbitrary database fields.

### Product Radar and opportunity reads

All product query routes require an authenticated application user and explicitly expose only
`active` opportunities and `active` signals. Invisible IDs and slugs return the same safe 404.
GET requests never trigger AI, normalization, trend aggregation, or scoring.

`GET /api/v1/radar` accepts `window_type` (`7d`, `30d`, `90d`), sort (`score`, `momentum`,
`confidence`, `hype`, `recent`), direction, offset/limit, simple `q`, classification filters,
score/confidence ranges, `hype_max`, and `detected_after`. Repeated or comma-separated values are
OR within one field; different fields are AND. Default score ranking excludes active opportunities
without `score-v001`; other sorts keep missing values last. Latest score is selected by
`calculated_at`; latest requested `trend-v001` by `period_end`. Missing display trend is null.
Ordering is deterministic with activity and ID tie-breaks. Hype direction is literal: ascending
places lower risk first.

`GET /api/v1/opportunities` is the active catalog and defaults to recent sorting while sharing the
same filters and compact response model. `GET /api/v1/opportunities/{id-or-slug}` returns identity,
business fields, persisted current score and seven components, latest 7d/30d/90d trends, compact
evidence counts, timestamps, and whether the opportunity occurs in any watchlist owned by the
current user. It does not expose score `inputs_snapshot`.

`GET /api/v1/opportunities/{id-or-slug}/trends` and `/scores` return bounded chronological history.
The former optionally filters by window; the latter omits reproducibility internals.
`GET /api/v1/opportunities/{id-or-slug}/evidence` returns bounded safe evidence summaries and
optional video ID/title, never comment author data or AI output.

`GET /api/v1/signals` returns only active signals and supports signal type, industry, customer,
active-opportunity, observed-after, and offset/limit filters. Source context is limited to video
title, source type, and active opportunity IDs; comment author identity is never returned.

`GET /api/v1/watchlist` returns the current user's logical personal watchlist with active
opportunity identity, current `score-v001` intelligence, latest 7-day `trend-v001` momentum, and
membership time. `POST /api/v1/watchlist/items/{opportunity_id}` adds a product-visible opportunity
and returns the existing membership on duplicate requests. `DELETE` on the same path removes the
membership and succeeds safely when it is already absent. The first valid add creates a personal
list named `Watchlist` only when the user has no list. Ownership is derived exclusively from the
authenticated user; no owner identifier is accepted. List reads use set queries and never expose
another user's items.

## Pagination

Product list, signal, evidence, and history reads use bounded `offset`/`limit` pagination for the
MVP dataset. Radar and catalog ordering includes deterministic tie-breaks, so repeated reads over
unchanged data are stable. Health endpoints are not paginated.

## CORS

Allowed origins are configured through `CORS_ORIGINS` as a comma-separated string or JSON-compatible string list. The development default is `http://localhost:3000`. Unrestricted `*` is rejected when `APP_ENV=production`.

## Endpoint Implementation Status

Implemented:

- `GET /api/v1/health`
- `GET /api/v1/health/ready`
- `GET /api/v1/auth/me`
- `GET /api/v1/admin/health`
- `POST /api/v1/admin/youtube/discovery`
- `POST /api/v1/admin/youtube/metadata`
- `POST /api/v1/admin/youtube/comments`
- `POST /api/v1/admin/youtube/discovery/jobs`
- `POST /api/v1/admin/youtube/metadata/jobs`
- `POST /api/v1/admin/youtube/comments/jobs`
- `POST /api/v1/admin/ai/relevance/{video_id}`
- `POST /api/v1/admin/ai/relevance`
- `POST /api/v1/admin/ai/relevance/jobs`
- `POST /api/v1/admin/ai/signals/{video_id}`
- `POST /api/v1/admin/ai/signals`
- `POST /api/v1/admin/ai/signals/jobs`
- `POST /api/v1/admin/ai/comment-pain/{comment_id}`
- `POST /api/v1/admin/ai/comment-pain`
- `POST /api/v1/admin/ai/comment-pain/jobs`
- `POST /api/v1/admin/ai/opportunities/normalize/{signal_id}`
- `POST /api/v1/admin/ai/opportunities/normalize`
- `POST /api/v1/admin/ai/opportunities/normalize/jobs`
- `POST /api/v1/admin/trends/{opportunity_id}`
- `POST /api/v1/admin/trends`
- `POST /api/v1/admin/trends/jobs`
- `POST /api/v1/admin/scoring/{opportunity_id}`
- `POST /api/v1/admin/scoring`
- `POST /api/v1/admin/scoring/jobs`
- `GET /api/v1/admin/reviews`
- `GET /api/v1/admin/reviews/{review_task_id}`
- `POST /api/v1/admin/reviews/{review_task_id}/claim`
- `POST /api/v1/admin/reviews/{review_task_id}/decision`
- `GET /api/v1/radar`
- `GET /api/v1/opportunities`
- `GET /api/v1/opportunities/{id-or-slug}`
- `GET /api/v1/opportunities/{id-or-slug}/trends`
- `GET /api/v1/opportunities/{id-or-slug}/scores`
- `GET /api/v1/opportunities/{id-or-slug}/evidence`
- `GET /api/v1/signals`
- `GET /api/v1/watchlist`
- `POST /api/v1/watchlist/items/{opportunity_id}`
- `DELETE /api/v1/watchlist/items/{opportunity_id}`

Planned:

- None in the frozen v0.1 product API

No planned endpoint path or payload is frozen by this status list.

## Intelligence locale projection

`GET /radar`, `GET /opportunities`, `GET /opportunities/{id-or-slug}`, and `GET /signals` accept
`locale=zh-CN|en-US` and default to canonical `en-US`. Missing or stale projections fall back to
canonical content without failing the request. These reads never generate a translation.

Signal items additionally return original statement/evidence, localization flags, original video
title, channel name, canonical enums, and visible linked opportunity identity (`id`, `slug`, `name`).
Translated evidence never replaces `original_evidence_text`. Candidate or rejected opportunities
are excluded from linked opportunity projections and Radar responses.
