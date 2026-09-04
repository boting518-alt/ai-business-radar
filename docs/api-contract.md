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

Reports application-level readiness for TASK-007. PostgreSQL, Supabase, Redis, YouTube, and AI-provider readiness checks are intentionally absent until those integrations exist.

Successful response, HTTP 200:

```json
{
  "status": "ready"
}
```

Future tasks may extend readiness with dependency checks without changing the meaning of the liveness endpoint.

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

Future protected endpoints will accept a Bearer token issued by Supabase Auth. FastAPI will perform authoritative authentication and role enforcement. TASK-007 does not verify tokens, create fake users, or expose admin routes.

Roles remain the frozen `user` and `admin` roles described in ADR-003.

## Pagination direction

The choice between cursor pagination and limit/offset remains deferred until the first collection endpoint contract is defined. Health endpoints are not paginated.

## CORS

Allowed origins are configured through `CORS_ORIGINS` as a comma-separated string or JSON-compatible string list. The development default is `http://localhost:3000`. Unrestricted `*` is rejected when `APP_ENV=production`.

## Endpoint Implementation Status

Implemented:

- `GET /api/v1/health`
- `GET /api/v1/health/ready`

Planned:

- Radar queries
- Opportunity search, summaries, and details
- Signal feed
- User watchlists
- Administrative review

No planned endpoint path or payload is frozen by this status list.
