from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Video, VideoSnapshot


class VideoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: UUID) -> Video | None:
        return await self.session.get(Video, entity_id)

    async def get_by_youtube_video_id(self, external_id: str) -> Video | None:
        return await self.session.scalar(select(Video).where(Video.youtube_video_id == external_id))

    async def create_or_update_video(self, **values: Any) -> Video:
        immutable = {"id", "youtube_video_id", "first_seen_at", "created_at"}
        mutable = {key: value for key, value in values.items() if key not in immutable}
        statement = (
            insert(Video)
            .values(**values)
            .on_conflict_do_update(index_elements=[Video.youtube_video_id], set_=mutable)
            .returning(Video)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(statement)).scalar_one()

    async def list_by_processing_status(self, status: str, *, limit: int = 100) -> list[Video]:
        result = await self.session.scalars(
            select(Video)
            .where(Video.processing_status == status)
            .order_by(Video.created_at)
            .limit(limit)
        )
        return list(result)

    async def add_snapshot(self, **values: Any) -> VideoSnapshot:
        statement = insert(VideoSnapshot).values(**values).returning(VideoSnapshot)
        return (await self.session.execute(statement)).scalar_one()
