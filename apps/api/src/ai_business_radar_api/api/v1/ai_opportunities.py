from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...infrastructure.ai import OpenAIClient
from ...infrastructure.auth import RequiredAdmin
from ...infrastructure.queue import JobEnqueuer, QueuedJob
from ...services.opportunity_normalization import (
    OpportunityNormalizationBatchRequest,
    OpportunityNormalizationBatchResult,
    OpportunityNormalizationItemResult,
    OpportunityNormalizationRunRequest,
    OpportunityNormalizationService,
    SignalNotEligibleError,
    SignalNotFoundError,
)
from .youtube_discovery import enqueue_job, get_job_enqueuer

router = APIRouter(prefix="/admin/ai/opportunities/normalize", tags=["admin", "ai"])


def get_opportunity_normalization_service(request: Request) -> OpportunityNormalizationService:
    settings = request.app.state.settings
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    if (
        settings.ai_provider != "openai"
        or not settings.ai_model_opportunity_normalization
        or settings.openai_api_key is None
    ):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AI opportunity normalization is not configured",
        )
    return OpportunityNormalizationService(
        sessions,
        OpenAIClient(
            settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
        ),
        provider="openai",
        model=settings.ai_model_opportunity_normalization,
        match_threshold=settings.ai_opportunity_match_threshold,
        create_threshold=settings.ai_opportunity_create_threshold,
    )


@router.post("", response_model=OpportunityNormalizationBatchResult)
async def normalize_batch(
    body: OpportunityNormalizationBatchRequest,
    _: RequiredAdmin,
    service: Annotated[
        OpportunityNormalizationService, Depends(get_opportunity_normalization_service)
    ],
) -> OpportunityNormalizationBatchResult:
    return await service.normalize_batch(body)


@router.post("/jobs", response_model=QueuedJob, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_normalization(
    body: OpportunityNormalizationBatchRequest,
    _: RequiredAdmin,
    enqueuer: Annotated[JobEnqueuer, Depends(get_job_enqueuer)],
) -> QueuedJob:
    return enqueue_job(
        enqueuer,
        queue="ai_extraction",
        actor="run_opportunity_normalization",
        payload=body.model_dump(mode="json"),
    )


@router.post("/{signal_id}", response_model=OpportunityNormalizationItemResult)
async def normalize_signal(
    signal_id: UUID,
    body: OpportunityNormalizationRunRequest,
    _: RequiredAdmin,
    service: Annotated[
        OpportunityNormalizationService, Depends(get_opportunity_normalization_service)
    ],
) -> OpportunityNormalizationItemResult:
    try:
        return await service.normalize(signal_id, force=body.force)
    except SignalNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Signal was not found") from error
    except SignalNotEligibleError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
