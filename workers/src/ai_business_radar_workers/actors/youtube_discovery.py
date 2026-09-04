import logging
from datetime import datetime
from uuid import UUID

import dramatiq
from ai_business_radar_api.services.youtube_discovery import (
    DiscoveryRequest,
    YouTubeDiscoveryService,
)

from ..config import WorkerSettings
from ..lifecycle import collection_dependencies
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_discovery(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    request = DiscoveryRequest(
        search_query_id=UUID(payload["search_query_id"]),
        max_pages=payload.get("max_pages", 1),
        max_results=payload.get("max_results", 50),
        order=payload.get("order", "date"),
        published_after=(
            datetime.fromisoformat(payload["published_after"])
            if payload.get("published_after")
            else None
        ),
    )
    async with collection_dependencies(runtime) as (sessions, youtube):
        return await YouTubeDiscoveryService(
            sessions,
            youtube,
            max_quota_units_per_run=runtime.youtube_discovery_max_quota_units_per_run,
        ).discover(request)


@dramatiq.actor(queue_name="youtube_discovery", max_retries=2, min_backoff=5000)
def run_youtube_discovery(**payload):
    result = run_async(lambda: execute_discovery(payload))
    logger.info(
        "youtube_discovery_actor_finished status=%s", getattr(result, "status", "permanent_error")
    )
