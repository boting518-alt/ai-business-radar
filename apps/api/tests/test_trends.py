from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.trends import get_trend_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.trend_aggregation import (
    TrendAggregationBatchResult,
    TrendAggregationMetrics,
    TrendAggregationResult,
)


class ServiceStub:
    async def aggregate(self, request):
        return result(request.opportunity_id)

    async def aggregate_batch(self, request):
        return TrendAggregationBatchResult(requested=0, processed=0, reused=0, items=[])


def result(opportunity_id):
    end = datetime(2026, 9, 4, tzinfo=UTC)
    return TrendAggregationResult(
        opportunity_id=opportunity_id,
        snapshot_id=uuid4(),
        window_type="7d",
        period_start=datetime(2026, 8, 28, tzinfo=UTC),
        period_end=end,
        aggregation_version="trend-v001",
        metrics=TrendAggregationMetrics(
            video_count=0,
            new_video_count=0,
            unique_channel_count=0,
            total_views=0,
            comment_count=0,
            pain_signal_count=0,
            demand_signal_count=0,
            purchase_intent_signal_count=0,
            revenue_signal_count=0,
            competitor_signal_count=0,
            momentum_score=Decimal("50"),
        ),
    )


def user(role):
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def test_trend_endpoints_require_admin_and_support_single_and_batch() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_trend_service] = ServiceStub
    opportunity_id = uuid4()
    with TestClient(app) as client:
        assert client.post(f"/api/v1/admin/trends/{opportunity_id}", json={}).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user("user")
        assert client.post(f"/api/v1/admin/trends/{opportunity_id}", json={}).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: user("admin")
        single = client.post(
            f"/api/v1/admin/trends/{opportunity_id}",
            json={"window_type": "7d", "period_end": "2026-09-04T00:00:00Z"},
        )
        batch = client.post("/api/v1/admin/trends", json={"window_type": "30d", "limit": 5})
    assert single.status_code == 200 and single.json()["aggregation_version"] == "trend-v001"
    assert batch.status_code == 200
