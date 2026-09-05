# Local Live API & Intelligence Validation v0.1

## Purpose and boundaries

This workflow performs small, explicitly triggered checks against the official YouTube Data API and
OpenAI using the application's existing collection, extraction, normalization, trend, and scoring
services. It is local QA—not production intelligence. It does not start APScheduler or Dramatiq,
does not reset databases, does not bypass review, and never runs automatically in normal tests.

Generated reports can contain excerpts from public YouTube content and are ignored under
`artifacts/live-validation/`.

## Prerequisites

- PostgreSQL 16 with a dedicated database named `ai_business_radar_live_test`
- Redis reachable only from the local machine
- the API workspace installed with `uv sync`
- official YouTube and OpenAI API credentials
- explicit model names compatible with the structured Responses API

As of this workflow's validation date, OpenAI's official model pages list `gpt-5.6-luna` and
`gpt-5.6-terra` as Responses API models with Structured Outputs support:

- <https://developers.openai.com/api/docs/models/gpt-5.6-luna>
- <https://developers.openai.com/api/docs/models/gpt-5.6-terra>

Run every command below from `apps/api`.

## Local PostgreSQL setup

Create the dedicated database without dropping or reusing another database:

```bash
createdb ai_business_radar_live_test
export LIVE_VALIDATION_DATABASE_URL='postgresql+asyncpg://localhost/ai_business_radar_live_test'
```

Apply the existing migrations manually from the repository root:

```bash
for migration in database/migrations/[0-9]*.sql; do
  psql -X -v ON_ERROR_STOP=1 \
    'postgresql://localhost/ai_business_radar_live_test' -f "$migration"
done
```

The CLI never drops, truncates, resets, or silently migrates a database. It refuses remote hosts and
refuses every database name except `ai_business_radar_live_test`. Preflight prints only hostname and
database name, never credentials.

## Environment

Configure `apps/api/.env` locally:

```dotenv
LIVE_VALIDATION_DATABASE_URL=postgresql+asyncpg://localhost/ai_business_radar_live_test
REDIS_URL=redis://127.0.0.1:6379/0
YOUTUBE_API_KEY=
AI_PROVIDER=openai
OPENAI_API_KEY=
AI_MODEL_RELEVANCE=
AI_MODEL_SIGNAL_EXTRACTION=
AI_MODEL_COMMENT_PAIN_MINING=
AI_MODEL_OPPORTUNITY_NORMALIZATION=
```

Do not prefix either provider key with `NEXT_PUBLIC_`, put it in `apps/web`, pass it on the command
line, or commit the local `.env` file.

## Safety limits

| Input | Default | Hard cap |
| --- | ---: | ---: |
| Videos | 10 | 25 |
| Comments per video | 20 | 50 |
| YouTube pages | 1 | 2 |
| AI videos | 5 | 10 |
| AI comments | 20 | 50 |
| Normalization signals | 20 | 20 |

The runner rejects values outside these limits. `--force-ai` is off by default; enabling it creates
new audited extraction history and consumes tokens.

## Quota model

Google's official quota documentation changed in June 2026. `search.list` now costs one unit per
request in a dedicated default 100-calls/day Search Queries bucket. `videos.list`, `channels.list`,
and `commentThreads.list` cost one unit per request in the general allocation. Every requested page
is charged separately and even invalid requests have a cost. The application's estimate metadata was
updated to this model. Account-specific remaining quota can only be checked in Google Cloud Console.

Official references:

- <https://developers.google.com/youtube/v3/determine_quota_cost>
- <https://developers.google.com/youtube/v3/docs/search/list>
- <https://developers.google.com/youtube/v3/docs/commentThreads/list>

## Preflight

Configuration-only preflight performs no provider calls:

```bash
uv run python scripts/live_validation.py preflight
```

It reports configured/missing status for both keys, provider and four models, checks required tables,
and sends a safe Redis `PING`. To deliberately spend one minimal YouTube search call and one small
OpenAI structured-output request through the real adapters:

