from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.database.repositories import YouTubeDiscoveryItemRepository


class StaleClaimRecoveryService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def recover(self, *, timeout_minutes: int, limit: int) -> int:
        stale_before = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
        async with self._sessions() as session, session.begin():
            return await YouTubeDiscoveryItemRepository(session).recover_stale_claims(
                stale_before=stale_before, limit=limit
            )
