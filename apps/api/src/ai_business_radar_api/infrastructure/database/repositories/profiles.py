from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import UserProfile


class UserProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_auth_user_id(self, auth_user_id: UUID) -> UserProfile | None:
        return await self.session.scalar(
            select(UserProfile).where(UserProfile.auth_user_id == auth_user_id)
        )
