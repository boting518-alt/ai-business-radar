"""Shared, cwd-independent runtime target resolution and safe diagnostics."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import SecretStr

RuntimeProfile = Literal["local", "live_validation", "staging", "production"]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SHARED_RUNTIME_ENV = REPOSITORY_ROOT / "apps" / "api" / ".env"


def resolve_database_url(
    profile: RuntimeProfile,
    database_url: SecretStr | None,
    live_validation_database_url: SecretStr | None,
) -> SecretStr | None:
    if profile == "live_validation":
        if live_validation_database_url is None:
            raise ValueError("LIVE_VALIDATION_DATABASE_URL is required for live_validation")
        return live_validation_database_url
    if profile in {"staging", "production"} and database_url is None:
        raise ValueError(f"DATABASE_URL is required for {profile}")
    return database_url


@dataclass(frozen=True)
class RuntimeTarget:
    runtime_profile: str
    database_host: str | None
    database_port: int | None
    database_name: str | None
    redis_host: str | None
    redis_port: int | None
    redis_database: str | None

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()[:16]


def runtime_target(
    profile: str, database_url: SecretStr | None, redis_url: SecretStr | None
) -> RuntimeTarget:
    database = _parse(database_url)
    redis = _parse(redis_url)
    return RuntimeTarget(
        runtime_profile=profile,
        database_host=database.hostname,
        database_port=database.port,
        database_name=database.path.lstrip("/") or None,
        redis_host=redis.hostname,
        redis_port=redis.port,
        redis_database=redis.path.lstrip("/") or None,
    )


def log_runtime_target(logger, component: str, target: RuntimeTarget) -> None:
    """Emit the same secret-free startup identity for every Python process."""
    logger.info(
        "runtime_start component=%s profile=%s database_host=%s database_port=%s "
        "database_name=%s redis_host=%s redis_port=%s redis_database=%s "
        "config_fingerprint=%s",
        component,
        target.runtime_profile,
        target.database_host,
        target.database_port,
        target.database_name,
        target.redis_host,
        target.redis_port,
        target.redis_database,
        target.fingerprint,
    )


def _parse(value: SecretStr | None):
    raw = value.get_secret_value() if value else ""
    return urlparse(raw.replace("postgresql+asyncpg://", "postgresql://", 1))
