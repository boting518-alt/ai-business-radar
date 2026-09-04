import logging
from uuid import UUID

import dramatiq
from ai_business_radar_api.services.youtube_metadata import (
    MetadataCollectionRequest,
    YouTubeMetadataCollectionService,
)

from ..config import WorkerSettings
from ..lifecycle import collection_dependencies
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_metadata(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    request = MetadataCollectionRequest(
        collection_run_id=(
            UUID(payload["collection_run_id"]) if payload.get("collection_run_id") else None
        ),
        limit=payload.get("limit", runtime.youtube_metadata_batch_size),
        include_snapshots=payload.get("include_snapshots", True),
    )
    async with collection_dependencies(runtime) as (sessions, youtube):
        return await YouTubeMetadataCollectionService(sessions, youtube).collect(request)


@dramatiq.actor(queue_name="youtube_metadata", max_retries=2, min_backoff=5000)
def run_youtube_metadata_collection(**payload):
    result = run_async(lambda: execute_metadata(payload))
    logger.info(
        "youtube_metadata_actor_finished status=%s", getattr(result, "status", "permanent_error")
    )
