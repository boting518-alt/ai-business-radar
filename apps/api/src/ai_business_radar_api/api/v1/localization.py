"""Admin-only enqueue boundaries for persisted intelligence translations."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...infrastructure.auth import RequiredAdmin
from ...infrastructure.queue import JobEnqueuer, QueuedJob
from ...services.intelligence_translation import TranslationBatchRequest, TranslationRequest
from ...services.translation_orchestration import (
    TranslationCoverageReconciliationService,
    TranslationReconciliationRequest,
    TranslationReconciliationResult,
)
from .youtube_discovery import enqueue_job, get_job_enqueuer

router = APIRouter(prefix="/admin/localization", tags=["admin", "localization"])


def get_reconciliation_service(request: Request) -> TranslationCoverageReconciliationService:
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    redis_url = request.app.state.settings.redis_url
    enqueuer = JobEnqueuer(redis_url.get_secret_value()) if redis_url is not None else None
    return TranslationCoverageReconciliationService(sessions, enqueuer)


@router.post("/translate", response_model=QueuedJob, status_code=status.HTTP_202_ACCEPTED)
async def translate_entity(
    body: TranslationRequest,
    _: RequiredAdmin,
    enqueuer: Annotated[JobEnqueuer, Depends(get_job_enqueuer)],
) -> QueuedJob:
    if body.dry_run:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use the local CLI for dry-run")
    actor = "translate_signal" if body.entity_type == "signal" else "translate_opportunity"
    return enqueue_job(
        enqueuer,
        queue="intelligence_translation",
        actor=actor,
        payload=body.model_dump(mode="json", by_alias=True, exclude={"dry_run"}),
    )


@router.post("/translate-batch", response_model=QueuedJob, status_code=status.HTTP_202_ACCEPTED)
async def translate_batch(
    body: TranslationBatchRequest,
    _: RequiredAdmin,
    enqueuer: Annotated[JobEnqueuer, Depends(get_job_enqueuer)],
) -> QueuedJob:
    if body.dry_run:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use the local CLI for dry-run")
    return enqueue_job(
        enqueuer,
        queue="intelligence_translation",
        actor="translate_batch",
        payload=body.model_dump(mode="json", by_alias=True, exclude={"dry_run"}),
    )


@router.post("/reconcile", response_model=TranslationReconciliationResult)
async def reconcile_translations(
    body: TranslationReconciliationRequest,
    _: RequiredAdmin,
    service: Annotated[
        TranslationCoverageReconciliationService, Depends(get_reconciliation_service)
    ],
) -> TranslationReconciliationResult:
    if not body.dry_run and not service.queue_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Translation queue is not configured"
        )
    return await service.reconcile(body)
