# Collection worker runtime

Install from this directory with `uv sync`.

- Worker: `uv run dramatiq ai_business_radar_workers.worker`
- Scheduler: `uv run python -m ai_business_radar_workers.scheduler`

Collection actors require `REDIS_URL`, `DATABASE_URL`, and `YOUTUBE_API_KEY`. The manually
triggered `ai_relevance` actor additionally requires `AI_PROVIDER=openai`,
`AI_MODEL_RELEVANCE`, and `OPENAI_API_KEY`. The scheduler enqueues bounded collection,
aggregation/scoring, stale-claim recovery, and translation-reconciliation work; it does not
schedule relevance extraction automatically.

Business signal extraction also requires `AI_MODEL_SIGNAL_EXTRACTION` and runs manually on the
`ai_extraction` queue. It is not scheduled automatically.

Comment pain mining shares `ai_extraction`, requires `AI_MODEL_COMMENT_PAIN_MINING`, and is also
manual-only.

Opportunity normalization shares `ai_extraction`, requires
`AI_MODEL_OPPORTUNITY_NORMALIZATION`, and is manual-only. MATCH/CREATE thresholds default to 0.70
and 0.75 and can be changed with `AI_OPPORTUNITY_MATCH_THRESHOLD` and
`AI_OPPORTUNITY_CREATE_THRESHOLD`.

Trend aggregation runs on the non-AI `aggregation` queue. The scheduler submits bounded `7d`,
`30d`, and `90d` batches once daily at `TREND_AGGREGATION_SCHEDULE_HOUR_UTC` (default 02:00 UTC);
`TREND_AGGREGATION_BATCH_SIZE` defaults to 100.

Translation coverage reconciliation runs every 20 minutes by default. It scans at most
`TRANSLATION_RECONCILIATION_BATCH_SIZE` eligible review/active entities and submits only
missing, stale, wrong-version, or failed coverage to the dedicated `intelligence_translation`
queue. Lifecycle triggers remain primary; reconciliation repairs missed best-effort enqueue events.
