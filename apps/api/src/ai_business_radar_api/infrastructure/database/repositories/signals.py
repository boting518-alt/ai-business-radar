from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Signal


class SignalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_signal(self, **values: Any) -> Signal:
        statement = insert(Signal).values(**values).returning(Signal)
        return (await self.session.execute(statement)).scalar_one()

    async def get_by_id(self, entity_id: UUID) -> Signal | None:
        return await self.session.get(Signal, entity_id)

    async def list_for_video(self, video_id: UUID) -> list[Signal]:
        return list(await self.session.scalars(select(Signal).where(Signal.video_id == video_id)))

    async def list_for_comment(self, comment_id: UUID) -> list[Signal]:
        return list(
            await self.session.scalars(select(Signal).where(Signal.comment_id == comment_id))
        )

    async def update_status(self, entity_id: UUID, status: str) -> Signal | None:
        statement = (
            update(Signal).where(Signal.id == entity_id).values(status=status).returning(Signal)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()
