# Collection worker runtime

Install from this directory with `uv sync`.

- Worker: `uv run dramatiq ai_business_radar_workers.worker`
- Scheduler: `uv run python -m ai_business_radar_workers.scheduler`

Collection actors require `REDIS_URL`, `DATABASE_URL`, and `YOUTUBE_API_KEY`. The manually
triggered `ai_relevance` actor additionally requires `AI_PROVIDER=openai`,
`AI_MODEL_RELEVANCE`, and `OPENAI_API_KEY`. The scheduler only enqueues bounded YouTube
collection jobs; v0.1 does not schedule relevance processing automatically.

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
