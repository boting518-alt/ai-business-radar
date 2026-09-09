"""Bounded business-case worker; transport retries never repeat a completed provider call."""

from uuid import UUID

import dramatiq
from ai_business_radar_api.services.opportunity_consolidation import OpportunityConsolidationService

from ..config import WorkerSettings
from ..lifecycle import opportunity_normalization_dependencies
from .runtime import run_async


async def execute_consolidation(consolidation_id: str, settings=None):
    runtime = settings or WorkerSettings()
    # Reuse the configured intelligence model/client without changing normalizer behavior.
    async with opportunity_normalization_dependencies(runtime) as (sessions, ai):
        return await OpportunityConsolidationService(sessions).execute(
            UUID(consolidation_id),
            ai,
            provider=runtime.ai_provider,
            model=runtime.ai_model_opportunity_normalization,
        )


@dramatiq.actor(queue_name="opportunity_consolidation", max_retries=2, min_backoff=5000)
def consolidate_opportunity(consolidation_id: str):
    return run_async(lambda: execute_consolidation(consolidation_id))
