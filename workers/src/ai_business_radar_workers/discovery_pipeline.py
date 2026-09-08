"""Durable, stage-by-stage orchestration for one Discovery Topic execution."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

import dramatiq
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    CollectionRun,
    Comment,
    DiscoveryTopic,
    DiscoveryTopicRun,
    Signal,
    Video,
    YouTubeDiscoveryItem,
)
from ai_business_radar_api.infrastructure.queue import JobEnqueuer, QueueUnavailableError
from sqlalchemy import distinct, func, select, update

from .config import WorkerSettings

logger = logging.getLogger(__name__)

PIPELINE_ACTORS = {
    "run_youtube_metadata_collection": "metadata",
    "run_youtube_comment_collection": "comments",
    "run_relevance_filter": "relevance",
    "run_signal_extraction": "signal_extraction",
    "run_comment_pain_mining": "comment_pain",
    "run_opportunity_normalization": "opportunity_normalization",
}


def _queue(settings: WorkerSettings, queue: str, actor: str, payload: dict) -> str:
    message_id = JobEnqueuer(settings.redis_url.get_secret_value()).enqueue(
        queue=queue, actor=actor, payload=payload
    )
    logger.info(
        "%s topic_run_id=%s stage=%s status=queued message_id=%s",
        f"{actor.removeprefix('run_')}_enqueued",
        payload.get("topic_run_id"),
        actor,
        message_id,
    )
    return message_id


async def start_pipeline(
    topic_run_id: UUID, settings: WorkerSettings, *, batch_limit: int = 250
) -> bool:
    engine = create_database_engine(settings.database_url.get_secret_value())
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            batch = await session.get(DiscoveryTopicRun, topic_run_id, with_for_update=True)
            if batch is None or batch.status in {"queued", "running"}:
                return False
            if batch.intelligence_status != "not_started":
                return False
            topic = await session.get(DiscoveryTopic, batch.topic_id)
            base = (
                select(YouTubeDiscoveryItem)
                .join(CollectionRun, CollectionRun.id == YouTubeDiscoveryItem.collection_run_id)
                .where(CollectionRun.topic_run_id == topic_run_id)
            )
            result_count = await session.scalar(select(func.count()).select_from(base.subquery()))
            unique_count = await session.scalar(
                select(func.count(distinct(YouTubeDiscoveryItem.youtube_video_id)))
                .join(CollectionRun, CollectionRun.id == YouTubeDiscoveryItem.collection_run_id)
                .where(CollectionRun.topic_run_id == topic_run_id)
            )
            new_count = await session.scalar(
                select(func.count(distinct(YouTubeDiscoveryItem.youtube_video_id)))
                .join(CollectionRun, CollectionRun.id == YouTubeDiscoveryItem.collection_run_id)
                .outerjoin(
                    Video,
                    Video.youtube_video_id == YouTubeDiscoveryItem.youtube_video_id,
                )
                .where(CollectionRun.topic_run_id == topic_run_id, Video.id.is_(None))
            )
            items = list(await session.scalars(base))
            external_ids = {item.youtube_video_id for item in items}
            known_videos = {
                video.youtube_video_id: video.id
                for video in await session.scalars(
                    select(Video).where(Video.youtube_video_id.in_(external_ids))
                )
            }
            now = datetime.now(UTC)
            for item in items:
                canonical_id = known_videos.get(item.youtube_video_id)
                if canonical_id is not None:
                    item.canonical_video_id = canonical_id
                    item.processing_status = "processed"
                    item.claimed_at = None
                    item.processed_at = now
                    item.error_summary = None
            batch.intelligence_status = "queued"
            batch.intelligence_started_at = datetime.now(UTC)
            batch.intelligence_metrics = {
                "discovery_results": result_count or 0,
                "unique_videos": unique_count or 0,
                "new_videos": new_count or 0,
                "metadata_completed": 0,
                "comments_completed": 0,
                "relevance_completed": 0,
                "relevant_videos": 0,
                "irrelevant_videos": 0,
                "signals_created": 0,
                "opportunity_candidates_created": 0,
                "failed_stages": 0,
                "video_normalization_done": False,
                "comment_normalization_done": False,
            }
            max_comments = topic.default_max_comments_per_video
        if not unique_count:
            await _finish_if_ready(factory, topic_run_id, force=True)
            return True
        pending = await _pending_discovery_count(topic_run_id, settings)
        if not pending:
            await metadata_completed(
                topic_run_id,
                type("ReusedMetadata", (), {"status": "completed"})(),
                {"max_comments_per_video": max_comments},
                settings,
            )
            return True
        try:
            _queue(
                settings,
                "youtube_metadata",
                "run_youtube_metadata_collection",
                {
                    "topic_run_id": str(topic_run_id),
                    "limit": min(pending, batch_limit),
                    "include_snapshots": True,
                    "max_comments_per_video": max_comments,
                },
            )
        except QueueUnavailableError:
            await fail_pipeline(topic_run_id, settings, "metadata queue unavailable")
            return False
        logger.info(
            "discovery_pipeline_started topic_run_id=%s unique_videos=%s new_videos=%s",
            topic_run_id,
            unique_count,
            new_count,
        )
        return True
    finally:
        await engine.dispose()


async def resume_pipeline(
    topic_run_id: UUID, settings: WorkerSettings, *, batch_limit: int = 50
) -> bool:
    """Re-open one bounded terminal pipeline; immutable stage results remain reusable."""
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        async with create_session_factory(engine)() as session, session.begin():
            batch = await session.get(DiscoveryTopicRun, topic_run_id, with_for_update=True)
            if batch is None or batch.status in {"queued", "running"}:
                return False
            if batch.intelligence_status in {"queued", "processing"}:
                return False
            batch.intelligence_status = "not_started"
            batch.intelligence_error_summary = None
            batch.intelligence_completed_at = None
            await session.execute(
                update(YouTubeDiscoveryItem)
                .where(
                    YouTubeDiscoveryItem.collection_run_id.in_(
                        select(CollectionRun.id).where(CollectionRun.topic_run_id == topic_run_id)
                    ),
                    YouTubeDiscoveryItem.processing_status == "failed",
                )
                .values(processing_status="pending", claimed_at=None, error_summary=None)
            )
    finally:
        await engine.dispose()
    return await start_pipeline(topic_run_id, settings, batch_limit=batch_limit)


async def canonical_video_ids(topic_run_id: UUID, settings: WorkerSettings) -> list[UUID]:
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        async with create_session_factory(engine)() as session:
            return list(
                await session.scalars(
                    select(distinct(YouTubeDiscoveryItem.canonical_video_id))
                    .join(CollectionRun, CollectionRun.id == YouTubeDiscoveryItem.collection_run_id)
                    .where(
                        CollectionRun.topic_run_id == topic_run_id,
                        YouTubeDiscoveryItem.canonical_video_id.is_not(None),
                    )
                )
            )
    finally:
        await engine.dispose()


async def metadata_completed(topic_run_id: UUID, result, payload: dict, settings: WorkerSettings):
    remaining = await _pending_discovery_count(topic_run_id, settings)
    video_ids = await canonical_video_ids(topic_run_id, settings)
    await update_metrics(
        topic_run_id,
        settings,
        metadata_completed=len(video_ids),
        failed_stages=int(result.status != "completed"),
    )
    if remaining:
        _queue(
            settings,
            "youtube_metadata",
            "run_youtube_metadata_collection",
            {
                "topic_run_id": str(topic_run_id),
                "limit": min(remaining, 250),
                "include_snapshots": True,
                "max_comments_per_video": payload.get("max_comments_per_video", 100),
            },
        )
        return
    if not video_ids:
        await fail_pipeline(topic_run_id, settings, "metadata_produced_no_eligible_videos")
        return
    comment_video_ids = await _comment_eligible_video_ids(topic_run_id, settings)
    if comment_video_ids and payload.get("max_comments_per_video", 100) > 0:
        _queue(
            settings,
            "youtube_comments",
            "run_youtube_comment_collection",
            {
                "topic_run_id": str(topic_run_id),
                "video_ids": [str(value) for value in comment_video_ids],
                "limit_videos": len(comment_video_ids),
                "max_pages_per_video": 1,
                "max_comments_per_video": payload.get("max_comments_per_video", 100),
            },
        )
    else:
        await comments_completed(
            topic_run_id,
            type(
                "SkippedComments",
                (),
                {"videos_completed": 0, "status": "completed"},
            )(),
            settings,
        )


async def comments_completed(topic_run_id: UUID, result, settings: WorkerSettings):
    video_ids = await canonical_video_ids(topic_run_id, settings)
    await update_metrics(
        topic_run_id,
        settings,
        comments_completed=result.videos_completed,
        failed_stages=int(result.status != "completed"),
    )
    _queue(
        settings,
        "ai_relevance",
        "run_relevance_filter",
        {
            "topic_run_id": str(topic_run_id),
            "video_ids": [str(v) for v in video_ids],
            "limit": min(len(video_ids), 100),
        },
    )
    comment_ids = await _comment_ids(topic_run_id, settings, 200)
    if comment_ids:
        _queue(
            settings,
            "ai_extraction",
            "run_comment_pain_mining",
            {
                "topic_run_id": str(topic_run_id),
                "comment_ids": [str(v) for v in comment_ids],
                "limit": len(comment_ids),
                "pipeline_branch": "comment",
            },
        )
    else:
        await update_metrics(topic_run_id, settings, comment_normalization_done=True)


async def relevance_completed(topic_run_id: UUID, result, settings: WorkerSettings):
    relevant_ids = [item.video_id for item in result.items if item.relevant is True]
    await update_metrics(
        topic_run_id,
        settings,
        relevance_completed=result.processed,
        relevant_videos=result.relevant,
        irrelevant_videos=result.irrelevant,
        failed_stages=int(result.failed > 0),
    )
    if relevant_ids:
        _queue(
            settings,
            "ai_extraction",
            "run_signal_extraction",
            {
                "topic_run_id": str(topic_run_id),
                "video_ids": [str(v) for v in relevant_ids],
                "limit": len(relevant_ids),
                "pipeline_branch": "video",
            },
        )
    else:
        await update_metrics(topic_run_id, settings, video_normalization_done=True)
        await finish_if_ready(topic_run_id, settings)


async def extraction_completed(topic_run_id: UUID, result, branch: str, settings: WorkerSettings):
    extraction_ids = [item.extraction_id for item in result.items if item.extraction_id]
    signal_ids = await _signal_ids(extraction_ids, settings)
    await update_metrics(
        topic_run_id,
        settings,
        signals_created_delta=sum(item.signals_created for item in result.items if not item.reused),
        failed_stages=int(result.failed > 0),
    )
    if signal_ids:
        _queue(
            settings,
            "ai_extraction",
            "run_opportunity_normalization",
            {
                "topic_run_id": str(topic_run_id),
                "signal_ids": [str(v) for v in signal_ids],
                "limit": len(signal_ids),
                "pipeline_branch": branch,
            },
        )
    else:
        await update_metrics(topic_run_id, settings, **{f"{branch}_normalization_done": True})
        await finish_if_ready(topic_run_id, settings)


async def normalization_completed(
    topic_run_id: UUID, result, branch: str, settings: WorkerSettings
):
    await update_metrics(
        topic_run_id,
        settings,
        opportunity_candidates_created_delta=result.created,
        failed_stages=int(result.failed > 0),
        **{f"{branch}_normalization_done": True},
    )
    await finish_if_ready(topic_run_id, settings)


async def update_metrics(topic_run_id: UUID, settings: WorkerSettings, **values) -> None:
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        async with create_session_factory(engine)() as session, session.begin():
            batch = await session.get(DiscoveryTopicRun, topic_run_id, with_for_update=True)
            metrics = dict(batch.intelligence_metrics or {})
            for key, value in values.items():
                if key.endswith("_delta"):
                    target = key.removesuffix("_delta")
                    metrics[target] = metrics.get(target, 0) + value
                elif key == "failed_stages":
                    metrics[key] = metrics.get(key, 0) + value
                else:
                    metrics[key] = value
            batch.intelligence_metrics = metrics
            batch.intelligence_status = "processing"
    finally:
        await engine.dispose()


async def finish_if_ready(topic_run_id: UUID, settings: WorkerSettings) -> None:
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        await _finish_if_ready(create_session_factory(engine), topic_run_id)
    finally:
        await engine.dispose()


async def _finish_if_ready(factory, topic_run_id: UUID, force: bool = False) -> None:
    async with factory() as session, session.begin():
        batch = await session.get(DiscoveryTopicRun, topic_run_id, with_for_update=True)
        metrics = batch.intelligence_metrics or {}
        if force or (
            metrics.get("video_normalization_done") and metrics.get("comment_normalization_done")
        ):
            batch.intelligence_status = "partial" if metrics.get("failed_stages") else "completed"
            batch.intelligence_completed_at = datetime.now(UTC)
            logger.info(
                "pipeline_video_completed topic_run_id=%s status=%s "
                "signals_created=%s opportunities_created=%s",
                topic_run_id,
                batch.intelligence_status,
                metrics.get("signals_created", 0),
                metrics.get("opportunity_candidates_created", 0),
            )


async def fail_pipeline(topic_run_id: UUID, settings: WorkerSettings, message: str) -> None:
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        async with create_session_factory(engine)() as session, session.begin():
            batch = await session.get(DiscoveryTopicRun, topic_run_id, with_for_update=True)
            batch.intelligence_status = "failed"
            batch.intelligence_error_summary = message[:500]
            batch.intelligence_completed_at = datetime.now(UTC)
            logger.error(
                "discovery_pipeline_failed topic_run_id=%s error=%s",
                topic_run_id,
                batch.intelligence_error_summary,
            )
    finally:
        await engine.dispose()


async def _comment_ids(topic_run_id: UUID, settings: WorkerSettings, limit: int) -> list[UUID]:
    video_ids = await canonical_video_ids(topic_run_id, settings)
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        async with create_session_factory(engine)() as session:
            return list(
                await session.scalars(
                    select(Comment.id)
                    .where(Comment.video_id.in_(video_ids))
                    .order_by(Comment.created_at)
                    .limit(limit)
                )
            )
    finally:
        await engine.dispose()


async def _comment_eligible_video_ids(topic_run_id: UUID, settings: WorkerSettings) -> list[UUID]:
    video_ids = await canonical_video_ids(topic_run_id, settings)
    if not video_ids:
        return []
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        async with create_session_factory(engine)() as session:
            has_comment = select(Comment.id).where(Comment.video_id == Video.id).exists()
            return list(
                await session.scalars(
                    select(Video.id).where(
                        Video.id.in_(video_ids),
                        (Video.processing_status == "new") | ~has_comment,
                    )
                )
            )
    finally:
        await engine.dispose()


async def _signal_ids(extraction_ids: list[UUID], settings: WorkerSettings) -> list[UUID]:
    if not extraction_ids:
        return []
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        async with create_session_factory(engine)() as session:
            return list(
                await session.scalars(
                    select(Signal.id).where(
                        Signal.ai_extraction_id.in_(extraction_ids),
                        Signal.status == "review",
                    )
                )
            )
    finally:
        await engine.dispose()


async def _pending_discovery_count(topic_run_id: UUID, settings: WorkerSettings) -> int:
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        async with create_session_factory(engine)() as session:
            value = await session.scalar(
                select(func.count(YouTubeDiscoveryItem.id))
                .join(CollectionRun, CollectionRun.id == YouTubeDiscoveryItem.collection_run_id)
                .where(
                    CollectionRun.topic_run_id == topic_run_id,
                    YouTubeDiscoveryItem.processing_status == "pending",
                )
            )
            return value or 0
    finally:
        await engine.dispose()


async def _record_retry_exhausted(original_message: dict) -> None:
    payload = original_message.get("kwargs", {})
    topic_run_id = payload.get("topic_run_id")
    if not topic_run_id:
        return
    actor_name = original_message.get("actor_name", "unknown")
    stage = PIPELINE_ACTORS.get(actor_name, actor_name)
    await fail_pipeline(
        UUID(topic_run_id),
        WorkerSettings(),
        f"{stage} retries exhausted",
    )


@dramatiq.actor(queue_name="maintenance", max_retries=0)
def finalize_discovery_pipeline_retry_exhausted(
    original_message: dict, _retry_metadata: dict
) -> None:
    asyncio.run(_record_retry_exhausted(original_message))
