import logging

import dramatiq
from ai_business_radar_api.infrastructure.ai import default_prompt_version
from ai_business_radar_api.infrastructure.queue import JobEnqueuer
from ai_business_radar_api.services.signal_extraction import (
    BusinessSignalExtractionService,
    SignalBatchRequest,
)
from ai_business_radar_api.services.translation_orchestration import (
    TranslationCoverageReconciliationService,
)

from ..config import WorkerSettings
from ..lifecycle import signal_extraction_dependencies
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_signal_extraction(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    request = SignalBatchRequest.model_validate(payload)
    async with signal_extraction_dependencies(runtime) as (sessions, ai_client):
        redis_url = getattr(runtime, "redis_url", None)
        translation = TranslationCoverageReconciliationService(
            sessions, JobEnqueuer(redis_url.get_secret_value()) if redis_url else None
        )
        return await BusinessSignalExtractionService(
            sessions,
            ai_client,
            provider=runtime.ai_provider or "",
            model=runtime.ai_model_signal_extraction or "",
            prompt_version=getattr(
                runtime,
                "signal_extractor_prompt_version",
                default_prompt_version("signal-extractor"),
            ),
            translation_orchestrator=translation,
        ).extract_batch(request)


@dramatiq.actor(queue_name="ai_extraction", max_retries=2, min_backoff=5000)
def run_signal_extraction(**payload):
    result = run_async(lambda: execute_signal_extraction(payload))
    logger.info("signal_extraction_actor_finished status=%s", type(result).__name__)
