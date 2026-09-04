from uuid import UUID

from fastapi.testclient import TestClient

from ai_business_radar_api.config import Settings
from ai_business_radar_api.main import create_app
from ai_business_radar_api.middleware.request_id import REQUEST_ID_HEADER


def test_request_id_is_generated_when_absent() -> None:
    app = create_app(Settings(_env_file=None))

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    generated = response.headers[REQUEST_ID_HEADER]
    assert str(UUID(generated)) == generated


def test_safe_supplied_request_id_is_preserved() -> None:
    app = create_app(Settings(_env_file=None))
    supplied = "client-request_123:retry.1"

    with TestClient(app) as client:
        response = client.get("/api/v1/health", headers={REQUEST_ID_HEADER: supplied})

    assert response.headers[REQUEST_ID_HEADER] == supplied


def test_unsafe_supplied_request_id_is_replaced() -> None:
    app = create_app(Settings(_env_file=None))

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/health",
            headers={REQUEST_ID_HEADER: "unsafe request id with spaces"},
        )

    generated = response.headers[REQUEST_ID_HEADER]
    assert generated != "unsafe request id with spaces"
    UUID(generated)
