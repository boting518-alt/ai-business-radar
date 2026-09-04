import logging

import dramatiq
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.services.opportunity_scoring import (
    OpportunityScoringService,
    ScoringBatchRequest,
)

from ..config import WorkerSettings
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_opportunity_scoring(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    engine = create_database_engine(runtime.database_url.get_secret_value())
    try:
        return await OpportunityScoringService(create_session_factory(engine)).score_batch(
            ScoringBatchRequest.model_validate(payload)
        )
    finally:
        await engine.dispose()


@dramatiq.actor(queue_name="aggregation", max_retries=2, min_backoff=5000)
def run_opportunity_scoring(**payload):
    result = run_async(lambda: execute_opportunity_scoring(payload))
    logger.info("opportunity_scoring_actor_finished status=%s", type(result).__name__)
