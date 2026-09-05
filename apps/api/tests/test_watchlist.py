from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.watchlist import get_watchlist_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.watchlist import (
    WatchlistMembershipResult,
    WatchlistOpportunityNotVisible,
    WatchlistResult,
)


class WatchlistStub:
    async def list_items(self, user_id):
        return WatchlistResult(items=[])

    async def add(self, user_id, opportunity_id):
        if opportunity_id.int == 0:
            raise WatchlistOpportunityNotVisible
        return WatchlistMembershipResult(
            opportunity_id=opportunity_id,
            watchlisted=True,
            added_at=datetime.now(UTC),
        )

    async def remove(self, user_id, opportunity_id):
        return WatchlistMembershipResult(opportunity_id=opportunity_id, watchlisted=False)


def current_user():
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role="user", email=None)


def test_watchlist_routes_require_auth_and_expose_idempotent_contract() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_watchlist_service] = WatchlistStub
    opportunity_id = uuid4()
    with TestClient(app) as client:
        assert client.get("/api/v1/watchlist").status_code == 401
        app.dependency_overrides[get_current_user] = current_user
        listed = client.get("/api/v1/watchlist")
        added = client.post(f"/api/v1/watchlist/items/{opportunity_id}")
        removed = client.delete(f"/api/v1/watchlist/items/{opportunity_id}")
        hidden = client.post(f"/api/v1/watchlist/items/{'00000000-0000-0000-0000-000000000000'}")
    assert listed.json() == {"items": []}
    assert added.json()["watchlisted"] is True
    assert removed.json()["watchlisted"] is False
    assert hidden.status_code == 404


def test_openapi_exposes_watchlist_without_owner_input() -> None:
    schema = create_app(Settings(_env_file=None)).openapi()
    paths = schema["paths"]
    assert "/api/v1/watchlist" in paths
    assert "/api/v1/watchlist/items/{opportunity_id}" in paths
    assert "user_profile_id" not in str(paths["/api/v1/watchlist"])
