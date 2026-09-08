import logging

import dramatiq
from ai_business_radar_api.infrastructure.queue import JobEnqueuer
from ai_business_radar_api.services.opportunity_normalization import (
    OpportunityNormalizationBatchRequest,
    OpportunityNormalizationService,
)
from ai_business_radar_api.services.translation_orchestration import (
    TranslationCoverageReconciliationService,
)

from ..config import WorkerSettings
from ..lifecycle import opportunity_normalization_dependencies
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_opportunity_normalization(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    request = OpportunityNormalizationBatchRequest.model_validate(payload)
    async with opportunity_normalization_dependencies(runtime) as (sessions, ai_client):
        redis_url = getattr(runtime, "redis_url", None)
        translation = TranslationCoverageReconciliationService(
            sessions, JobEnqueuer(redis_url.get_secret_value()) if redis_url else None
        )
        return await OpportunityNormalizationService(
            sessions,
            ai_client,
            provider=runtime.ai_provider or "",
            model=runtime.ai_model_opportunity_normalization or "",
            match_threshold=runtime.ai_opportunity_match_threshold,
            create_threshold=runtime.ai_opportunity_create_threshold,
            translation_orchestrator=translation,
        ).normalize_batch(request)


@dramatiq.actor(queue_name="ai_extraction", max_retries=2, min_backoff=5000)
def run_opportunity_normalization(**payload):
    result = run_async(lambda: execute_opportunity_normalization(payload))
    logger.info("opportunity_normalization_actor_finished status=%s", type(result).__name__)
