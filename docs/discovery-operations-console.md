# Discovery Operations Console v0.1

`/admin/discovery` is the admin-only control plane for official YouTube discovery. A Discovery
Topic represents one research theme; each child Discovery Query is one literal YouTube search.
Query text remains user-authored, while `query_group` and `discovery_mode` remain `discovery`.

Topics persist status (`active`, `paused`, `archived`), a bounded schedule preset (`manual`, `6h`,
`12h`, `daily`, `weekly`), and defaults for videos, pages, and comments. Query overrides are
nullable and inherit topic defaults. Limits are 100 videos, 5 pages (the existing service ceiling),
and 100 comments per video. Archived topics and disabled queries are not scheduled.

Run Now creates a durable pending `collection_runs` row, then enqueues the existing
`run_youtube_discovery` actor. A partial unique index prevents a second pending/running run for the
same query. The actor passes the pre-created run ID into `YouTubeDiscoveryService`, which records
running and terminal state plus auditable item and estimated quota metrics. Safe error categories
are shown; raw provider responses and secrets are not exposed. Discovery currently ends after RAW
discovery; existing separately scheduled metadata, comment, relevance, extraction, normalization,
translation, trend, and scoring workers continue downstream.

The existing APScheduler interval remains the only scheduler. Each tick preserves legacy ungrouped
queries and also polls due active topics, queues enabled queries, and advances topic `next_run_at`.
Manual topics have no next run. One provider failure does not pause future scheduling. Actor retries
remain bounded at two.

The API is under `/api/v1/admin/discovery`: topic list/create/detail/update, pause/resume/archive,
duplicate, topic/query Run Now, paged run history, and safe system configuration status. All routes
use the existing admin dependency; the new topic table also has admin-only RLS. Worker liveness is
reported as `unknown` because no reliable heartbeat exists.

Local operators should start PostgreSQL, Redis, the Dramatiq worker, and the existing scheduler;
apply migration `0018_discovery_operations.sql`; then create a paused/manual low-limit topic before
running a single query. TASK-044 local validation completed one official API page with five unique
videos and one estimated quota unit; the immediate duplicate was rejected. The shared scheduler was
not invoked live because legacy enabled queries would also be queued, so due-topic scheduling was
validated in isolation and the validation topic was left paused/manual. v0.1 does not provide arbitrary cron, non-YouTube sources, exact provider
quota accounting, downstream per-run attribution, worker heartbeat, or billing.
