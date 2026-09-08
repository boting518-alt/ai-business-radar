import logging
from uuid import UUID

import dramatiq
from ai_business_radar_api.services.youtube_comments import (
    CommentCollectionRequest,
    YouTubeCommentCollectionService,
)

from ..config import WorkerSettings
from ..discovery_pipeline import comments_completed
from ..lifecycle import collection_dependencies
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_comments(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    request = CommentCollectionRequest(
        video_ids=[UUID(value) for value in payload["video_ids"]]
        if payload.get("video_ids")
        else None,
        limit_videos=payload.get("limit_videos", runtime.youtube_comment_batch_size),
        max_pages_per_video=payload.get("max_pages_per_video", 1),
        max_comments_per_video=payload.get("max_comments_per_video", 100),
        order=payload.get("order", "relevance"),
    )
    async with collection_dependencies(runtime) as (sessions, youtube):
        result = await YouTubeCommentCollectionService(
            sessions,
            youtube,
            max_quota_units_per_run=runtime.youtube_comment_max_quota_units_per_run,
        ).collect(request)
    if payload.get("topic_run_id"):
        await comments_completed(UUID(payload["topic_run_id"]), result, runtime)
    return result


@dramatiq.actor(
    queue_name="youtube_comments",
    max_retries=2,
    min_backoff=5000,
    on_retry_exhausted="finalize_discovery_pipeline_retry_exhausted",
)
def run_youtube_comment_collection(**payload):
    result = run_async(lambda: execute_comments(payload))
    logger.info(
        "youtube_comments_actor_finished status=%s", getattr(result, "status", "permanent_error")
    )
