"""Environment-backed application configuration."""

import json
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .infrastructure.ai.errors import PromptNotFoundError
from .infrastructure.ai.prompts import default_prompt_version, resolve_prompt


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "YouTube AI Business Radar API"
    app_version: str = "0.1.0"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    supabase_url: str | None = None
    supabase_anon_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_jwt_secret: SecretStr | None = None
    supabase_jwks_url: str | None = None
    supabase_jwt_issuer: str | None = None
    supabase_jwt_audience: str | None = "authenticated"
    database_url: SecretStr | None = None
    live_validation_database_url: SecretStr | None = None
    redis_url: SecretStr | None = None

    youtube_api_key: SecretStr | None = None
    youtube_api_base_url: str = "https://www.googleapis.com/youtube/v3/"
    youtube_http_timeout_seconds: float = 10.0
    youtube_max_retries: int = 3
    youtube_discovery_max_quota_units_per_run: int = 500
    youtube_comment_max_quota_units_per_run: int = 500
    ai_provider: str | None = None
    ai_model_relevance: str | None = None
    ai_model_signal_extraction: str | None = None
    signal_extractor_prompt_version: str = default_prompt_version("signal-extractor")
    ai_model_comment_pain_mining: str | None = None
    ai_model_opportunity_normalization: str | None = None
    intelligence_translation_model: str | None = None
    ai_opportunity_match_threshold: float = Field(default=0.70, ge=0, le=1)
    ai_opportunity_create_threshold: float = Field(default=0.75, ge=0, le=1)
    ai_max_retries: int = 2
    openai_api_key: SecretStr | None = None

    @field_validator("signal_extractor_prompt_version")
    @classmethod
    def validate_signal_prompt_version(cls, value: str) -> str:
        try:
            resolve_prompt("signal-extractor", value)
        except PromptNotFoundError as error:
            raise ValueError(str(error)) from error
        return value

    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        raw_value = self.cors_origins.strip()
        if raw_value.startswith("["):
            decoded = json.loads(raw_value)
            if not isinstance(decoded, list) or not all(isinstance(item, str) for item in decoded):
                raise ValueError("CORS_ORIGINS JSON must be a list of strings")
            return [item.strip() for item in decoded if item.strip()]
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    @model_validator(mode="after")
    def validate_safe_production_cors(self) -> "Settings":
        if self.app_env.lower() == "production" and "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS must not contain '*' in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
