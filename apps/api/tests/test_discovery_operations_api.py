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
    assert "/api/v1/admin/discovery/topic-runs/{topic_run_id}" in paths
    assert "/api/v1/admin/discovery/topic-runs/{topic_run_id}/runs" in paths
    assert "/api/v1/admin/discovery/topics/{topic_id}/runs" in paths
    schemas = app.openapi()["components"]["schemas"]
    assert "DiscoveryTopicSummary" in schemas
    assert "DiscoveryRunSummary" in schemas
    assert "DiscoverySystemStatus" in schemas
    assert "DiscoveryTopicRunDetail" in schemas
    assert "DiscoveryTopicRunSummary" in schemas


def test_discovery_system_status_exposes_only_safe_runtime_identity() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:secret@db.local:5432/radar",
        redis_url="redis://:hidden@cache.local:6379/0",
    )
    app = create_app(settings)
    app.dependency_overrides[get_current_user] = lambda: identity("admin")
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/discovery/system-status")

    assert response.status_code == 200
    body = response.json()
    assert body["database_host"] == "db.local"
    assert body["database_name"] == "radar"
    assert body["redis_host"] == "cache.local"
    assert body["runtime_profile"] == "local"
    assert "secret" not in response.text and "hidden" not in response.text
