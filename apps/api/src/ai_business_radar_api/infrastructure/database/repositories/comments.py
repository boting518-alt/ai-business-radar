from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Comment


class CommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_youtube_comment_id(self, external_id: str) -> Comment | None:
        return await self.session.scalar(
            select(Comment).where(Comment.youtube_comment_id == external_id)
        )

    async def upsert_comment(self, **values: Any) -> Comment:
        immutable = {
            "id",
            "youtube_comment_id",
            "video_id",
            "published_at",
            "author_hash",
            "is_question",
            "first_seen_at",
            "created_at",
        }
        mutable = {key: value for key, value in values.items() if key not in immutable}
        statement = (
            insert(Comment)
            .values(**values)
            .on_conflict_do_update(index_elements=[Comment.youtube_comment_id], set_=mutable)
            .returning(Comment)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(statement)).scalar_one()

    async def list_for_video(self, video_id: UUID, *, limit: int = 500) -> list[Comment]:
        rows = await self.session.scalars(
            select(Comment)
            .where(Comment.video_id == video_id)
            .order_by(Comment.published_at)
            .limit(limit)
        )
        return list(rows)

    async def list_for_pain_mining(self, *, limit: int) -> list[Comment]:
        return list(
            await self.session.scalars(
                select(Comment)
                .where(Comment.text.is_not(None), Comment.text != "")
                .order_by(Comment.first_seen_at, Comment.id)
                .limit(limit)
            )
        )
