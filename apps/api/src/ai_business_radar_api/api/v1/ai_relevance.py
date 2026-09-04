"""Admin-only entry points for the AI relevance filter."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...infrastructure.ai import AIConfigurationError, OpenAIClient
from ...infrastructure.auth import RequiredAdmin
from ...infrastructure.queue import JobEnqueuer, QueuedJob
from ...services.relevance_filter import (
    RelevanceBatchRequest,
    RelevanceBatchResult,
    RelevanceItemResult,
    RelevanceRunRequest,
    VideoNotFoundError,
    VideoRelevanceService,
)
from .youtube_discovery import enqueue_job, get_job_enqueuer

router = APIRouter(prefix="/admin/ai/relevance", tags=["admin", "ai"])


def get_relevance_service(request: Request) -> VideoRelevanceService:
    settings = request.app.state.settings
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    if settings.ai_provider != "openai" or not settings.ai_model_relevance:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "AI relevance is not configured")
    if settings.openai_api_key is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "AI relevance is not configured")
    try:
        client = OpenAIClient(
            settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
        )
    except AIConfigurationError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI relevance is not configured"
        ) from error
    return VideoRelevanceService(
        sessions, client, provider="openai", model=settings.ai_model_relevance
    )


@router.post("", response_model=RelevanceBatchResult)
async def analyze_batch(
    body: RelevanceBatchRequest,
    _: RequiredAdmin,
    service: Annotated[VideoRelevanceService, Depends(get_relevance_service)],
) -> RelevanceBatchResult:
    return await service.analyze_batch(body)


@router.post("/jobs", response_model=QueuedJob, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_relevance(
    body: RelevanceBatchRequest,
    _: RequiredAdmin,
    enqueuer: Annotated[JobEnqueuer, Depends(get_job_enqueuer)],
) -> QueuedJob:
    return enqueue_job(
        enqueuer,
        queue="ai_relevance",
        actor="run_relevance_filter",
        payload=body.model_dump(mode="json"),
    )


@router.post("/{video_id}", response_model=RelevanceItemResult)
async def analyze_video(
    video_id: UUID,
    body: RelevanceRunRequest,
    _: RequiredAdmin,
    service: Annotated[VideoRelevanceService, Depends(get_relevance_service)],
) -> RelevanceItemResult:
    try:
        return await service.analyze(video_id, force=body.force)
    except VideoNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Canonical video was not found") from error
