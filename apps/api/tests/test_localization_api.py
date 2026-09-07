from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.youtube_discovery import get_job_enqueuer
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app


class Enqueuer:
    def __init__(self):
        self.calls = []

    def enqueue(self, **kwargs):
        self.calls.append(kwargs)
        return "job-translation"


def user(role):
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def test_translation_endpoint_is_admin_only_and_uses_dedicated_queue():
    app = create_app(Settings(_env_file=None))
    queue = Enqueuer()
    app.dependency_overrides[get_job_enqueuer] = lambda: queue
    body = {"entity_type": "signal", "entity_id": str(uuid4()), "locale": "zh-CN"}
    with TestClient(app) as client:
        app.dependency_overrides[get_current_user] = lambda: user("user")
        assert client.post("/api/v1/admin/localization/translate", json=body).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: user("admin")
        response = client.post("/api/v1/admin/localization/translate", json=body)
    assert response.status_code == 202
    assert response.json() == {
        "job_id": "job-translation",
        "queue": "intelligence_translation",
        "status": "queued",
    }
    assert queue.calls[0]["actor"] == "translate_signal"


def test_translation_batch_is_bounded_and_dry_run_never_enqueues():
    app = create_app(Settings(_env_file=None))
    queue = Enqueuer()
    app.dependency_overrides[get_job_enqueuer] = lambda: queue
    app.dependency_overrides[get_current_user] = lambda: user("admin")
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/admin/localization/translate-batch",
                json={"entity_type": "all", "locale": "zh-CN", "limit": 51},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/admin/localization/translate-batch",
                json={"entity_type": "all", "locale": "zh-CN", "dry_run": True},
            ).status_code
            == 422
        )
    assert queue.calls == []


def test_unsupported_locale_and_field_are_rejected():
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_job_enqueuer] = Enqueuer
    app.dependency_overrides[get_current_user] = lambda: user("admin")
    base = {"entity_type": "signal", "entity_id": str(uuid4())}
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/admin/localization/translate", json={**base, "locale": "ja-JP"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/admin/localization/translate", json={**base, "fields": ["video_title"]}
            ).status_code
            == 422
        )