```bash
uv run python scripts/live_validation.py preflight --live
```

## Dry-run

Dry-run validates command limits and report generation but performs no network calls and makes no
database changes:

```bash
uv run python scripts/live_validation.py full \
  --query "AI dental receptionist" \
  --dry-run
```

## YouTube-only validation and RAW pause

```bash
uv run python scripts/live_validation.py youtube \
  --query "AI dental receptionist" \
  --max-videos 10 \
  --max-comments-per-video 20 \
  --max-pages 1
```

This invokes Discovery → Metadata → Comments and stops before any OpenAI request. Add
`--show-sample` to include at most five titles and five author-free, bounded comment excerpts in the
ignored report. Raw comments are never dumped to the terminal.

## AI-only validation

After inspecting locally collected RAW data:

```bash
uv run python scripts/live_validation.py ai \
  --max-ai-videos 5 \
  --max-ai-comments 20
```

This selects a deterministic bounded set of eligible local videos. Signal extraction runs only for
videos classified relevant. Comment mining operates one comment per existing service call and may
correctly return no signal.

## Full pipeline

```bash
uv run python scripts/live_validation.py full \
  --query "AI dental receptionist" \
  --max-videos 10 \
  --max-comments-per-video 20 \
  --max-ai-videos 5 \
  --max-ai-comments 20
```

The full flow invokes Discovery → Metadata → Comments → Relevance → Signal Extraction → Comment
Pain Mining → Opportunity Normalization → 7d/30d/90d Trend Aggregation → deterministic Scoring.
No scoring formula or prompt is reimplemented by the CLI.

## Stop points and force behavior

Use `--stop-after` with `discovery`, `metadata`, `comments`, `relevance`, `signals`, `comment-pain`,
`normalization`, `trend`, or `scoring`. The completed partial report remains available. Prefer the
YouTube-only command or `--stop-after comments` before paying for AI calls.

Use `--force-ai` only for an intentional repeat-quality test. Default reuse avoids duplicate provider
requests when application extraction identity matches.

## Reports and manual review

Each invocation writes a timestamped directory containing:

- `summary.md` and `summary.json`
- `relevance_review.csv`
- `signal_review.csv`
- `comment_pain_review.csv`
- `opportunities.csv`
- `scores.csv`

Reports include safe run metadata, applied limits, RAW counts, stage outcomes, token totals from
persisted `ai_extractions`, failures by exception type, ranking components, and blank human-review
fields. They never estimate cost because model pricing is not frozen in this repository.

Manually complete Relevance Precision, Signal Precision, Atomic Signal Quality, Creator Claim
Accuracy, Comment No-Signal Accuracy, Comment Pain Precision, Purchase Intent Precision,
Opportunity Match Accuracy, Opportunity Duplicate Rate, and Top-10 Usefulness. The CLI does not
invent labels or calculate quality metrics without those labels.

The opportunity file lists created/matched candidates and linked-signal counts for duplicate review.
The existing normalizer performs lexical candidate selection internally; candidate similarity scores
are not exposed by its public result, so the CLI does not duplicate that algorithm.

## Radar visibility and frontend demo

Signals normally remain in review and opportunities may remain candidates. The runner does not
directly update status or bypass authorization. **Radar may be empty until the normal Admin Review
workflow activates the intelligence.** After legitimate review, start FastAPI and Next.js normally,
sign in as a configured local user, and open `/radar`.

## Cleanup, security, and limitations

Stop local processes and delete the dedicated database manually only when its identity has been
independently verified. Reports and collected local data are not fixtures and must not be committed.
Errors are reduced to exception class names; provider responses and credentials are never printed.

Known limits: no automatic clean reset, no browser review automation, no scheduler/queue execution,
no automatic duplicate metric, and no real cost estimate. A stage failure stops later stages but
still writes all completed-stage results and a sanitized partial report.
