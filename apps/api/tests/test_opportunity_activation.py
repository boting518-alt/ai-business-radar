from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.opportunity_activation import get_activation_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.opportunity_activation import (
    ActivationMetrics,
    ActivationReviewResult,
    OpportunityActivationReadiness,
    ReadinessCheck,
)


class ServiceStub:
    def __init__(self) -> None:
        self.opportunity_id = uuid4()
        self.review_id = uuid4()

    async def assess(self, opportunity_id: UUID):
        return readiness(opportunity_id)

    async def create_review(self, opportunity_id: UUID):
        return ActivationReviewResult(
            review_task_id=self.review_id,
            created=True,
            readiness=readiness(opportunity_id),
        )


def readiness(opportunity_id):
    now = datetime(2026, 9, 7, tzinfo=UTC)
    check = ReadinessCheck(status="pass", message="ready", supporting_metrics={})
    return OpportunityActivationReadiness(
        opportunity_id=opportunity_id,
        checks={
            name: check
            for name in (
                "supporting_evidence",
                "scope_clear",
                "commercial_definition",
                "duplicate_risk",
                "source_diversity",
                "contradiction_quality",
            )
        },
        overall="ready",
        recommendation="publish",
        metrics=ActivationMetrics(
            active_signal_count=2,
            distinct_video_count=2,
            distinct_channel_count=2,
            latest_score=42,
            confidence_score=60,
            hype_risk=20,
            momentum_7d=50,
            first_detected_at=now,
            last_activity_at=now,
        ),
        duplicate_candidates=[],
    )


def user(role):
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def test_activation_endpoints_are_admin_only_and_do_not_decide_publication():
    app = create_app(Settings(_env_file=None))
    stub = ServiceStub()
    app.dependency_overrides[get_activation_service] = lambda: stub
    with TestClient(app) as client:
        path = f"/api/v1/admin/opportunities/{stub.opportunity_id}"
        assert client.get(f"{path}/activation-readiness").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user("user")
        assert client.post(f"{path}/activation-review").status_code == 403
        app.dependency_overrides[get_current_user] = lambda: user("admin")
        assessed = client.get(f"{path}/activation-readiness")
        created = client.post(f"{path}/activation-review")
    assert assessed.status_code == 200
    assert assessed.json()["recommendation"] == "publish"
    assert created.status_code == 200 and created.json()["created"] is True
    assert created.json()["review_task_id"] == str(stub.review_id)
