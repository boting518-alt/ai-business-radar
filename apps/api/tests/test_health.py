from fastapi.testclient import TestClient

from ai_business_radar_api.config import Settings
from ai_business_radar_api.main import create_app


def test_create_app_metadata() -> None:
    app = create_app(Settings(_env_file=None))

    assert app.title == "YouTube AI Business Radar API"
    assert app.version == "0.1.0"


def test_health_returns_typed_service_status() -> None:
    app = create_app(Settings(_env_file=None))

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "api",
        "version": "0.1.0",
    }


def test_readiness_is_application_level_only() -> None:
    app = create_app(Settings(_env_file=None))

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
