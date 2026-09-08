"""Worker configuration extending the canonical shared runtime contract."""

from ai_business_radar_api.config import Settings
from pydantic import Field, SecretStr, model_validator


class WorkerSettings(Settings):
    redis_url: SecretStr
    database_url: SecretStr
    youtube_api_key: SecretStr
    youtube_staging_claim_timeout_minutes: int = Field(default=30, ge=1)
    youtube_staging_recovery_batch_size: int = Field(default=100, ge=1, le=1000)
    youtube_discovery_schedule_batch_size: int = Field(default=10, ge=1, le=100)
    youtube_metadata_batch_size: int = Field(default=50, ge=1, le=250)
    youtube_comment_batch_size: int = Field(default=20, ge=1, le=100)
    youtube_discovery_schedule_minutes: int = Field(default=360, ge=1)
    youtube_metadata_schedule_minutes: int = Field(default=30, ge=1)
    youtube_comment_schedule_minutes: int = Field(default=120, ge=1)
    youtube_stale_recovery_schedule_minutes: int = Field(default=15, ge=1)
    trend_aggregation_batch_size: int = Field(default=100, ge=1, le=500)
    trend_aggregation_schedule_hour_utc: int = Field(default=2, ge=0, le=23)
    opportunity_scoring_batch_size: int = Field(default=100, ge=1, le=500)
    opportunity_scoring_schedule_delay_minutes: int = Field(default=30, ge=1, le=180)
    translation_reconciliation_batch_size: int = Field(default=100, ge=1, le=500)
    translation_reconciliation_schedule_minutes: int = Field(default=20, ge=5, le=1440)

    @model_validator(mode="after")
    def require_worker_runtime(self) -> "WorkerSettings":
        if not self.database_url or not self.redis_url:
            raise ValueError("Worker requires resolved DATABASE_URL and REDIS_URL")
        return self
