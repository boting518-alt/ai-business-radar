# YouTube Ingestion Boundary v0.1

Status: Accepted for TASK-010
Version: 0.1

## Official API boundary

The v0.1 adapter uses only the official YouTube Data API v3 over HTTPS with a server-side API key. Browser automation, page scraping, yt-dlp, undocumented APIs, and unofficial transcript endpoints are prohibited. The adapter is infrastructure code and does not depend on repositories, services, or workers.

## Supported endpoints and DTOs

| Client method | Official endpoint | Returned data |
| --- | --- | --- |
| `search_videos` | `search.list` | Video/channel IDs, snippet metadata, timestamps, thumbnail, explicit page tokens |
| `get_videos` | `videos.list` | Canonical snippet, duration, optional statistics, language, official caption flag |
| `get_channels` | `channels.list` | Channel snippet and optional public statistics |
| `get_comment_threads` | `commentThreads.list` | Top-level comment text/timestamps and optional like/reply counts |

The Pydantic DTOs live inside the YouTube adapter. They describe external API data and are deliberately separate from shared business-domain schemas. Missing public statistics remain `None`; hidden subscriber counts are never represented as zero. Durations are converted from ISO 8601 to seconds, and timestamps remain timezone-aware.

## Pagination and batching

Search and comment methods return exactly one requested page with continuation tokens. They never auto-exhaust result pages. Future orchestration chooses page budgets. Video and channel ID reads batch at the official maximum of 50 IDs per request; batching is not pagination.

## Quota awareness

The adapter exposes local published-cost metadata, not account quota remaining:

- `search.list`: 100 units and therefore high cost.
- `videos.list`, `channels.list`, `commentThreads.list`: 1 unit per request.

TASK-011 owns collection-run quota budgets and decisions about how many search pages to request.

## Retry and errors

HTTP 429 and 500/502/503/504 responses receive bounded exponential backoff with jitter. `Retry-After` takes precedence when valid. Normal validation/authentication 4xx responses are not retried. Authentication, quota exhaustion, rate limiting, not-found responses, generic API failures, and malformed successful responses map to distinct internal exceptions. Error construction omits request URLs and redacts the configured API key.

## Known limitations

- Only public API-key-compatible data is supported; OAuth-only/private resources are excluded.
- Only top-level comments are parsed; replies are not expanded.
- Search snippets are discovery hints, not canonical video statistics.
- The API does not reveal real quota remaining, so costs are estimates only.
- Deleted, disabled-comment, region-restricted, or unavailable resources may be omitted or rejected by YouTube.

## Transcript policy

v0.1 does not depend on unofficial bulk transcript scraping. Transcript ingestion remains optional and requires a later, explicit authorization and an official or legally available source design.

## Discovery versus monitoring

Discovery searches for unknown videos and opportunities and is quota-sensitive. Monitoring refreshes already known resource IDs using lower-cost metadata endpoints. The client supplies primitives for both but makes no scheduling or persistence decisions. TASK-011 will implement discovery orchestration, managed queries, page/quota budgeting, and collection-run behavior.
