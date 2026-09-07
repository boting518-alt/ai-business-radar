"""Admin-only enqueue boundaries for persisted intelligence translations."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ...infrastructure.auth import RequiredAdmin
from ...infrastructure.queue import JobEnqueuer, QueuedJob
from ...services.intelligence_translation import TranslationBatchRequest, TranslationRequest
from .youtube_discovery import enqueue_job, get_job_enqueuer

router = APIRouter(prefix="/admin/localization", tags=["admin", "localization"])


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
