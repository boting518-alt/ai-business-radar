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

- `search.list`: 1 unit per request in a dedicated default 100-calls/day Search Queries bucket.
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

## Discovery pipeline

TASK-011 implements admin-triggered discovery from enabled `search_queries` whose `discovery_mode` is `discovery`. Each attempt creates a `collection_runs` record, transitions it through `pending`/`running`, and finalizes it as `completed`, `partial`, or `failed`. `last_run_at` is set when a valid external attempt starts; disabled or monitoring queries do not change it.

The service uses short database transactions before and after network calls. It never holds a transaction open while awaiting YouTube. Search results enter `youtube_discovery_items`, an internal RAW staging table, instead of polluting canonical channel/video records with incomplete search snippets. TASK-012 owns conversion of pending staging items into canonical metadata.

Pagination is bounded by `max_pages` (1–5), optional `max_results` (up to 250), missing continuation tokens, and the configured per-run estimated quota budget. Since Google's June 2026 quota change, search cost is counted as 1 unit per logical page request against a dedicated default 100-calls/day Search Queries bucket. Items are deduplicated by video ID within and across pages and by a database uniqueness constraint within each run. `items_discovered` means unique items accepted by that run.

Zero results complete normally. A YouTube failure before any completed page marks the run failed; a failure after progress marks it partial. Reaching the quota budget with more pages available also produces a partial run after progress. Early stops preserve `next_page_token` for inspection, but automatic resume and scheduling are intentionally deferred.

## Metadata collection

TASK-012 converts pending discovery staging rows into canonical RAW records. The collector atomically claims rows by changing `pending` to `processing` under `FOR UPDATE SKIP LOCKED`, commits that short transaction, and only then calls YouTube. Selection is deterministic by `discovered_at, id`; an optional discovery run filter can target one prior run. Worker scheduling and automatic recovery of abandoned `processing` claims remain deferred to TASK-014.

`videos.list` is authoritative for video metadata; discovery snippets are never copied into canonical videos. Returned channel IDs are resolved through `channels.list`, channels are upserted before videos, and missing channel metadata causes the affected staging rows to fail rather than creating fabricated channels or FK-invalid videos. Channel `first_seen_at` and existing `channel_type` classifications are preserved. Video `first_seen_at` and existing downstream `processing_status` are also preserved; newly inserted videos use `new`, meaning canonical metadata is available but AI processing has not started.

When enabled, one append-only `video_snapshots` observation is created per unique successfully fetched video using a consistent batch timestamp. Canonical channel/video uniqueness is based on YouTube external IDs, and `(video_id, captured_at)` conflicts are ignored, making persistence safe if the same batch timestamp is retried. A later collection at a new timestamp appends a new observation.

Missing/private/deleted videos are recorded as `video_unavailable`; unresolved channels use `channel_unavailable`. Successful staging rows store their canonical video ID and processing timestamp. Mixed success produces a `partial` metadata collection run, complete success (including no eligible rows) produces `completed`, and an external request failure with no persisted successes produces `failed` while releasing claimed rows back to `pending`. Provider payloads and exception text are not persisted.

## Comment collection

TASK-013 collects only top-level public comments for canonical videos through the official `commentThreads.list` endpoint. Replies are not expanded; only the thread's reply count is retained. Every run is bounded by video count, pages per video, comments per video, and an estimated quota budget (default 500 units). Each run starts at the first page and does not persist a cursor.

For initial discovery and analysis, `order=relevance` with one or two pages samples higher-value discussion. For monitoring recent demand, `order=time` samples recent comments. Both modes are deliberately bounded; adaptive sampling is deferred. The service selects eligible videos with fewest stored comments first, then newer discoveries, excluding canonical videos marked `ignored` or `failed`. Explicit IDs must all resolve to eligible canonical videos.

Comments are idempotently upserted by YouTube comment ID. Source refreshes update plain text, like/reply counts, source edit time, and the database row timestamp while preserving `first_seen_at`, `is_question`, and `author_hash`. No author display name is requested or stored, and no hash is fabricated. `source_updated_at` represents YouTube's edit timestamp; `updated_at` remains application row-maintenance time.

A disabled-comments response is recorded as a safe video-level skip and never changes the canonical video's status. A failed video alongside successful or skipped videos makes the run partial; all external failures make it failed. A valid video with zero comments is completed successfully. Provider messages and payloads are not persisted. RAW comments remain internal until a later, explicitly scoped AI comment-mining task creates traceable FACT records.
