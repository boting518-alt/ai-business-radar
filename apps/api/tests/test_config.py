import pytest
from pydantic import ValidationError

from ai_business_radar_api.config import Settings


def test_non_secret_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.app_name == "YouTube AI Business Radar API"
    assert settings.app_version == "0.1.0"
    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 8000
    assert settings.log_level == "INFO"
    assert settings.cors_origin_list == ["http://localhost:3000"]
    assert settings.youtube_api_base_url == "https://www.googleapis.com/youtube/v3/"
    assert settings.youtube_http_timeout_seconds == 10.0
    assert settings.youtube_max_retries == 3
    assert settings.youtube_discovery_max_quota_units_per_run == 500
    assert settings.youtube_comment_max_quota_units_per_run == 500
    assert settings.signal_extractor_prompt_version == "v003"


def test_external_service_secrets_are_optional() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url is None
    assert settings.redis_url is None
    assert settings.youtube_api_key is None
    assert settings.openai_api_key is None
    assert settings.supabase_service_role_key is None
    assert settings.hosted_supabase_database_url is None


def test_supabase_issuer_and_audience_accept_hosted_aliases(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_ISSUER", "https://project.supabase.co/auth/v1")
    monkeypatch.setenv("SUPABASE_AUDIENCE", "authenticated")

    settings = Settings(_env_file=None)

    assert settings.supabase_jwt_issuer == "https://project.supabase.co/auth/v1"
    assert settings.supabase_jwt_audience == "authenticated"


def test_cors_accepts_comma_separated_or_json_lists() -> None:
    comma_separated = Settings(
        _env_file=None,
        cors_origins="http://localhost:3000,https://radar.example",
    )
    json_list = Settings(
        _env_file=None,
        cors_origins='["http://localhost:3000", "https://radar.example"]',
    )

    expected = ["http://localhost:3000", "https://radar.example"]
    assert comma_separated.cors_origin_list == expected
    assert json_list.cors_origin_list == expected


def test_production_cors_rejects_unrestricted_wildcard() -> None:
    with pytest.raises(ValidationError, match="must not contain"):
        Settings(_env_file=None, app_env="production", cors_origins="*")


def test_signal_prompt_version_allows_rollback_and_rejects_unknown_version() -> None:
    settings = Settings(_env_file=None, signal_extractor_prompt_version="v001")
    assert settings.signal_extractor_prompt_version == "v001"
    with pytest.raises(ValidationError, match="Invalid prompt version"):
        Settings(_env_file=None, signal_extractor_prompt_version="v999")


def test_live_validation_selects_explicit_database_and_has_safe_fingerprint() -> None:
    settings = Settings(
        _env_file=None,
        runtime_profile="live_validation",
        database_url="postgresql://user:secret@db.local:5432/default_db",
        live_validation_database_url="postgresql://other:hidden@validation.local:6432/live_db",
        redis_url="redis://:password@cache.local:6379/2",
    )

    target = settings.runtime_target
    assert target.database_host == "validation.local"
    assert target.database_name == "live_db"
    assert target.redis_host == "cache.local"
    assert len(target.fingerprint) == 16
    assert "secret" not in repr(target) and "password" not in repr(target)


def test_live_validation_fails_without_dedicated_database() -> None:
    with pytest.raises(ValidationError, match="LIVE_VALIDATION_DATABASE_URL"):
        Settings(_env_file=None, runtime_profile="live_validation")
