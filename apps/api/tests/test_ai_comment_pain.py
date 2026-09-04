from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.ai_comment_pain import get_comment_pain_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.comment_pain_mining import (
    CommentPainBatchResult,
    CommentPainItemResult,
)


class ServiceStub:
    async def mine(self, comment_id, *, force=False):
        return CommentPainItemResult(
            comment_id=comment_id,
            extraction_id=uuid4(),
            status="completed",
            mined=True,
            signals_created=1,
        )

    async def mine_batch(self, request):
        return CommentPainBatchResult(
            requested=0,
            processed=0,
            reused=0,
            signals_created=0,
            empty_results=0,
            failed=0,
            items=[],
        )


def current_user(role):
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def test_comment_pain_routes_enforce_admin_and_return_safe_output() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_comment_pain_service] = ServiceStub
    comment_id = uuid4()
    with TestClient(app) as client:
        assert (
            client.post(f"/api/v1/admin/ai/comment-pain/{comment_id}", json={}).status_code == 401
        )
        app.dependency_overrides[get_current_user] = lambda: current_user("user")
        assert (
            client.post(f"/api/v1/admin/ai/comment-pain/{comment_id}", json={}).status_code == 403
        )
        app.dependency_overrides[get_current_user] = lambda: current_user("admin")
        response = client.post(f"/api/v1/admin/ai/comment-pain/{comment_id}", json={})
        batch = client.post("/api/v1/admin/ai/comment-pain", json={"limit": 2})
    assert response.status_code == 200 and response.json()["signals_created"] == 1
    assert "raw_output" not in response.json() and batch.status_code == 200


def test_missing_comment_pain_configuration_returns_503() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_current_user] = lambda: current_user("admin")
    with TestClient(app) as client:
        response = client.post(f"/api/v1/admin/ai/comment-pain/{uuid4()}", json={})
    assert response.status_code == 503 and "key" not in response.text.lower()
