import logging

import dramatiq
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.queue import JobEnqueuer
from ai_business_radar_api.services.discovery_operations import (
    DiscoveryOperationsService,
    StaleRunRecoveryRequest,
)
from ai_business_radar_api.services.stale_claims import StaleClaimRecoveryService
from ai_business_radar_api.services.translation_orchestration import (
    TranslationCoverageReconciliationService,
    TranslationReconciliationRequest,
)

from ..config import WorkerSettings
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_recovery(payload: dict, settings: WorkerSettings | None = None) -> int:
    runtime = settings or WorkerSettings()
    engine = create_database_engine(runtime.database_url.get_secret_value())
    try:
        recovered = await StaleClaimRecoveryService(create_session_factory(engine)).recover(
            timeout_minutes=payload.get(
                "timeout_minutes", runtime.youtube_staging_claim_timeout_minutes
            ),
            limit=payload.get("limit", runtime.youtube_staging_recovery_batch_size),
        )
        logger.info("stale_collection_claims_recovered count=%s", recovered)
        return recovered
    finally:
        await engine.dispose()


@dramatiq.actor(queue_name="maintenance", max_retries=2, min_backoff=5000)
def recover_stale_collection_claims(**payload):
    run_async(lambda: execute_recovery(payload))


async def execute_discovery_run_recovery(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    engine = create_database_engine(runtime.database_url.get_secret_value())
    try:
        return await DiscoveryOperationsService(create_session_factory(engine)).recover_stale(
            StaleRunRecoveryRequest(dry_run=False, limit=payload.get("limit", 100))
        )
    finally:
        await engine.dispose()


@dramatiq.actor(queue_name="maintenance", max_retries=2, min_backoff=5000)
def recover_stale_discovery_runs(**payload):
    run_async(lambda: execute_discovery_run_recovery(payload))


async def execute_translation_reconciliation(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    engine = create_database_engine(runtime.database_url.get_secret_value())
    try:
        service = TranslationCoverageReconciliationService(
            create_session_factory(engine), JobEnqueuer(runtime.redis_url.get_secret_value())
        )
        return await service.reconcile(
            TranslationReconciliationRequest(
                locale="zh-CN",
                limit=payload.get("limit", runtime.translation_reconciliation_batch_size),
            )
        )
    finally:
        await engine.dispose()


@dramatiq.actor(queue_name="maintenance", max_retries=2, min_backoff=5000)
def reconcile_translation_coverage(**payload):
    result = run_async(lambda: execute_translation_reconciliation(payload))
    logger.info("translation_reconciliation_actor_finished status=%s", type(result).__name__)
