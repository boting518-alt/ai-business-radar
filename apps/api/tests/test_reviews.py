from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.reviews import get_review_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.review_workflow import (
    DECISION_MATRIX,
    ReviewListResult,
    ReviewTaskResult,
    ReviewWorkflowResult,
)


class ServiceStub:
    def __init__(self) -> None:
        self.task_id = uuid4()

    async def list_tasks(self, request):
        return ReviewListResult(items=[], offset=request.offset, limit=request.limit)

    async def get_task(self, task_id):
        return task_result(task_id)

    async def claim_task(self, task_id, admin_id):
        return workflow_result(task_id, admin_id, "in_review", None)

    async def decide(self, task_id, admin_id, request):
        return workflow_result(task_id, admin_id, "resolved", request.decision.value)


def task_result(task_id):
    now = datetime(2026, 9, 5, tzinfo=UTC)
    return ReviewTaskResult(
        id=task_id,
        review_type="signal_validation",
        target_type="signal",
        target_id=uuid4(),
        status="pending",
        priority=1,
        assigned_to=None,
        resolved_by=None,
        decision=None,
        decision_notes=None,
        context=None,
        created_at=now,
        updated_at=now,
        resolved_at=None,
    )


def workflow_result(task_id, admin_id, status, decision):
    return ReviewWorkflowResult(
        review_task_id=task_id,
        review_type="signal_validation",
        previous_status="pending",
        status=status,
        decision=decision,
        target_type="signal",
        target_id=uuid4(),
        assigned_to=admin_id,
        resolved_by=admin_id if status == "resolved" else None,
        resolved_at=datetime(2026, 9, 5, tzinfo=UTC) if status == "resolved" else None,
    )


def user(role):
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role=role, email=None)


def test_review_decision_matrix_is_explicit() -> None:
    assert DECISION_MATRIX["signal_validation"] == {"approve", "reject", "ignore", "defer"}
    assert DECISION_MATRIX["opportunity_merge"] == {"merge", "reject", "defer"}
    assert set(DECISION_MATRIX) == {
        "signal_validation",
        "opportunity_match",
        "opportunity_merge",
        "opportunity_creation",
        "hype_review",
        "quality_review",
    }


def test_review_endpoints_are_admin_only_and_bounded() -> None:
    app = create_app(Settings(_env_file=None))
    stub = ServiceStub()
    app.dependency_overrides[get_review_service] = lambda: stub
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/reviews").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user("user")
        assert client.get("/api/v1/admin/reviews").status_code == 403
        admin = user("admin")
        app.dependency_overrides[get_current_user] = lambda: admin
        listing = client.get("/api/v1/admin/reviews?status=pending&limit=20")
        detail = client.get(f"/api/v1/admin/reviews/{stub.task_id}")
        claim = client.post(f"/api/v1/admin/reviews/{stub.task_id}/claim")
        decision = client.post(
            f"/api/v1/admin/reviews/{stub.task_id}/decision",
            json={"decision": "approve", "decision_notes": "Evidence checked"},
        )
        too_large = client.get("/api/v1/admin/reviews?limit=201")
    assert listing.status_code == 200 and listing.json()["limit"] == 20
    assert detail.status_code == 200
    assert claim.status_code == 200 and claim.json()["status"] == "in_review"
    assert decision.status_code == 200 and decision.json()["status"] == "resolved"
    assert too_large.status_code == 422
