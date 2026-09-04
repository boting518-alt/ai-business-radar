# Collection worker runtime

Install from this directory with `uv sync`.

- Worker: `uv run dramatiq ai_business_radar_workers.worker`
- Scheduler: `uv run python -m ai_business_radar_workers.scheduler`

Both commands require `REDIS_URL`, `DATABASE_URL`, and `YOUTUBE_API_KEY`. The scheduler only enqueues bounded jobs; workers execute the existing application services.
