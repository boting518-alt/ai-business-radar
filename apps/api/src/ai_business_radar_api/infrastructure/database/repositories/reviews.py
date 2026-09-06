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

    async def get_for_update(self, entity_id: UUID) -> ReviewTask | None:
        return await self.session.scalar(
            select(ReviewTask).where(ReviewTask.id == entity_id).with_for_update()
        )

    async def list_tasks(
        self,
        *,
        status: str | None = None,
        review_type: str | None = None,
        assigned_to: UUID | None = None,
        priority: float | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ReviewTask]:
        query = select(ReviewTask)
        if status is not None:
            query = query.where(ReviewTask.status == status)
        if review_type is not None:
            query = query.where(ReviewTask.review_type == review_type)
        if assigned_to is not None:
            query = query.where(ReviewTask.assigned_to == assigned_to)
        if priority is not None:
            query = query.where(ReviewTask.priority == priority)
        rows = await self.session.scalars(
            query.order_by(ReviewTask.priority.desc(), ReviewTask.created_at, ReviewTask.id)
            .offset(offset)
            .limit(limit)
        )
        return list(rows)

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

    async def find_open_for_target(
        self, *, target_type: str, target_id: UUID, review_type: str | None = None
    ) -> ReviewTask | None:
        conditions = [
            ReviewTask.target_type == target_type,
            ReviewTask.target_id == target_id,
            ReviewTask.status.in_(("pending", "in_review")),
        ]
        if review_type is not None:
            conditions.append(ReviewTask.review_type == review_type)
        return await self.session.scalar(
            select(ReviewTask)
            .where(*conditions)
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
