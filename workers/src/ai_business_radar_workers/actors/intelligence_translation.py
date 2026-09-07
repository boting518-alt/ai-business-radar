import logging

import dramatiq
from ai_business_radar_api.services.intelligence_translation import (
    IntelligenceTranslationService,
    TranslationBatchRequest,
    TranslationRequest,
)

from ..config import WorkerSettings
from ..lifecycle import intelligence_translation_dependencies
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_entity_translation(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    request = TranslationRequest.model_validate(payload)
    async with intelligence_translation_dependencies(runtime) as (sessions, ai_client):
        return await IntelligenceTranslationService(
            sessions,
            ai_client,
            provider=runtime.ai_provider or "",
            model=runtime.intelligence_translation_model or "",
        ).translate_entity(request)


async def execute_batch_translation(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    request = TranslationBatchRequest.model_validate(payload)
    async with intelligence_translation_dependencies(runtime) as (sessions, ai_client):
        return await IntelligenceTranslationService(
            sessions,
            ai_client,
            provider=runtime.ai_provider or "",
            model=runtime.intelligence_translation_model or "",
        ).translate_batch(request)


@dramatiq.actor(queue_name="intelligence_translation", max_retries=2, min_backoff=5000)
def translate_signal(**payload):
    payload["entity_type"] = "signal"
    result = run_async(lambda: execute_entity_translation(payload))
    logger.info(
        "translation_actor_finished actor=translate_signal status=%s", type(result).__name__
    )


@dramatiq.actor(queue_name="intelligence_translation", max_retries=2, min_backoff=5000)
def translate_opportunity(**payload):
    payload["entity_type"] = "opportunity"
    result = run_async(lambda: execute_entity_translation(payload))
    logger.info(
        "translation_actor_finished actor=translate_opportunity status=%s", type(result).__name__
    )


@dramatiq.actor(queue_name="intelligence_translation", max_retries=2, min_backoff=5000)
def translate_batch(**payload):
    result = run_async(lambda: execute_batch_translation(payload))
    logger.info("translation_actor_finished actor=translate_batch status=%s", type(result).__name__)
