"""Bounded, quota-aware YouTube discovery orchestration."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.database.repositories import (
    CollectionRunRepository,
    SearchQueryRepository,
    YouTubeDiscoveryItemRepository,
)
from ..infrastructure.external.youtube import YouTubeAPIError, YouTubeClient, YouTubeQuotaCost

logger = logging.getLogger(__name__)
DiscoveryStatus = Literal["completed", "partial", "failed"]
DiscoveryOrder = Literal["date", "relevance", "viewCount"]


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search_query_id: UUID
    collection_run_id: UUID | None = None
    max_pages: int = Field(default=1, ge=1, le=5)
    max_results: int | None = Field(default=50, ge=1, le=250)
    published_after: datetime | None = None
    order: DiscoveryOrder = "date"

    @field_validator("published_after")
    @classmethod
    def require_aware_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("published_after must be timezone-aware")
        return value


class DiscoveryResult(BaseModel):
    collection_run_id: UUID
    search_query_id: UUID
    pages_requested: int
    pages_completed: int
    items_discovered: int
    unique_video_count: int
    estimated_quota_units: int
    next_page_token: str | None
    status: DiscoveryStatus
    reason: str | None = None
    started_at: datetime
    finished_at: datetime


class DiscoveryError(RuntimeError):
    pass


class SearchQueryNotFound(DiscoveryError):
    pass


class SearchQueryDisabled(DiscoveryError):
    pass


class InvalidDiscoveryMode(DiscoveryError):
    pass


class DiscoveryQuotaBudgetExceeded(DiscoveryError):
    pass


class DiscoveryExecutionError(DiscoveryError):
    pass


class YouTubeDiscoveryService:
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

    async def discover(self, request: DiscoveryRequest) -> DiscoveryResult:
        query = await self._load_query(request.search_query_id)
        started_at = self._clock()
        run_id = await self._start_run(request, started_at)
        pages_requested = 0
        pages_completed = 0
        estimated_quota = 0
        next_page_token: str | None = None
        seen_video_ids: set[str] = set()
        status: DiscoveryStatus = "completed"
        reason: str | None = None

        for page_number in range(1, request.max_pages + 1):
            if estimated_quota + YouTubeQuotaCost.SEARCH_LIST > self._quota_budget:
                status = "partial" if pages_completed else "failed"
                reason = "quota_budget_reached"
                break
            remaining = (
                50
                if request.max_results is None
                else min(50, request.max_results - len(seen_video_ids))
            )
            if remaining <= 0:
                break
            pages_requested += 1
            estimated_quota += YouTubeQuotaCost.SEARCH_LIST
            try:
                page = await self._youtube.search_videos(
                    query.query,
                    max_results=remaining,
                    order=request.order,
                    published_after=request.published_after,
                    page_token=next_page_token,
                    region_code=query.region,
                    relevance_language=query.language,
                )
            except YouTubeAPIError:
                status = "partial" if pages_completed else "failed"
                reason = "youtube_request_failed"
                finished_at = self._clock()
                await self._finalize(
                    run_id,
                    status=status,
                    finished_at=finished_at,
                    items_discovered=len(seen_video_ids),
                    pages_requested=pages_requested,
                    pages_completed=pages_completed,
                    estimated_quota=estimated_quota,
                    next_page_token=next_page_token,
                    reason=reason,
                    order=request.order,
                    error_summary="youtube_request_failed",
                )
                logger.warning(
                    "youtube_discovery_failed collection_run_id=%s search_query_id=%s "
                    "pages_completed=%s",
                    run_id,
                    request.search_query_id,
                    pages_completed,
                )
                return self._result(
                    request,
                    run_id,
                    started_at,
                    finished_at,
                    pages_requested,
                    pages_completed,
                    seen_video_ids,
                    estimated_quota,
                    next_page_token,
                    status,
                    reason,
                )

            accepted = []
            for item in page.items:
                if item.youtube_video_id in seen_video_ids:
                    continue
                if request.max_results is not None and len(seen_video_ids) >= request.max_results:
                    break
                seen_video_ids.add(item.youtube_video_id)
                accepted.append(item)
            next_page_token = page.next_page_token
            pages_completed += 1
            await self._persist_page(
                run_id,
                request.search_query_id,
                accepted,
                self._clock(),
                pages_requested,
                pages_completed,
                len(seen_video_ids),
                estimated_quota,
                next_page_token,
                request.order,
            )
            logger.info(
                "youtube_discovery_page collection_run_id=%s search_query_id=%s page=%s "
                "result_count=%s estimated_quota_units=%s",
                run_id,
                request.search_query_id,
                page_number,
                len(accepted),
                estimated_quota,
            )
            if request.max_results is not None and len(seen_video_ids) >= request.max_results:
                break
            if next_page_token is None:
                break

        finished_at = self._clock()
        await self._finalize(
            run_id,
            status=status,
            finished_at=finished_at,
            items_discovered=len(seen_video_ids),
            pages_requested=pages_requested,
            pages_completed=pages_completed,
            estimated_quota=estimated_quota,
            next_page_token=next_page_token,
            reason=reason,
            order=request.order,
        )
        logger.info(
            "youtube_discovery_finished collection_run_id=%s search_query_id=%s "
            "status=%s items_discovered=%s estimated_quota_units=%s",
            run_id,
            request.search_query_id,
            status,
            len(seen_video_ids),
            estimated_quota,
        )
        return self._result(
            request,
            run_id,
            started_at,
            finished_at,
            pages_requested,
            pages_completed,
            seen_video_ids,
            estimated_quota,
            next_page_token,
            status,
            reason,
        )

    async def _load_query(self, query_id: UUID):
        async with self._sessions() as session:
            query = await SearchQueryRepository(session).get_by_id(query_id)
        if query is None:
            raise SearchQueryNotFound("Search query was not found")
        if not query.enabled:
            raise SearchQueryDisabled("Search query is disabled")
        if query.discovery_mode != "discovery":
            raise InvalidDiscoveryMode("Search query is not configured for discovery")
        return query

    async def _start_run(self, request: DiscoveryRequest, started_at: datetime) -> UUID:
        metadata = self._metadata(0, 0, 0, None, request.order, None)
        async with self._sessions() as session, session.begin():
            runs = CollectionRunRepository(session)
            if request.collection_run_id is None:
                run = await runs.create_run(request.search_query_id, metadata)
                run_id = run.id
            else:
                run_id = request.collection_run_id
            await runs.mark_running(run_id, started_at)
            await SearchQueryRepository(session).update_last_run_at(
                request.search_query_id, started_at
            )
            return run_id

    async def _persist_page(
        self,
        run_id: UUID,
        query_id: UUID,
        items: list,
        discovered_at: datetime,
        pages_requested: int,
        pages_completed: int,
        item_count: int,
        quota: int,
        next_token: str | None,
        order: str,
    ) -> None:
        values = [
            {
                "collection_run_id": run_id,
                "search_query_id": query_id,
                "youtube_video_id": item.youtube_video_id,
                "youtube_channel_id": item.youtube_channel_id,
                "title": item.title,
                "description": item.description,
                "published_at": item.published_at,
                "channel_title": item.channel_title,
                "thumbnail_url": item.thumbnail_url,
                "discovered_at": discovered_at,
                "processing_status": "pending",
            }
            for item in items
        ]
        metadata = self._metadata(pages_requested, pages_completed, quota, next_token, order, None)
        async with self._sessions() as session, session.begin():
            await YouTubeDiscoveryItemRepository(session).add_discovered_items(values)
            await CollectionRunRepository(session).update_progress(
                run_id, items_discovered=item_count, metadata=metadata
            )

    async def _finalize(
        self,
        run_id: UUID,
        *,
        status: DiscoveryStatus,
        finished_at: datetime,
        items_discovered: int,
        pages_requested: int,
        pages_completed: int,
        estimated_quota: int,
        next_page_token: str | None,
        reason: str | None,
        order: str,
        error_summary: str | None = None,
    ) -> None:
        metadata = self._metadata(
            pages_requested, pages_completed, estimated_quota, next_page_token, order, reason
        )
        values = {
            "finished_at": finished_at,
            "items_discovered": items_discovered,
            "items_processed": 0,
            "items_failed": 0,
            "error_summary": error_summary,
            "metadata": metadata,
        }
        async with self._sessions() as session, session.begin():
            runs = CollectionRunRepository(session)
            if status == "completed":
                await runs.mark_completed(run_id, **values)
            elif status == "partial":
                await runs.mark_partial(run_id, **values)
            else:
                await runs.mark_failed(run_id, **values)

    @staticmethod
    def _metadata(
        pages_requested: int,
        pages_completed: int,
        estimated_quota: int,
        next_token: str | None,
        order: str | None,
        reason: str | None,
    ) -> dict:
        return {
            "pages_requested": pages_requested,
            "pages_completed": pages_completed,
            "estimated_quota_units": estimated_quota,
            "next_page_token": next_token,
            "order": order,
            "reason": reason,
        }

    @staticmethod
    def _result(
        request: DiscoveryRequest,
        run_id: UUID,
        started_at: datetime,
        finished_at: datetime,
        pages_requested: int,
        pages_completed: int,
        seen: set[str],
        quota: int,
        next_token: str | None,
        status: DiscoveryStatus,
        reason: str | None,
    ) -> DiscoveryResult:
        return DiscoveryResult(
            collection_run_id=run_id,
            search_query_id=request.search_query_id,
            pages_requested=pages_requested,
            pages_completed=pages_completed,
            items_discovered=len(seen),
            unique_video_count=len(seen),
            estimated_quota_units=quota,
            next_page_token=next_token,
            status=status,
            reason=reason,
            started_at=started_at,
            finished_at=finished_at,
        )
