from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app


def identity(role: str) -> CurrentUser:
    return CurrentUser(
        auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email="test@example.com"
    )


def test_discovery_console_routes_are_admin_only_and_typed() -> None:
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/discovery/topics").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: identity("user")
        assert client.get("/api/v1/admin/discovery/topics").status_code == 403
    paths = app.openapi()["paths"]
    assert "/api/v1/admin/discovery/topics" in paths
    assert "/api/v1/admin/discovery/topics/{topic_id}/run" in paths
    assert "/api/v1/admin/discovery/queries/{query_id}/run" in paths
    assert "/api/v1/admin/discovery/runs" in paths
    assert "/api/v1/admin/discovery/runs/recover-stale" in paths
    schemas = app.openapi()["components"]["schemas"]
    assert "DiscoveryTopicSummary" in schemas
    assert "DiscoveryRunSummary" in schemas
    assert "DiscoverySystemStatus" in schemas
