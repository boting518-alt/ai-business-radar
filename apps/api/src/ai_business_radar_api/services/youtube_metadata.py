"""Canonical YouTube metadata and snapshot collection orchestration."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.database.repositories import (
    ChannelRepository,
    CollectionRunRepository,
    VideoRepository,
    YouTubeDiscoveryItemRepository,
)
from ..infrastructure.external.youtube import YouTubeAPIError, YouTubeClient
from ..infrastructure.external.youtube.models import YouTubeChannel, YouTubeVideo

logger = logging.getLogger(__name__)
MetadataStatus = Literal["completed", "partial", "failed"]


class MetadataCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_run_id: UUID | None = None
    topic_run_id: UUID | None = None
    limit: int = Field(default=50, ge=1, le=250)
    include_snapshots: bool = True


class MetadataCollectionResult(BaseModel):
    collection_run_id: UUID
    items_claimed: int
    items_processed: int
    items_failed: int
    videos_requested: int
    videos_returned: int
    channels_requested: int
    channels_returned: int
    snapshots_created: int
    estimated_quota_units: int
    status: MetadataStatus
    reason: str | None = None
    started_at: datetime
    finished_at: datetime


class YouTubeMetadataCollectionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        youtube: YouTubeClient,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._youtube = youtube
        self._clock = clock or (lambda: datetime.now(UTC))

    async def collect(self, request: MetadataCollectionRequest) -> MetadataCollectionResult:
        started_at = self._clock()
        run_id, items = await self._start_and_claim(request, started_at)
        item_ids = [item.id for item in items]
        video_ids = list(dict.fromkeys(item.youtube_video_id for item in items))
        if not items:
            return await self._finish(
                run_id,
                started_at,
                claimed=0,
                processed=0,
                failed=0,
                videos_requested=0,
                videos_returned=0,
                channels_requested=0,
                channels_returned=0,
                snapshots_created=0,
                quota=0,
            )

        try:
            videos = await self._youtube.get_videos(video_ids)
        except YouTubeAPIError:
            await self._release(item_ids)
            return await self._finish(
                run_id,
                started_at,
                claimed=len(items),
                processed=0,
                failed=0,
                videos_requested=len(video_ids),
                videos_returned=0,
                channels_requested=0,
                channels_returned=0,
                snapshots_created=0,
                quota=self._batch_count(len(video_ids)),
                status="failed",
                reason="youtube_videos_request_failed",
                error_summary="youtube_request_failed",
            )

        videos_by_id = {video.youtube_video_id: video for video in videos}
        channel_ids = list(dict.fromkeys(video.youtube_channel_id for video in videos))
        quota = self._batch_count(len(video_ids))
        try:
            channels = await self._youtube.get_channels(channel_ids) if channel_ids else []
        except YouTubeAPIError:
            await self._release(item_ids)
            return await self._finish(
                run_id,
                started_at,
                claimed=len(items),
                processed=0,
                failed=0,
                videos_requested=len(video_ids),
                videos_returned=len(videos_by_id),
                channels_requested=len(channel_ids),
                channels_returned=0,
                snapshots_created=0,
                quota=quota + self._batch_count(len(channel_ids)),
                status="failed",
                reason="youtube_channels_request_failed",
                error_summary="youtube_request_failed",
            )

        channels_by_id = {channel.youtube_channel_id: channel for channel in channels}
        captured_at = self._clock()
        processed, failed, snapshots = await self._persist(
            items, videos_by_id, channels_by_id, captured_at, request.include_snapshots
        )
        status: MetadataStatus = (
            "completed" if failed == 0 else ("partial" if processed else "failed")
        )
        return await self._finish(
            run_id,
            started_at,
            claimed=len(items),
            processed=processed,
            failed=failed,
            videos_requested=len(video_ids),
            videos_returned=len(videos_by_id),
            channels_requested=len(channel_ids),
            channels_returned=len(channels_by_id),
            snapshots_created=snapshots,
            quota=quota + self._batch_count(len(channel_ids)),
            status=status,
            reason="items_unavailable" if failed else None,
            error_summary="metadata_items_failed" if failed else None,
        )

    async def _start_and_claim(self, request: MetadataCollectionRequest, started_at: datetime):
        metadata = self._metadata(0, 0, 0, 0, 0, 0)
        async with self._sessions() as session, session.begin():
            run = await CollectionRunRepository(session).create_run(
                None, metadata, run_type="metadata_collection"
            )
            await CollectionRunRepository(session).mark_running(run.id, started_at)
            items = await YouTubeDiscoveryItemRepository(session).claim_pending(
                limit=request.limit,
                claimed_at=started_at,
                collection_run_id=request.collection_run_id,
                topic_run_id=request.topic_run_id,
            )
            await CollectionRunRepository(session).update_progress(
                run.id, items_discovered=len(items), metadata=metadata
            )
            return run.id, items

    async def _persist(
        self,
        items: list,
        videos: dict[str, YouTubeVideo],
        channels: dict[str, YouTubeChannel],
        captured_at: datetime,
        include_snapshots: bool,
    ) -> tuple[int, int, int]:
        processed = failed = snapshots = 0
        async with self._sessions() as session, session.begin():
            channel_repository = ChannelRepository(session)
            video_repository = VideoRepository(session)
            staging = YouTubeDiscoveryItemRepository(session)
            canonical_channels = {}
            for channel in channels.values():
                canonical_channels[
                    channel.youtube_channel_id
                ] = await channel_repository.upsert_channel(
                    youtube_channel_id=channel.youtube_channel_id,
                    name=channel.name,
                    description=channel.description,
                    country=channel.country,
                    subscriber_count=channel.subscriber_count,
                    video_count=channel.video_count,
                    view_count=channel.view_count,
                    channel_type=None,
                    first_seen_at=captured_at,
                    last_seen_at=captured_at,
                    updated_at=captured_at,
                )
            canonical_videos = {}
            for video in videos.values():
                channel = canonical_channels.get(video.youtube_channel_id)
                if channel is None:
                    continue
                canonical = await video_repository.create_or_update_video(
                    youtube_video_id=video.youtube_video_id,
                    channel_id=channel.id,
                    title=video.title,
                    description=video.description,
                    published_at=video.published_at,
                    duration_seconds=video.duration_seconds,
                    language=video.language,
                    category_id=video.category_id,
                    thumbnail_url=video.thumbnail_url,
                    current_view_count=video.view_count,
                    current_like_count=video.like_count,
                    current_comment_count=video.comment_count,
                    has_captions=video.has_captions,
                    first_seen_at=captured_at,
                    last_seen_at=captured_at,
                    processing_status="new",
                    updated_at=captured_at,
                )
                canonical_videos[video.youtube_video_id] = canonical
                if include_snapshots:
                    snapshot = await video_repository.add_snapshot(
                        video_id=canonical.id,
                        captured_at=captured_at,
                        view_count=video.view_count,
                        like_count=video.like_count,
                        comment_count=video.comment_count,
                    )
                    snapshots += snapshot is not None
            for item in items:
                video = videos.get(item.youtube_video_id)
                canonical = canonical_videos.get(item.youtube_video_id)
                if canonical is not None:
                    await staging.mark_processed(
                        item.id, canonical_video_id=canonical.id, processed_at=captured_at
                    )
                    processed += 1
                else:
                    reason = "video_unavailable" if video is None else "channel_unavailable"
                    await staging.mark_failed(item.id, processed_at=captured_at, reason=reason)
                    failed += 1
        return processed, failed, snapshots

    async def _release(self, item_ids: list[UUID]) -> None:
        async with self._sessions() as session, session.begin():
            await YouTubeDiscoveryItemRepository(session).release_claims(item_ids)

    async def _finish(
        self,
        run_id: UUID,
        started_at: datetime,
        *,
        claimed: int,
        processed: int,
        failed: int,
        videos_requested: int,
        videos_returned: int,
        channels_requested: int,
        channels_returned: int,
        snapshots_created: int,
        quota: int,
        status: MetadataStatus = "completed",
        reason: str | None = None,
        error_summary: str | None = None,
    ) -> MetadataCollectionResult:
        finished_at = self._clock()
        metadata = self._metadata(
            videos_requested,
            videos_returned,
            channels_requested,
            channels_returned,
            snapshots_created,
            quota,
        )
        values = dict(
            finished_at=finished_at,
            items_discovered=claimed,
            items_processed=processed,
            items_failed=failed,
            error_summary=error_summary,
            metadata=metadata,
        )
        async with self._sessions() as session, session.begin():
            runs = CollectionRunRepository(session)
            await getattr(runs, f"mark_{status}")(run_id, **values)
        logger.info(
            "youtube_metadata_finished collection_run_id=%s status=%s processed=%s failed=%s",
            run_id,
            status,
            processed,
            failed,
        )
        return MetadataCollectionResult(
            collection_run_id=run_id,
            items_claimed=claimed,
            items_processed=processed,
            items_failed=failed,
            videos_requested=videos_requested,
            videos_returned=videos_returned,
            channels_requested=channels_requested,
            channels_returned=channels_returned,
            snapshots_created=snapshots_created,
            estimated_quota_units=quota,
            status=status,
            reason=reason,
            started_at=started_at,
            finished_at=finished_at,
        )

    @staticmethod
    def _metadata(
        videos_requested: int,
        videos_returned: int,
        channels_requested: int,
        channels_returned: int,
        snapshots_created: int,
        quota: int,
    ) -> dict:
        return {
            "videos_requested": videos_requested,
            "videos_returned": videos_returned,
            "channels_requested": channels_requested,
            "channels_returned": channels_returned,
            "snapshots_created": snapshots_created,
            "estimated_quota_units": quota,
        }

    @staticmethod
    def _batch_count(count: int) -> int:
        return (count + 49) // 50
