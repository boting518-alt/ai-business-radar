"""Admin-only business signal extraction entry points."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...infrastructure.ai import OpenAIClient
from ...infrastructure.auth import RequiredAdmin
from ...infrastructure.queue import JobEnqueuer, QueuedJob
from ...services.signal_extraction import (
    BusinessSignalExtractionService,
    SignalBatchRequest,
    SignalBatchResult,
    SignalItemResult,
    SignalRunRequest,
    SignalVideoNotEligibleError,
    SignalVideoNotFoundError,
)
from .youtube_discovery import enqueue_job, get_job_enqueuer

router = APIRouter(prefix="/admin/ai/signals", tags=["admin", "ai"])


def get_signal_extraction_service(request: Request) -> BusinessSignalExtractionService:
    settings = request.app.state.settings
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    if (
        settings.ai_provider != "openai"
        or not settings.ai_model_signal_extraction
        or settings.openai_api_key is None
    ):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI signal extraction is not configured"
        )
    client = OpenAIClient(
        settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
    )
    return BusinessSignalExtractionService(
        sessions,
        client,
        provider="openai",
        model=settings.ai_model_signal_extraction,
        prompt_version=settings.signal_extractor_prompt_version,
    )


@router.post("", response_model=SignalBatchResult)
async def extract_batch(
    body: SignalBatchRequest,
    _: RequiredAdmin,
    service: Annotated[BusinessSignalExtractionService, Depends(get_signal_extraction_service)],
) -> SignalBatchResult:
    return await service.extract_batch(body)


@router.post("/jobs", response_model=QueuedJob, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_signal_extraction(
    body: SignalBatchRequest,
    _: RequiredAdmin,
    enqueuer: Annotated[JobEnqueuer, Depends(get_job_enqueuer)],
) -> QueuedJob:
    return enqueue_job(
        enqueuer,
        queue="ai_extraction",
        actor="run_signal_extraction",
        payload=body.model_dump(mode="json"),
    )


@router.post("/{video_id}", response_model=SignalItemResult)
async def extract_video(
    video_id: UUID,
    body: SignalRunRequest,
    _: RequiredAdmin,
    service: Annotated[BusinessSignalExtractionService, Depends(get_signal_extraction_service)],
) -> SignalItemResult:
    try:
        return await service.extract(video_id, force=body.force)
    except SignalVideoNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Canonical video was not found") from error
    except SignalVideoNotEligibleError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Video is not queued for signal extraction"
        ) from error
