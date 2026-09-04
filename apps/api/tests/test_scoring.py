from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from ai_business_radar_schemas import OpportunityScoreComponents
from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.scoring import get_scoring_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.opportunity_scoring import (
    ScoringBatchResult,
    ScoringRunResult,
)


class ServiceStub:
    async def score(self, opportunity_id, *, force=False):
        return result(opportunity_id)

    async def score_batch(self, request):
        return ScoringBatchResult(requested=0, processed=0, reused=0, items=[])


def result(opportunity_id):
    return ScoringRunResult(
        opportunity_id=opportunity_id,
        score_id=uuid4(),
        calculated_at=datetime(2026, 9, 5, tzinfo=UTC),
        scoring_version="score-v001",
        input_hash="a" * 64,
        components=OpportunityScoreComponents(
            trend_velocity_score=50,
            demand_evidence_score=50,
            revenue_evidence_score=50,
            pain_severity_score=50,
            competition_white_space_score=50,
            build_feasibility_score=50,
            distribution_ease_score=50,
        ),
        opportunity_score=Decimal(50),
        confidence_score=Decimal(40),
        hype_risk_score=Decimal(60),
        inputs_snapshot={},
    )


def user(role):
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def test_scoring_endpoints_require_admin_and_support_single_and_batch() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_scoring_service] = ServiceStub
    opportunity_id = uuid4()
    with TestClient(app) as client:
        assert client.post(f"/api/v1/admin/scoring/{opportunity_id}", json={}).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user("user")
        assert client.post(f"/api/v1/admin/scoring/{opportunity_id}", json={}).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: user("admin")
        single = client.post(f"/api/v1/admin/scoring/{opportunity_id}", json={})
        batch = client.post("/api/v1/admin/scoring", json={"limit": 5})
    assert single.status_code == 200 and single.json()["scoring_version"] == "score-v001"
    assert batch.status_code == 200
