from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...infrastructure.auth import RequiredAdmin
from ...infrastructure.queue import JobEnqueuer, QueuedJob
from ...services.trend_aggregation import (
    OpportunityNotEligibleError,
    OpportunityNotFoundError,
    OpportunityTrendAggregationService,
    TrendAggregationBatchRequest,
    TrendAggregationBatchResult,
    TrendAggregationRequest,
    TrendAggregationResult,
)
from .youtube_discovery import enqueue_job, get_job_enqueuer

router = APIRouter(prefix="/admin/trends", tags=["admin", "trends"])


def get_trend_service(request: Request) -> OpportunityTrendAggregationService:
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    return OpportunityTrendAggregationService(sessions)


@router.post("", response_model=TrendAggregationBatchResult)
async def aggregate_batch(
    body: TrendAggregationBatchRequest,
    _: RequiredAdmin,
    service: Annotated[OpportunityTrendAggregationService, Depends(get_trend_service)],
) -> TrendAggregationBatchResult:
    return await service.aggregate_batch(body)


@router.post("/jobs", response_model=QueuedJob, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_aggregation(
    body: TrendAggregationBatchRequest,
    _: RequiredAdmin,
    enqueuer: Annotated[JobEnqueuer, Depends(get_job_enqueuer)],
) -> QueuedJob:
    return enqueue_job(
        enqueuer,
        queue="aggregation",
        actor="run_trend_aggregation",
        payload=body.model_dump(mode="json"),
    )


@router.post("/{opportunity_id}", response_model=TrendAggregationResult)
async def aggregate_one(
    opportunity_id: UUID,
    body: TrendAggregationRequest,
    _: RequiredAdmin,
    service: Annotated[OpportunityTrendAggregationService, Depends(get_trend_service)],
) -> TrendAggregationResult:
    try:
        return await service.aggregate(body.model_copy(update={"opportunity_id": opportunity_id}))
    except OpportunityNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity was not found") from error
    except OpportunityNotEligibleError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
