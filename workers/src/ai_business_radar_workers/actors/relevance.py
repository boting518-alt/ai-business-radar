import logging

import dramatiq
from ai_business_radar_api.services.relevance_filter import (
    RelevanceBatchRequest,
    VideoRelevanceService,
)

from ..config import WorkerSettings
from ..lifecycle import relevance_dependencies
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_relevance(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    request = RelevanceBatchRequest.model_validate(payload)
    async with relevance_dependencies(runtime) as (sessions, ai_client):
        return await VideoRelevanceService(
            sessions,
            ai_client,
            provider=runtime.ai_provider or "",
            model=runtime.ai_model_relevance or "",
        ).analyze_batch(request)


@dramatiq.actor(queue_name="ai_relevance", max_retries=2, min_backoff=5000)
def run_relevance_filter(**payload):
    result = run_async(lambda: execute_relevance(payload))
    logger.info("ai_relevance_actor_finished status=%s", type(result).__name__)
