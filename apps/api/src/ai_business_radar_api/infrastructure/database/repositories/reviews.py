from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ReviewTask


class ReviewTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: UUID) -> ReviewTask | None:
        return await self.session.get(ReviewTask, entity_id)

    async def list_pending(self, *, limit: int = 100) -> list[ReviewTask]:
        rows = await self.session.scalars(
            select(ReviewTask)
            .where(ReviewTask.status == "pending")
            .order_by(ReviewTask.priority.desc(), ReviewTask.created_at)
            .limit(limit)
        )
        return list(rows)

    async def create_review_task(self, **values: Any) -> ReviewTask:
        statement = insert(ReviewTask).values(**values).returning(ReviewTask)
        return (await self.session.execute(statement)).scalar_one()

    async def find_open_for_target(self, *, target_type: str, target_id: UUID) -> ReviewTask | None:
        return await self.session.scalar(
            select(ReviewTask)
            .where(
                ReviewTask.target_type == target_type,
                ReviewTask.target_id == target_id,
                ReviewTask.status.in_(("pending", "in_review")),
            )
            .order_by(ReviewTask.created_at.desc())
        )

    async def update_review_status(self, entity_id: UUID, **values: Any) -> ReviewTask | None:
        statement = (
            update(ReviewTask)
            .where(ReviewTask.id == entity_id)
            .values(**values)
            .returning(ReviewTask)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()
