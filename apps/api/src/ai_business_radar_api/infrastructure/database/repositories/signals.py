from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Signal


class SignalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_signal(self, **values: Any) -> Signal:
        statement = insert(Signal).values(**values).returning(Signal)
        return (await self.session.execute(statement)).scalar_one()

    async def create_many(self, values: list[dict[str, Any]]) -> list[Signal]:
        if not values:
            return []
        return list(await self.session.scalars(insert(Signal).values(values).returning(Signal)))

    async def count_for_extraction(self, extraction_id: UUID) -> int:
        return (
            await self.session.scalar(
                select(func.count(Signal.id)).where(Signal.ai_extraction_id == extraction_id)
            )
        ) or 0

    async def get_by_id(self, entity_id: UUID) -> Signal | None:
        return await self.session.get(Signal, entity_id)

    async def list_for_video(self, video_id: UUID) -> list[Signal]:
        return list(await self.session.scalars(select(Signal).where(Signal.video_id == video_id)))

    async def list_for_comment(self, comment_id: UUID) -> list[Signal]:
        return list(
            await self.session.scalars(select(Signal).where(Signal.comment_id == comment_id))
        )

    async def list_for_normalization(self, *, limit: int) -> list[Signal]:
        return list(
            await self.session.scalars(
                select(Signal)
                .where((Signal.status == "review") & (Signal.semantic_status == "current"))
                .order_by(Signal.observed_at.asc().nulls_last(), Signal.created_at, Signal.id)
                .limit(limit)
            )
        )

    async def update_status(self, entity_id: UUID, status: str) -> Signal | None:
        statement = (
            update(Signal).where(Signal.id == entity_id).values(status=status).returning(Signal)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()
