from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.youtube_discovery import get_job_enqueuer
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.infrastructure.queue import QueueUnavailableError
from ai_business_radar_api.main import create_app


class EnqueuerStub:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def enqueue(self, **values) -> str:
        if self.fail:
            raise QueueUnavailableError("redis details")
        self.calls.append(values)
        return "job-123"


def user(role: str) -> CurrentUser:
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def make_app(role: str, enqueuer: EnqueuerStub):
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_current_user] = lambda: user(role)
    app.dependency_overrides[get_job_enqueuer] = lambda: enqueuer
    return app


def test_async_enqueue_requires_auth_and_rejects_user() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_job_enqueuer] = EnqueuerStub
    with TestClient(app) as client:
        assert client.post("/api/v1/admin/youtube/metadata/jobs", json={}).status_code == 401
    enqueuer = EnqueuerStub()
    with TestClient(make_app("user", enqueuer)) as client:
        assert client.post("/api/v1/admin/youtube/comments/jobs", json={}).status_code == 403
    assert enqueuer.calls == []


def test_admin_enqueue_returns_202_and_json_safe_payloads() -> None:
    enqueuer = EnqueuerStub()
    query_id = uuid4()
    with TestClient(make_app("admin", enqueuer)) as client:
        response = client.post(
            "/api/v1/admin/youtube/discovery/jobs",
            json={"search_query_id": str(query_id), "max_pages": 1},
        )
    assert response.status_code == 202
    assert response.json() == {
        "job_id": "job-123",
        "queue": "youtube_discovery",
        "status": "queued",
    }
    assert enqueuer.calls[0]["payload"]["search_query_id"] == str(query_id)


def test_enqueue_failure_returns_safe_503() -> None:
    with TestClient(make_app("admin", EnqueuerStub(fail=True))) as client:
        response = client.post("/api/v1/admin/youtube/metadata/jobs", json={})
    assert response.status_code == 503
    assert response.json()["detail"] == "Collection queue is unavailable"
    assert "redis" not in response.text.lower()
