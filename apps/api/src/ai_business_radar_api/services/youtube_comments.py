"""Bounded official YouTube top-level comment collection."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.database.repositories import (
    CollectionRunRepository,
    CommentRepository,
    VideoRepository,
)
from ..infrastructure.external.youtube import YouTubeAPIError, YouTubeClient, YouTubeQuotaCost

logger = logging.getLogger(__name__)
CommentOrder = Literal["relevance", "time"]
CommentCollectionStatus = Literal["completed", "partial", "failed"]


class CommentCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_ids: list[UUID] | None = None
    limit_videos: int = Field(default=20, ge=1, le=100)
    max_pages_per_video: int = Field(default=1, ge=1, le=5)
    max_comments_per_video: int = Field(default=100, ge=1, le=500)
    order: CommentOrder = "relevance"

    @field_validator("video_ids")
    @classmethod
    def validate_video_ids(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is None:
            return None
        unique = list(dict.fromkeys(value))
        if not unique:
            raise ValueError("video_ids must not be empty")
        if len(unique) > 100:
            raise ValueError("video_ids must contain at most 100 unique IDs")
        return unique


class CommentCollectionResult(BaseModel):
    collection_run_id: UUID
    videos_requested: int
    videos_completed: int
    videos_failed: int
    videos_skipped: int
    pages_requested: int
    pages_completed: int
    comments_discovered: int
    comments_processed: int
    estimated_quota_units: int
    status: CommentCollectionStatus
    reason: str | None = None
    started_at: datetime
    finished_at: datetime


class CanonicalVideosNotFound(RuntimeError):
    def __init__(self, missing_ids: list[UUID]) -> None:
        super().__init__("One or more canonical videos were not found or are ineligible")
        self.missing_ids = missing_ids


class YouTubeCommentCollectionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        youtube: YouTubeClient,
        *,
        max_quota_units_per_run: int = 500,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._youtube = youtube
        self._quota_budget = max_quota_units_per_run
        self._clock = clock or (lambda: datetime.now(UTC))

    async def collect(self, request: CommentCollectionRequest) -> CommentCollectionResult:
        videos = await self._select_videos(request)
        started_at = self._clock()
        run_id = await self._start_run(started_at, len(videos))
        metrics = {
            "videos_requested": len(videos),
            "videos_completed": 0,
            "videos_failed": 0,
            "videos_skipped": 0,
            "pages_requested": 0,
            "pages_completed": 0,
            "comments_discovered": 0,
            "comments_processed": 0,
            "estimated_quota_units": 0,
        }
        outcomes: dict[str, str] = {}
        quota_stopped = False

        for video in videos:
            video_comments = 0
            seen_comment_ids: set[str] = set()
            next_page_token: str | None = None
            video_failed = False
            for page_number in range(1, request.max_pages_per_video + 1):
                if (
                    metrics["estimated_quota_units"] + YouTubeQuotaCost.COMMENT_THREADS_LIST
                    > self._quota_budget
                ):
                    quota_stopped = True
                    break
                remaining = request.max_comments_per_video - video_comments
                if remaining <= 0:
                    break
                metrics["pages_requested"] += 1
                metrics["estimated_quota_units"] += YouTubeQuotaCost.COMMENT_THREADS_LIST
                try:
                    page = await self._youtube.get_comment_threads(
                        video.youtube_video_id,
                        max_results=min(100, remaining),
                        page_token=next_page_token,
                        order=request.order,
                    )
                except YouTubeAPIError as error:
                    if error.reason == "commentsDisabled":
                        metrics["videos_skipped"] += 1
                        outcomes[str(video.id)] = "comments_disabled"
                    else:
                        metrics["videos_failed"] += 1
                        outcomes[str(video.id)] = "collection_failed"
                    video_failed = True
                    logger.warning(
                        "youtube_comments_video_failed collection_run_id=%s video_id=%s page=%s",
                        run_id,
                        video.id,
                        page_number,
                    )
                    break

                accepted = []
                for comment in page.items:
                    if (
                        comment.youtube_comment_id in seen_comment_ids
                        or len(accepted) >= remaining
                    ):
                        continue
                    seen_comment_ids.add(comment.youtube_comment_id)
                    accepted.append(comment)
                persisted = await self._persist_page(video.id, accepted, self._clock())
                video_comments += len(accepted)
                metrics["comments_discovered"] += len(accepted)
                metrics["comments_processed"] += persisted
                metrics["pages_completed"] += 1
                next_page_token = page.next_page_token
                logger.info(
                    "youtube_comments_page collection_run_id=%s video_id=%s page=%s "
                    "comments_returned=%s comments_persisted=%s estimated_quota_units=%s",
                    run_id,
                    video.id,
                    page_number,
                    len(accepted),
                    persisted,
                    metrics["estimated_quota_units"],
                )
                if video_comments >= request.max_comments_per_video or next_page_token is None:
                    break
            if quota_stopped:
                outcomes[str(video.id)] = "quota_budget_reached"
                break
            if not video_failed:
                metrics["videos_completed"] += 1
                outcomes[str(video.id)] = "completed"

        status, reason = self._status(metrics, quota_stopped)
        return await self._finish(run_id, started_at, metrics, outcomes, status, reason)

    async def _select_videos(self, request: CommentCollectionRequest):
        async with self._sessions() as session:
            repository = VideoRepository(session)
            if request.video_ids is None:
                return await repository.list_for_comment_collection(limit=request.limit_videos)
            videos = await repository.list_existing_by_ids(request.video_ids)
        by_id = {video.id: video for video in videos}
        missing = [video_id for video_id in request.video_ids if video_id not in by_id]
        if missing:
            raise CanonicalVideosNotFound(missing)
        return [by_id[video_id] for video_id in request.video_ids]

    async def _start_run(self, started_at: datetime, videos_requested: int) -> UUID:
        metadata = self._metadata(videos_requested=videos_requested)
        async with self._sessions() as session, session.begin():
            runs = CollectionRunRepository(session)
            run = await runs.create_run(None, metadata, run_type="comment_collection")
            await runs.mark_running(run.id, started_at)
            return run.id

    async def _persist_page(self, video_id: UUID, comments: list, observed_at: datetime) -> int:
        async with self._sessions() as session, session.begin():
            repository = CommentRepository(session)
            for comment in comments:
                values = dict(
                    youtube_comment_id=comment.youtube_comment_id,
                    video_id=video_id,
                    text=comment.text,
                    published_at=comment.published_at,
                    like_count=comment.like_count,
                    reply_count=comment.reply_count,
                    author_hash=None,
                    is_question=None,
                    first_seen_at=observed_at,
                    updated_at=observed_at,
                )
                if comment.updated_at is not None:
                    values["source_updated_at"] = comment.updated_at
                await repository.upsert_comment(**values)
        return len(comments)

    async def _finish(
        self,
        run_id: UUID,
        started_at: datetime,
        metrics: dict[str, int],
        outcomes: dict[str, str],
        status: CommentCollectionStatus,
        reason: str | None,
    ) -> CommentCollectionResult:
        finished_at = self._clock()
        metadata = {**self._metadata(**metrics), "video_outcomes": outcomes, "reason": reason}
        values = {
            "finished_at": finished_at,
            "items_discovered": metrics["comments_discovered"],
            "items_processed": metrics["comments_processed"],
            "items_failed": metrics["videos_failed"],
            "error_summary": "comment_collection_failed" if status == "failed" else None,
            "metadata": metadata,
        }
        async with self._sessions() as session, session.begin():
            runs = CollectionRunRepository(session)
            await getattr(runs, f"mark_{status}")(run_id, **values)
        return CommentCollectionResult(
            collection_run_id=run_id,
            status=status,
            reason=reason,
            started_at=started_at,
            finished_at=finished_at,
            **metrics,
        )

    @staticmethod
    def _status(
        metrics: dict[str, int], quota_stopped: bool
    ) -> tuple[CommentCollectionStatus, str | None]:
        if quota_stopped:
            return ("partial" if metrics["pages_completed"] else "failed"), "quota_budget_reached"
        if metrics["videos_failed"]:
            if (
                metrics["videos_completed"]
                or metrics["videos_skipped"]
                or metrics["pages_completed"]
            ):
                return "partial", "video_collection_failed"
            return "failed", "all_videos_failed"
        return "completed", None

    @staticmethod
    def _metadata(**values: int) -> dict:
        defaults = {
            "videos_requested": 0,
            "videos_completed": 0,
            "videos_failed": 0,
            "videos_skipped": 0,
            "pages_requested": 0,
            "pages_completed": 0,
            "comments_discovered": 0,
            "comments_processed": 0,
            "estimated_quota_units": 0,
        }
        return defaults | values
