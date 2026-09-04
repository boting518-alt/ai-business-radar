from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Watchlist, WatchlistItem


class WatchlistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_watchlists(self, user_profile_id: UUID) -> list[Watchlist]:
        return list(
            await self.session.scalars(
                select(Watchlist)
                .where(Watchlist.user_profile_id == user_profile_id)
                .order_by(Watchlist.created_at)
            )
        )

    async def create_watchlist(self, **values: Any) -> Watchlist:
        statement = insert(Watchlist).values(**values).returning(Watchlist)
        return (await self.session.execute(statement)).scalar_one()

    async def add_item(self, **values: Any) -> WatchlistItem:
        statement = insert(WatchlistItem).values(**values).returning(WatchlistItem)
        return (await self.session.execute(statement)).scalar_one()

    async def remove_item(self, watchlist_id: UUID, opportunity_id: UUID) -> bool:
        result = await self.session.execute(
            delete(WatchlistItem).where(
                WatchlistItem.watchlist_id == watchlist_id,
                WatchlistItem.opportunity_id == opportunity_id,
            )
        )
        return bool(result.rowcount)

    async def list_items(self, watchlist_id: UUID) -> list[WatchlistItem]:
        return list(
            await self.session.scalars(
                select(WatchlistItem)
                .where(WatchlistItem.watchlist_id == watchlist_id)
                .order_by(WatchlistItem.added_at)
            )
        )
