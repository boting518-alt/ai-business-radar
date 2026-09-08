from typing import Annotated, Literal
from uuid import UUID

from ai_business_radar_schemas import ReviewDecisionRequest
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ...infrastructure.auth import RequiredAdmin
from ...infrastructure.queue import JobEnqueuer
from ...services.review_workflow import (
    InvalidMergeTarget,
    InvalidReviewDecision,
    OpportunityMergeCycleError,
    ReviewAssignmentConflict,
    ReviewListRequest,
    ReviewListResult,
    ReviewTargetNotFound,
    ReviewTaskAlreadyResolved,
    ReviewTaskConflict,
    ReviewTaskNotFound,
    ReviewTaskResult,
    ReviewWorkflowResult,
    ReviewWorkflowService,
)
from ...services.translation_orchestration import TranslationCoverageReconciliationService

router = APIRouter(prefix="/admin/reviews", tags=["admin", "reviews"])


def get_review_service(request: Request) -> ReviewWorkflowService:
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    redis_url = request.app.state.settings.redis_url
    enqueuer = JobEnqueuer(redis_url.get_secret_value()) if redis_url is not None else None
    translation = TranslationCoverageReconciliationService(sessions, enqueuer)
    return ReviewWorkflowService(sessions, translation)


def _raise_review_error(error: Exception) -> None:
    if isinstance(error, (ReviewTaskNotFound, ReviewTargetNotFound)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    if isinstance(error, (InvalidReviewDecision, InvalidMergeTarget, OpportunityMergeCycleError)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    if isinstance(
        error,
        (ReviewTaskConflict, ReviewTaskAlreadyResolved, ReviewAssignmentConflict),
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    raise error


@router.get("", response_model=ReviewListResult)
async def list_reviews(
    _: RequiredAdmin,
    service: Annotated[ReviewWorkflowService, Depends(get_review_service)],
    review_status: Annotated[
        Literal["pending", "in_review", "resolved", "ignored"] | None,
        Query(alias="status"),
    ] = None,
    review_type: Literal[
        "signal_validation",
        "opportunity_match",
        "opportunity_merge",
        "opportunity_creation",
        "opportunity_activation",
        "hype_review",
        "quality_review",
    ]
    | None = None,
    assigned_to: UUID | None = None,
    priority: float | None = Query(default=None, ge=0),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> ReviewListResult:
    return await service.list_tasks(
        ReviewListRequest(
            status=review_status,
            review_type=review_type,
            assigned_to=assigned_to,
            priority=priority,
            offset=offset,
            limit=limit,
        )
    )


@router.get("/{review_task_id}", response_model=ReviewTaskResult)
async def get_review(
    review_task_id: UUID,
    _: RequiredAdmin,
    service: Annotated[ReviewWorkflowService, Depends(get_review_service)],
) -> ReviewTaskResult:
    try:
        return await service.get_task(review_task_id)
    except Exception as error:
        _raise_review_error(error)
        raise


@router.post("/{review_task_id}/claim", response_model=ReviewWorkflowResult)
async def claim_review(
    review_task_id: UUID,
    admin: RequiredAdmin,
    service: Annotated[ReviewWorkflowService, Depends(get_review_service)],
) -> ReviewWorkflowResult:
    try:
        return await service.claim_task(review_task_id, admin.user_profile_id)
    except Exception as error:
        _raise_review_error(error)
        raise


@router.post("/{review_task_id}/decision", response_model=ReviewWorkflowResult)
async def decide_review(
    review_task_id: UUID,
    body: ReviewDecisionRequest,
    admin: RequiredAdmin,
    service: Annotated[ReviewWorkflowService, Depends(get_review_service)],
) -> ReviewWorkflowResult:
    try:
        return await service.decide(review_task_id, admin.user_profile_id, body)
    except Exception as error:
        _raise_review_error(error)
        raise
