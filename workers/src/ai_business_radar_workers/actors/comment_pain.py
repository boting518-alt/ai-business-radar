import logging
from uuid import UUID

import dramatiq
from ai_business_radar_api.infrastructure.queue import JobEnqueuer
from ai_business_radar_api.services.comment_pain_mining import (
    CommentPainBatchRequest,
    CommentPainMiningService,
)
from ai_business_radar_api.services.translation_orchestration import (
    TranslationCoverageReconciliationService,
)

from ..config import WorkerSettings
from ..discovery_pipeline import extraction_completed
from ..lifecycle import comment_pain_dependencies
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_comment_pain(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    request = CommentPainBatchRequest(
        limit=payload.get("limit", 50),
        force=payload.get("force", False),
        comment_ids=[UUID(value) for value in payload.get("comment_ids", [])] or None,
    )
    async with comment_pain_dependencies(runtime) as (sessions, ai_client):
        redis_url = getattr(runtime, "redis_url", None)
        translation = TranslationCoverageReconciliationService(
            sessions, JobEnqueuer(redis_url.get_secret_value()) if redis_url else None
        )
        result = await CommentPainMiningService(
            sessions,
            ai_client,
            provider=runtime.ai_provider or "",
            model=runtime.ai_model_comment_pain_mining or "",
            translation_orchestrator=translation,
        ).mine_batch(request)
    if payload.get("topic_run_id"):
        await extraction_completed(
            UUID(payload["topic_run_id"]),
            result,
            payload.get("pipeline_branch", "comment"),
            runtime,
        )
    return result


@dramatiq.actor(
    queue_name="ai_extraction",
    max_retries=2,
    min_backoff=5000,
    on_retry_exhausted="finalize_discovery_pipeline_retry_exhausted",
)
def run_comment_pain_mining(**payload):
    result = run_async(lambda: execute_comment_pain(payload))
    logger.info("comment_pain_actor_finished status=%s", type(result).__name__)
