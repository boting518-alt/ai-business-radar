from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...infrastructure.auth import RequiredAdmin
from ...infrastructure.queue import JobEnqueuer, QueuedJob
from ...services.opportunity_scoring import (
    OpportunityNotEligibleError,
    OpportunityNotFoundError,
    OpportunityScoringService,
    ScoringBatchRequest,
    ScoringBatchResult,
    ScoringRunRequest,
    ScoringRunResult,
)
from .youtube_discovery import enqueue_job, get_job_enqueuer

router = APIRouter(prefix="/admin/scoring", tags=["admin", "scoring"])


def get_scoring_service(request: Request) -> OpportunityScoringService:
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    return OpportunityScoringService(sessions)


@router.post("", response_model=ScoringBatchResult)
async def score_batch(
    body: ScoringBatchRequest,
    _: RequiredAdmin,
    service: Annotated[OpportunityScoringService, Depends(get_scoring_service)],
) -> ScoringBatchResult:
    return await service.score_batch(body)


@router.post("/jobs", response_model=QueuedJob, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_scoring(
    body: ScoringBatchRequest,
    _: RequiredAdmin,
    enqueuer: Annotated[JobEnqueuer, Depends(get_job_enqueuer)],
) -> QueuedJob:
    return enqueue_job(
        enqueuer,
        queue="aggregation",
        actor="run_opportunity_scoring",
        payload=body.model_dump(mode="json"),
    )


@router.post("/{opportunity_id}", response_model=ScoringRunResult)
async def score_one(
    opportunity_id: UUID,
    body: ScoringRunRequest,
    _: RequiredAdmin,
    service: Annotated[OpportunityScoringService, Depends(get_scoring_service)],
) -> ScoringRunResult:
    try:
        return await service.score(opportunity_id, force=body.force)
    except OpportunityNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity was not found") from error
    except OpportunityNotEligibleError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
