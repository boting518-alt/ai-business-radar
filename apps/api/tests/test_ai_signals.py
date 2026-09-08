from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.ai_signals import get_signal_extraction_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.signal_extraction import SignalBatchResult, SignalItemResult


class ServiceStub:
    async def extract(self, video_id, *, force=False):
        return SignalItemResult(
            video_id=video_id, extraction_id=uuid4(), status="completed", signals_created=2
        )

    async def extract_batch(self, request):
        return SignalBatchResult(
            requested=0, processed=0, reused=0, signals_created=0, failed=0, items=[]
        )


def user(role):
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def test_signal_endpoint_requires_auth_and_admin() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_signal_extraction_service] = ServiceStub
    video_id = uuid4()
    with TestClient(app) as client:
        assert client.post(f"/api/v1/admin/ai/signals/{video_id}", json={}).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user("user")
        assert client.post(f"/api/v1/admin/ai/signals/{video_id}", json={}).status_code == 403


def test_admin_can_extract_without_raw_provider_output() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_current_user] = lambda: user("admin")
    app.dependency_overrides[get_signal_extraction_service] = ServiceStub
    with TestClient(app) as client:
        response = client.post(f"/api/v1/admin/ai/signals/{uuid4()}", json={"force": False})
    assert response.status_code == 200 and response.json()["signals_created"] == 2
    assert "raw_output" not in response.json()


def test_missing_signal_configuration_is_safe_503() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_current_user] = lambda: user("admin")
    with TestClient(app) as client:
        response = client.post(f"/api/v1/admin/ai/signals/{uuid4()}", json={})
    assert response.status_code == 503 and "key" not in response.text.lower()


def test_admin_runtime_diagnostics_exposes_versions_and_hashes_only() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_current_user] = lambda: user("admin")
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/runtime/ai-versions")
    assert response.status_code == 200
    body = response.json()
    assert body["prompts"]["signal_extractor"]["version"] == "v003"
    assert len(body["prompts"]["signal_extractor"]["prompt_hash"]) == 64
    assert "path" not in response.text and "key" not in response.text.lower()
    assert body["hybrid_retrieval"] == "offline_only"
