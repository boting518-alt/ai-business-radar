from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    redis_url: SecretStr
    database_url: SecretStr
    youtube_api_key: SecretStr
    ai_provider: str | None = None
    ai_model_relevance: str | None = None
    ai_model_signal_extraction: str | None = None
    ai_max_retries: int = 2
    openai_api_key: SecretStr | None = None
    youtube_api_base_url: str = "https://www.googleapis.com/youtube/v3/"
    youtube_http_timeout_seconds: float = 10
    youtube_max_retries: int = 3
    youtube_discovery_max_quota_units_per_run: int = 500
    youtube_comment_max_quota_units_per_run: int = 500
    youtube_staging_claim_timeout_minutes: int = Field(default=30, ge=1)
    youtube_staging_recovery_batch_size: int = Field(default=100, ge=1, le=1000)
    youtube_discovery_schedule_batch_size: int = Field(default=10, ge=1, le=100)
    youtube_metadata_batch_size: int = Field(default=50, ge=1, le=250)
    youtube_comment_batch_size: int = Field(default=20, ge=1, le=100)
    youtube_discovery_schedule_minutes: int = Field(default=360, ge=1)
    youtube_metadata_schedule_minutes: int = Field(default=30, ge=1)
    youtube_comment_schedule_minutes: int = Field(default=120, ge=1)
    youtube_stale_recovery_schedule_minutes: int = Field(default=15, ge=1)
