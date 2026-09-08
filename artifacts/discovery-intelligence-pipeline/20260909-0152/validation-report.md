# Discovery-to-Intelligence Validation Report

- Validation date: 2026-09-09 (Asia/Shanghai)
- Topic: `Micro Duck Trend Spillover`
- Topic ID: `200c7f35-fd6a-4acc-b97a-1075eb7f5f96`
- Topic run ID: `eb0d0d11-e53c-4480-8460-b34a06e9fc7c`
- Runtime profile: `local`
- Configuration fingerprint: `0b0184355f0cb72c`

## Original gap

Before this change, a completed topic run stopped after YouTube discovery. The latest prior batch
contained 57 discovery rows (53 unique external video IDs), but no canonical videos, comments,
relevance decisions, signals, or opportunity links attributable to that run.

## Orchestration exercised

The same topic-run correlation now continues through:

`Discovery -> Metadata -> Comments -> Relevance v001 -> Signal Extractor v003 / Comment Pain v001 -> Opportunity Normalizer v001 -> Translation`

The implementation reuses canonical videos, processes only explicit run-scoped IDs, excludes
irrelevant videos from video-signal extraction, and records resumable stage state on the topic run.

## Live result

The single real post-fix discovery run reached `intelligence_status=completed` with:

| Metric | Result |
| --- | ---: |
| Discovery results | 57 |
| Unique canonical videos | 54 |
| Newly collected videos | 22 |
| Metadata completed | 54 |
| Comments completed | 49 |
| Relevance completed | 54 |
| Relevant videos | 44 |
| Irrelevant videos | 10 |
| Signals created | 238 |
| Normalization candidate operations | 54 |
| Failed stages | 0 |

Database reconciliation additionally confirmed:

- 195 video-level signals were produced from the 44 relevant videos.
- None of the 10 irrelevant videos produced a video-level signal.
- Those video-level signals linked to 38 distinct, deduplicated opportunity records.
- The remaining 43 signals in the batch total came from comment-pain extraction.
- Both video and comment normalization branches completed.
- Translation orchestration was triggered naturally by downstream signal/opportunity activation.

`opportunity_candidates_created=54` is a normalization processing/match count, not a count of
distinct opportunity rows; opportunity deduplication reduced the linked result to 38 records.

## Recovery validation

The original successful discovery data was resumed with the reconciliation CLI after a
post-discovery callback defect was identified. The resume did not repeat external discovery calls.
The CLI supports dry-run inspection and bounded resume, and every downstream actor has a terminal
retry-exhaustion finalizer so a topic run cannot remain permanently active without an error state.

## Runtime validation

The unified launcher started Web, API, workers, and scheduler. API, every worker process, and the
scheduler reported the same database/Redis coordinates and configuration fingerprint. Web runs on
port 3000 and API on port 8000. Next.js development and production builds use webpack because the
repository resides on an external filesystem where Turbopack persistence is unreliable.

Route probes returned HTTP 307 for `/admin/discovery` and `/signals` without a browser session,
confirming the protected-page login boundary, and HTTP 200 for `/api/v1/health`.

## Automated verification

- Ruff: passed for `apps/api`, `workers`, and `packages`.
- API unit suite: passed (PostgreSQL tests skipped in the unit invocation).
- PostgreSQL integration suite: 69 passed against an isolated temporary database.
- Worker suite: 23 passed.
- Shared schema suite: 59 passed.
- Frontend typecheck: passed.
- Frontend ESLint: passed.
- Frontend Vitest: 70 passed.
- Next.js production build: passed with webpack; all MVP and admin routes compiled.

## Known non-blocking notes

- Five videos did not yield collected comments, while the bounded comment stage completed without a
  terminal stage failure. This is expected for videos with unavailable/disabled/no retrievable
  comments and did not block video intelligence processing.
- The frontend's generated `next-env.d.ts` has a pre-existing user modification and is intentionally
  excluded from the TASK-044D commit.
