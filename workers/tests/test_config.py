import pytest
from ai_business_radar_api.config import Settings
from pydantic import ValidationError

from ai_business_radar_workers.config import WorkerSettings


def test_api_and_worker_resolve_identical_runtime_target() -> None:
    values = {
        "database_url": "postgresql://user:secret@db.local:5432/radar",
        "redis_url": "redis://cache.local:6379/1",
        "youtube_api_key": "test-key",
    }
    api = Settings(_env_file=None, **values)
    worker = WorkerSettings(_env_file=None, **values)
    assert worker.runtime_target == api.runtime_target
    assert worker.runtime_target.fingerprint == api.runtime_target.fingerprint


def test_worker_fails_fast_without_database_or_redis() -> None:
    with pytest.raises(ValidationError):
        WorkerSettings(_env_file=None, youtube_api_key="test-key")
