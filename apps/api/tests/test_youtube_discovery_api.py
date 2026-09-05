from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.youtube_discovery import get_youtube_discovery_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.youtube_discovery import DiscoveryResult


class DiscoveryServiceStub:
    def __init__(self) -> None:
        self.called = False

    async def discover(self, request: object) -> DiscoveryResult:
        self.called = True
        now = datetime.now(UTC)
        return DiscoveryResult(
            collection_run_id=uuid4(),
            search_query_id=request.search_query_id,
            pages_requested=1,
            pages_completed=1,
            items_discovered=1,
            unique_video_count=1,
            estimated_quota_units=1,
            next_page_token=None,
            status="completed",
            started_at=now,
            finished_at=now,
        )


def current_user(role: str) -> CurrentUser:
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def test_manual_discovery_requires_authentication() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_youtube_discovery_service] = DiscoveryServiceStub
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/admin/youtube/discovery", json={"search_query_id": str(uuid4())}
        )
    assert response.status_code == 401


def test_normal_user_cannot_trigger_discovery() -> None:
    app = create_app(Settings(_env_file=None))
    service = DiscoveryServiceStub()
    app.dependency_overrides[get_current_user] = lambda: current_user("user")
    app.dependency_overrides[get_youtube_discovery_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/admin/youtube/discovery", json={"search_query_id": str(uuid4())}
        )
    assert response.status_code == 403
    assert service.called is False


def test_admin_can_trigger_discovery() -> None:
    app = create_app(Settings(_env_file=None))
    service = DiscoveryServiceStub()
    app.dependency_overrides[get_current_user] = lambda: current_user("admin")
    app.dependency_overrides[get_youtube_discovery_service] = lambda: service
    query_id = uuid4()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/admin/youtube/discovery",
            json={"search_query_id": str(query_id), "max_pages": 1, "max_results": 10},
        )
    assert response.status_code == 200
    assert response.json()["search_query_id"] == str(query_id)
    assert response.json()["estimated_quota_units"] == 1
    assert service.called is True
