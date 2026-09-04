from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.youtube_discovery import get_youtube_metadata_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.youtube_metadata import MetadataCollectionResult


class MetadataServiceStub:
    def __init__(self) -> None:
        self.called = False

    async def collect(self, request: object) -> MetadataCollectionResult:
        self.called = True
        now = datetime.now(UTC)
        return MetadataCollectionResult(
            collection_run_id=uuid4(),
            items_claimed=1,
            items_processed=1,
            items_failed=0,
            videos_requested=1,
            videos_returned=1,
            channels_requested=1,
            channels_returned=1,
            snapshots_created=int(request.include_snapshots),
            estimated_quota_units=2,
            status="completed",
            started_at=now,
            finished_at=now,
        )


def user(role: str) -> CurrentUser:
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def test_metadata_requires_authentication() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_youtube_metadata_service] = MetadataServiceStub
    with TestClient(app) as client:
        response = client.post("/api/v1/admin/youtube/metadata", json={})
    assert response.status_code == 401


def test_normal_user_cannot_collect_metadata() -> None:
    app = create_app(Settings(_env_file=None))
    service = MetadataServiceStub()
    app.dependency_overrides[get_current_user] = lambda: user("user")
    app.dependency_overrides[get_youtube_metadata_service] = lambda: service
    with TestClient(app) as client:
        response = client.post("/api/v1/admin/youtube/metadata", json={})
    assert response.status_code == 403 and service.called is False


def test_admin_can_collect_metadata() -> None:
    app = create_app(Settings(_env_file=None))
    service = MetadataServiceStub()
    app.dependency_overrides[get_current_user] = lambda: user("admin")
    app.dependency_overrides[get_youtube_metadata_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/admin/youtube/metadata", json={"limit": 10, "include_snapshots": True}
        )
    assert response.status_code == 200
    assert response.json()["items_processed"] == 1 and service.called is True
