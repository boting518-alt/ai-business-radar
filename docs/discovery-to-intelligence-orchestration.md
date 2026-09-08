# Discovery-to-Intelligence Orchestration v0.1

## Product contract

`Run Now` means running the bounded Topic queries and starting intelligence production for the
resulting eligible YouTube videos. It never means stopping after raw search-result persistence.
Manual Topic runs, scheduled Topic runs, and direct Query runs all create a `topic_run_id` and use
the same asynchronous chain.

## Layer and stage boundaries

The chain preserves the existing data layers:

1. RAW: query-scoped `youtube_discovery_items` with all Topic/Query provenance.
2. FACT: canonical video/channel metadata, metadata snapshots, and top-level comments.
3. INTELLIGENCE: Relevance v001, Signal Extractor v003, Comment Pain v001, and Opportunity
   Normalizer v001.

Each stage remains a separate Dramatiq message on its existing queue. AI work starts only after
canonical FACT rows exist. Normalization produces candidates or review decisions and never
publishes an Opportunity or bypasses human review.

## Eligibility, deduplication, and reuse

Discovery items retain query provenance but are grouped by canonical YouTube video identity for
processing. Existing canonical videos are linked without fetching their metadata again. New or
missing canonical videos are sent to metadata in bounded chunks. Comment collection selects new
videos or known videos with no stored comments; `max_comments_per_video=0` skips it. Relevance,
signal, pain, and normalization services receive explicit canonical IDs and retain their existing
prompt/model/input-hash reuse rules. Thus rediscovery can resume a missing stage without paying for
an unchanged immutable AI extraction.

## Durable status and provenance

`discovery_topic_runs.status` remains the TASK-044B child-query rollup. Separate fields
`intelligence_status`, `intelligence_metrics`, start/completion timestamps, and a safe error summary
track downstream work without changing discovery correctness. Messages propagate `topic_run_id`;
discovery children also retain `discovery_run_id`, Topic, Query, and source-video provenance.

The auditable metrics are discovery results, unique videos, new videos, metadata completed,
comments completed, relevance completed, relevant/irrelevant videos, newly created Signals,
newly created Opportunity candidates, and failed stage count. Reused records are not reported as
newly created. Discovery quota remains the existing exact estimate; this version does not invent
cross-stage quota estimates.

## Completion and failures

Discovery can be terminal while intelligence is queued or processing. Both video-signal and
comment-pain normalization branches must terminate before intelligence becomes `completed`.
Item-level failures retain RAW/FACT data and yield `partial`; an exhausted stage retry or queue
failure yields `failed` with a bounded safe message. Retries remain bounded. Translation is not
called by this coordinator: existing TASK-042 hooks enqueue it naturally when a Signal or
Opportunity reaches an eligible review/active state.

## Recovery

The same stage services are idempotent, so a terminal legacy or partial batch can be inspected and
resumed without another discovery run:

```bash
uv run --project workers python workers/scripts/reconcile_discovery_pipeline.py \
  --topic-run-id UUID --limit 50 --dry-run
```

Remove `--dry-run` to reset only that terminal pipeline and enqueue its next bounded stage. Failed
metadata discovery items are returned to pending; current immutable AI outputs are reused.
Historical batches are never swept automatically.

## Current limitations

Progress is stage-count based, not a per-video workflow table. Comment staleness has no time-based
refresh policy; a video with stored comments is considered current. The coordinator caps AI stage
batches at existing service limits (100 videos and 200 comments), and reports exact counts only
where current persistence supports attribution. Trend aggregation and scoring remain their
existing independent workers.
