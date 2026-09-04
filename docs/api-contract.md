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

The API verifies the JWT locally, resolves `sub` through `user_profiles.auth_user_id`, and takes the `user`/`admin` authorization role from that database profile. JWT role claims are not authoritative. Missing, malformed, invalid, or expired tokens return HTTP 401. A valid token without an application profile, or an authenticated user lacking the required role, returns HTTP 403.

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

Roles remain the frozen `user` and `admin` roles described in ADR-003.

## Pagination direction

The choice between cursor pagination and limit/offset remains deferred until the first collection endpoint contract is defined. Health endpoints are not paginated.

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

Planned:

- Radar queries
- Opportunity search, summaries, and details
- Signal feed
- User watchlists
- Administrative review

No planned endpoint path or payload is frozen by this status list.
