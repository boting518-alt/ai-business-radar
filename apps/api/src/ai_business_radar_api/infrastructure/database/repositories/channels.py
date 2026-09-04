from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Channel


class ChannelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: UUID) -> Channel | None:
        return await self.session.get(Channel, entity_id)

    async def get_by_youtube_channel_id(self, external_id: str) -> Channel | None:
        return await self.session.scalar(
            select(Channel).where(Channel.youtube_channel_id == external_id)
        )

    async def upsert_channel(self, **values: Any) -> Channel:
        mutable = {
            key: value
            for key, value in values.items()
            if key
            not in {"id", "youtube_channel_id", "first_seen_at", "created_at", "channel_type"}
        }
        statement = (
            insert(Channel)
            .values(**values)
            .on_conflict_do_update(index_elements=[Channel.youtube_channel_id], set_=mutable)
            .returning(Channel)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(statement)).scalar_one()
