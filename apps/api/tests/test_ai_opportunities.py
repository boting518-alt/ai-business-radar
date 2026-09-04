from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.ai_opportunities import get_opportunity_normalization_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.opportunity_normalization import (
    OpportunityNormalizationBatchResult,
    OpportunityNormalizationItemResult,
)


class ServiceStub:
    async def normalize(self, signal_id, *, force=False):
        return OpportunityNormalizationItemResult(
            signal_id=signal_id,
            extraction_id=uuid4(),
            status="completed",
            action="MATCH",
            opportunity_id=uuid4(),
        )

    async def normalize_batch(self, request):
        return OpportunityNormalizationBatchResult(
            requested=0,
            processed=0,
            reused=0,
            matched=0,
            created=0,
            review=0,
            failed=0,
            items=[],
        )


def user(role):
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def test_opportunity_normalization_requires_admin_and_returns_safe_result() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_opportunity_normalization_service] = ServiceStub
    signal_id = uuid4()
    with TestClient(app) as client:
        assert (
            client.post(
                f"/api/v1/admin/ai/opportunities/normalize/{signal_id}", json={}
            ).status_code
            == 401
        )
        app.dependency_overrides[get_current_user] = lambda: user("user")
        assert (
            client.post(
                f"/api/v1/admin/ai/opportunities/normalize/{signal_id}", json={}
            ).status_code
            == 403
        )
        app.dependency_overrides[get_current_user] = lambda: user("admin")
        response = client.post(
            f"/api/v1/admin/ai/opportunities/normalize/{signal_id}", json={"force": False}
        )
        batch = client.post("/api/v1/admin/ai/opportunities/normalize", json={"limit": 2})
    assert response.status_code == 200 and response.json()["action"] == "MATCH"
    assert "raw_output" not in response.json() and batch.status_code == 200


def test_missing_opportunity_normalization_configuration_is_safe_503() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_current_user] = lambda: user("admin")
    with TestClient(app) as client:
        response = client.post(f"/api/v1/admin/ai/opportunities/normalize/{uuid4()}", json={})
    assert response.status_code == 503 and "key" not in response.text.lower()


def test_batch_limit_is_bounded() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_current_user] = lambda: user("admin")
    app.dependency_overrides[get_opportunity_normalization_service] = ServiceStub
    with TestClient(app) as client:
        response = client.post("/api/v1/admin/ai/opportunities/normalize", json={"limit": 201})
    assert response.status_code == 422
