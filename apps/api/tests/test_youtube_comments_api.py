from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.youtube_discovery import get_youtube_comment_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.youtube_comments import CommentCollectionResult


class CommentServiceStub:
    def __init__(self) -> None:
        self.called = False

    async def collect(self, request: object) -> CommentCollectionResult:
        self.called = True
        now = datetime.now(UTC)
        return CommentCollectionResult(
            collection_run_id=uuid4(),
            videos_requested=1,
            videos_completed=1,
            videos_failed=0,
            videos_skipped=0,
            pages_requested=1,
            pages_completed=1,
            comments_discovered=1,
            comments_processed=1,
            estimated_quota_units=1,
            status="completed",
            started_at=now,
            finished_at=now,
        )


def user(role: str) -> CurrentUser:
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def test_comments_require_authentication() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_youtube_comment_service] = CommentServiceStub
    with TestClient(app) as client:
        response = client.post("/api/v1/admin/youtube/comments", json={})
    assert response.status_code == 401


def test_normal_user_cannot_collect_comments() -> None:
    app = create_app(Settings(_env_file=None))
    service = CommentServiceStub()
    app.dependency_overrides[get_current_user] = lambda: user("user")
    app.dependency_overrides[get_youtube_comment_service] = lambda: service
    with TestClient(app) as client:
        response = client.post("/api/v1/admin/youtube/comments", json={})
    assert response.status_code == 403 and service.called is False


def test_admin_can_collect_comments() -> None:
    app = create_app(Settings(_env_file=None))
    service = CommentServiceStub()
    app.dependency_overrides[get_current_user] = lambda: user("admin")
    app.dependency_overrides[get_youtube_comment_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/admin/youtube/comments",
            json={"limit_videos": 2, "max_pages_per_video": 1, "order": "relevance"},
        )
    assert response.status_code == 200
    assert response.json()["comments_processed"] == 1 and service.called is True
