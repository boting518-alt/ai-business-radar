from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.radar import get_radar_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.radar_query import OpportunityLibraryResponse, RadarResponse


class ServiceStub:
    async def radar(self, user_id, request, locale="en-US"):
        return RadarResponse(items=[], total=0, offset=request.offset, limit=request.limit)

    async def opportunities(self, user_id, request, locale="en-US"):
        return OpportunityLibraryResponse(
            items=[], total=0, page=request.page, page_size=request.page_size, total_pages=0
        )

    async def signals(self, **filters):
        return []


def user(role):
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def test_product_query_routes_require_auth_and_validate_queries() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_radar_service] = ServiceStub
    with TestClient(app) as client:
        assert client.get("/api/v1/radar").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user("user")
        radar = client.get("/api/v1/radar?window_type=30d&industry=Dental,Legal&limit=20")
        browse = client.get(
            "/api/v1/opportunities?sort=score_desc&page=2&page_size=50&watchlisted=true"
        )
        signals = client.get("/api/v1/signals")
        invalid_window = client.get("/api/v1/radar?window_type=1d")
        invalid_limit = client.get("/api/v1/radar?limit=101")
    assert radar.status_code == 200 and radar.json()["limit"] == 20
    assert browse.status_code == 200 and browse.json()["page_size"] == 50
    assert signals.status_code == 200
    assert invalid_window.status_code == 422 and invalid_limit.status_code == 422
    parameters = create_app(Settings(_env_file=None)).openapi()["paths"]["/api/v1/signals"]["get"][
        "parameters"
    ]
    assert any(parameter["name"] == "locale" for parameter in parameters)
    opportunity_parameters = create_app(Settings(_env_file=None)).openapi()["paths"][
        "/api/v1/opportunities"
    ]["get"]["parameters"]
    assert {"q", "industry_code", "customer_code", "watchlisted", "page", "page_size"} <= {
        parameter["name"] for parameter in opportunity_parameters
    }


def test_openapi_exposes_product_routes_without_internal_score_inputs() -> None:
    schema = create_app(Settings(_env_file=None)).openapi()
    paths = schema["paths"]
    assert "/api/v1/radar" in paths
    assert "/api/v1/opportunities/{identifier}/scores" in paths
    assert "/api/v1/opportunities/{identifier}/trends" in paths
    assert "/api/v1/opportunities/{identifier}/evidence" in paths
    assert "inputs_snapshot" not in str(schema["components"]["schemas"]["ScoreItem"])
