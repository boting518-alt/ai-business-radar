import logging
from uuid import UUID

import dramatiq
from ai_business_radar_api.services.relevance_filter import (
    RelevanceBatchRequest,
    VideoRelevanceService,
)

from ..config import WorkerSettings
from ..discovery_pipeline import relevance_completed
from ..lifecycle import relevance_dependencies
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_relevance(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    request = RelevanceBatchRequest(
        limit=payload.get("limit", 20),
        force=payload.get("force", False),
        video_ids=[UUID(value) for value in payload.get("video_ids", [])] or None,
    )
    async with relevance_dependencies(runtime) as (sessions, ai_client):
        result = await VideoRelevanceService(
            sessions,
            ai_client,
            provider=runtime.ai_provider or "",
            model=runtime.ai_model_relevance or "",
        ).analyze_batch(request)
    if payload.get("topic_run_id"):
        await relevance_completed(UUID(payload["topic_run_id"]), result, runtime)
    return result


@dramatiq.actor(
    queue_name="ai_relevance",
    max_retries=2,
    min_backoff=5000,
    on_retry_exhausted="finalize_discovery_pipeline_retry_exhausted",
)
def run_relevance_filter(**payload):
    result = run_async(lambda: execute_relevance(payload))
    logger.info("ai_relevance_actor_finished status=%s", type(result).__name__)
