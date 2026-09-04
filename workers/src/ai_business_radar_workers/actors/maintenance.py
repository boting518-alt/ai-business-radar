import logging

import dramatiq
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.services.stale_claims import StaleClaimRecoveryService

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
