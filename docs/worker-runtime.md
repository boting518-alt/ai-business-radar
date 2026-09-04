# Collection Worker Runtime v0.1

## Architecture and queues

The collection runtime is one Python project under `workers/`, using Dramatiq with Redis. It depends on the API application's services and infrastructure; the API never imports the worker package. Four fixed queues keep ownership explicit:

| Queue | Actor responsibility |
| --- | --- |
| `youtube_discovery` | Invoke managed-query discovery |
| `youtube_metadata` | Invoke staging-to-canonical metadata collection |
| `youtube_comments` | Invoke bounded top-level comment collection |
| `maintenance` | Recover stale metadata staging claims |

Actors carry only JSON-safe IDs, numbers, booleans, strings, and ISO timestamps. They construct engines, sessions, and YouTube clients during execution and release them afterward. Business orchestration remains in application services.

## Delivery and retries

Dramatiq is at-least-once. Metadata/video/comment upserts and staging claims provide application-level retry safety; a repeated discovery delivery creates a separate observable run by design. Actors allow two job-level retries with backoff for unexpected infrastructure failures. Validation, missing/disabled managed queries, and invalid discovery mode are permanent and are logged without retry. A service result of `partial` is a successful actor execution and is not retried wholesale. YouTubeClient retains its separate bounded HTTP retry policy.

Transport `job_id` is the Dramatiq message ID returned when a job is queued. `collection_run_id` is created only when the actor starts the application service. No durable queue-status API or jobs table exists; `collection_runs` becomes the operational audit record after execution begins.

## Stale recovery

Metadata claims record `claimed_at`. The maintenance actor resets only `processing` rows older than `YOUTUBE_STAGING_CLAIM_TIMEOUT_MINUTES` to `pending`, clears `claimed_at`, and applies a configurable recovery batch limit. Fresh, processed, and terminal failed rows are untouched. v0.1 reports stale running collection runs through normal operational inspection but does not rewrite them automatically because a safe last-progress timestamp is not available.

## Scheduling and backpressure

APScheduler provides four interval hooks: discovery, metadata, comments, and stale recovery. Every interval and batch size is configuration-driven. Discovery selects only enabled `discovery` queries and applies `YOUTUBE_DISCOVERY_SCHEDULE_BATCH_SIZE`; metadata and comments reuse their bounded service limits. `max_instances=1` prevents overlapping scheduler callbacks in one scheduler process. This is intentionally not a workflow engine or sophisticated queue-pressure controller.

Suggested defaults are low-frequency discovery (360 minutes), metadata every 30 minutes, comments every 120 minutes, and stale recovery every 15 minutes. They are operational defaults, not frozen product policy.

## Startup

From `workers/`:

```bash
uv sync --check
uv run dramatiq ai_business_radar_workers.worker
uv run python -m ai_business_radar_workers.scheduler
```

Both processes require valid `REDIS_URL`, `DATABASE_URL`, and `YOUTUBE_API_KEY`. Broker construction is explicit and does not silently fall back to an in-memory production broker. Startup does not provide a distributed heartbeat; dependency failures surface when the broker starts or a job constructs its application dependencies.

The existing synchronous admin collection endpoints remain development/debug operations. The `/jobs` variants return `202` after Redis accepts the message. Redis failures return a safe `503`; queued transport state is not presented as durable execution state.

## AI relevance actor

TASK-015 adds the manually triggered `run_relevance_filter` actor on the `ai_relevance` queue.
It constructs the configured AI provider and delegates all selection, inference, audit, reuse, and
video-state behavior to `VideoRelevanceService`. It is intentionally absent from the scheduler.
AI configuration and missing immutable prompts are permanent job errors; unexpected infrastructure
errors retain the actor's bounded retry policy. Provider retries remain separately bounded by
`AI_MAX_RETRIES` to avoid multiplying retries.

TASK-016 adds `run_signal_extraction` on the shared-capacity `ai_extraction` queue. It accepts only
primitive bounded batch arguments and delegates to `BusinessSignalExtractionService`; it does not
duplicate prompt, validation, audit, or persistence behavior. It is manual-only in v0.1 and uses
`AI_MODEL_SIGNAL_EXTRACTION`.

TASK-017 adds `run_comment_pain_mining` to the same `ai_extraction` queue. The actor accepts only
bounded primitive batch arguments, constructs `AI_MODEL_COMMENT_PAIN_MINING` dependencies, and
delegates to `CommentPainMiningService`. It is intentionally absent from the scheduler.
## Opportunity scoring

`run_opportunity_scoring` runs on the non-AI `aggregation` queue and delegates to the deterministic
scoring service. A daily bounded scoring batch is scheduled after trend aggregation using
`OPPORTUNITY_SCORING_SCHEDULE_DELAY_MINUTES` (default 30) and
`OPPORTUNITY_SCORING_BATCH_SIZE` (default 100). It does not trigger trend aggregation or invoke an
LLM.
