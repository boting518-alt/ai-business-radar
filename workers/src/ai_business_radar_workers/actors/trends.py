import logging

import dramatiq
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.services.trend_aggregation import (
    OpportunityTrendAggregationService,
    TrendAggregationBatchRequest,
    TrendAggregationRequest,
)

from ..config import WorkerSettings
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_trend_aggregation(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    engine = create_database_engine(runtime.database_url.get_secret_value())
    try:
        service = OpportunityTrendAggregationService(create_session_factory(engine))
        if payload.get("opportunity_id"):
            return await service.aggregate(TrendAggregationRequest.model_validate(payload))
        return await service.aggregate_batch(TrendAggregationBatchRequest.model_validate(payload))
    finally:
        await engine.dispose()


@dramatiq.actor(queue_name="aggregation", max_retries=2, min_backoff=5000)
def run_trend_aggregation(**payload):
    result = run_async(lambda: execute_trend_aggregation(payload))
    logger.info("trend_aggregation_actor_finished status=%s", type(result).__name__)
