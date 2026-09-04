from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...infrastructure.ai import OpenAIClient
from ...infrastructure.auth import RequiredAdmin
from ...infrastructure.queue import JobEnqueuer, QueuedJob
from ...services.comment_pain_mining import (
    CommentNotFoundError,
    CommentPainBatchRequest,
    CommentPainBatchResult,
    CommentPainItemResult,
    CommentPainMiningService,
    CommentPainRunRequest,
)
from .youtube_discovery import enqueue_job, get_job_enqueuer

router = APIRouter(prefix="/admin/ai/comment-pain", tags=["admin", "ai"])


def get_comment_pain_service(request: Request) -> CommentPainMiningService:
    settings = request.app.state.settings
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    if (
        settings.ai_provider != "openai"
        or not settings.ai_model_comment_pain_mining
        or settings.openai_api_key is None
    ):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI comment pain mining is not configured"
        )
    client = OpenAIClient(
        settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
    )
    return CommentPainMiningService(
        sessions,
        client,
        provider="openai",
        model=settings.ai_model_comment_pain_mining,
    )


@router.post("", response_model=CommentPainBatchResult)
async def mine_batch(
    body: CommentPainBatchRequest,
    _: RequiredAdmin,
    service: Annotated[CommentPainMiningService, Depends(get_comment_pain_service)],
) -> CommentPainBatchResult:
    return await service.mine_batch(body)


@router.post("/jobs", response_model=QueuedJob, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_comment_pain(
    body: CommentPainBatchRequest,
    _: RequiredAdmin,
    enqueuer: Annotated[JobEnqueuer, Depends(get_job_enqueuer)],
) -> QueuedJob:
    return enqueue_job(
        enqueuer,
        queue="ai_extraction",
        actor="run_comment_pain_mining",
        payload=body.model_dump(mode="json"),
    )


@router.post("/{comment_id}", response_model=CommentPainItemResult)
async def mine_comment(
    comment_id: UUID,
    body: CommentPainRunRequest,
    _: RequiredAdmin,
    service: Annotated[CommentPainMiningService, Depends(get_comment_pain_service)],
) -> CommentPainItemResult:
    try:
        return await service.mine(comment_id, force=body.force)
    except CommentNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Canonical comment was not found") from error
