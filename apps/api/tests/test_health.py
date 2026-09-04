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


def test_readiness_reports_unconfigured_database_without_failing_startup() -> None:
    app = create_app(Settings(_env_file=None))

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {"database": "not_configured"},
    }


def test_readiness_returns_503_when_configured_database_is_unreachable() -> None:
    class FailingSession:
        async def __aenter__(self) -> None:
            raise OSError("database unavailable")

        async def __aexit__(self, *args: object) -> None:
            return None

    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        app.state.database_session_factory = FailingSession
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependencies": {"database": "not_ready"},
    }
