from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ai_business_radar_api.api.v1.candidates import get_candidate_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.candidate_workspace import CandidateEdit, CandidatePage


def user(role):
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


class Stub:
    async def list(self, filters, locale):
        assert filters.limit == 20 and filters.q == "robot" and locale == "zh-CN"
        return CandidatePage(items=[], total=0, offset=0, limit=20, has_more=False, counts={})


def test_candidate_routes_require_admin_and_parse_filters():
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_candidate_service] = lambda: Stub()
    with TestClient(app) as client:
        base = "/api/v1/admin/opportunities/candidates"
        assert client.get(base).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user("user")
        for method, path in (
            ("get", base),
            ("get", f"{base}/{uuid4()}"),
            ("get", f"{base}/{uuid4()}/evidence"),
            ("patch", f"{base}/{uuid4()}"),
        ):
            assert getattr(client, method)(path).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: user("admin")
        response = client.get(base, params={"q": "robot", "locale": "zh-CN"})
        assert response.status_code == 200, response.text
        assert client.get(base, params={"limit": 101}).status_code == 422
        assert client.get(base, params={"readiness": "invented"}).status_code == 422


@pytest.mark.parametrize(
    "change",
    [
        {"name": " "},
        {"name": None},
        {"market_stage": "fake"},
        {"market_stage": None},
        {"typical_price_min": -1},
        {"typical_price_currency": "usd"},
        {"raw_output": "overwrite"},
        {"industry_code": "invented"},
        {"competition_level": "fake"},
    ],
)
def test_candidate_edits_validate_and_forbid_unsupported_fields(change):
    with pytest.raises(ValidationError):
        CandidateEdit(expected_updated_at="2026-09-09T10:00:00Z", **change)


def test_candidate_prices_preserve_schema_precision_and_reject_non_finite_values():
    from decimal import Decimal

    change = CandidateEdit(expected_updated_at="2026-09-09T10:00:00Z", typical_price_min="0.0005")
    assert change.typical_price_min == Decimal("0.0005")
    for value in ("NaN", "Infinity"):
        with pytest.raises(ValidationError):
            CandidateEdit(expected_updated_at="2026-09-09T10:00:00Z", typical_price_min=value)
