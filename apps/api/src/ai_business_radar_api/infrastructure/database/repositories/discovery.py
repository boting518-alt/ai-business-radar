"""Persistence primitives for managed YouTube discovery."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CollectionRun, SearchQuery, YouTubeDiscoveryItem


class SearchQueryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: UUID) -> SearchQuery | None:
        return await self.session.get(SearchQuery, entity_id)

    async def list_enabled(self) -> list[SearchQuery]:
        return list(
            await self.session.scalars(
                select(SearchQuery)
                .where(SearchQuery.enabled.is_(True))
                .order_by(SearchQuery.priority.desc(), SearchQuery.created_at)
            )
        )

    async def update_last_run_at(self, entity_id: UUID, attempted_at: datetime) -> None:
        await self.session.execute(
            update(SearchQuery).where(SearchQuery.id == entity_id).values(last_run_at=attempted_at)
        )


class CollectionRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_run(self, search_query_id: UUID, metadata: dict[str, Any]) -> CollectionRun:
        statement = (
            insert(CollectionRun)
            .values(
                source_type="youtube",
                run_type="discovery",
                status="pending",
                search_query_id=search_query_id,
                metadata_=metadata,
            )
            .returning(CollectionRun)
        )
        return (await self.session.execute(statement)).scalar_one()

    async def mark_running(self, run_id: UUID, started_at: datetime) -> None:
        await self._update(run_id, status="running", started_at=started_at)

    async def update_progress(
        self, run_id: UUID, *, items_discovered: int, metadata: dict[str, Any]
    ) -> None:
        await self._update(run_id, items_discovered=items_discovered, metadata=metadata)

    async def mark_completed(self, run_id: UUID, **values: Any) -> None:
        await self._update(run_id, status="completed", **values)

    async def mark_partial(self, run_id: UUID, **values: Any) -> None:
        await self._update(run_id, status="partial", **values)

    async def mark_failed(self, run_id: UUID, **values: Any) -> None:
        await self._update(run_id, status="failed", **values)

    async def _update(self, run_id: UUID, **values: Any) -> None:
        if "metadata" in values:
            values["metadata_"] = values.pop("metadata")
        await self.session.execute(
            update(CollectionRun).where(CollectionRun.id == run_id).values(**values)
        )


class YouTubeDiscoveryItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_discovered_items(self, values: list[dict[str, Any]]) -> int:
        if not values:
            return 0
        statement = (
            insert(YouTubeDiscoveryItem)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=[
                    YouTubeDiscoveryItem.collection_run_id,
                    YouTubeDiscoveryItem.youtube_video_id,
                ]
            )
            .returning(YouTubeDiscoveryItem.id)
        )
        return len((await self.session.scalars(statement)).all())

    async def list_pending(self, *, limit: int = 100) -> list[YouTubeDiscoveryItem]:
        return list(
            await self.session.scalars(
                select(YouTubeDiscoveryItem)
                .where(YouTubeDiscoveryItem.processing_status == "pending")
                .order_by(YouTubeDiscoveryItem.created_at)
                .limit(limit)
            )
        )

    async def mark_processed(self, entity_id: UUID) -> None:
        await self.session.execute(
            update(YouTubeDiscoveryItem)
            .where(YouTubeDiscoveryItem.id == entity_id)
            .values(processing_status="processed")
        )
