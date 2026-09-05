from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.database.models import UserProfile
from ..infrastructure.database.repositories.radar_queries import RadarQueryRepository
from ..infrastructure.database.repositories.watchlists import WatchlistRepository


class WatchlistOpportunity(BaseModel):
    id: UUID
    slug: str
    name: str
    one_line_thesis: str | None
    industry: str | None
    market_stage: str


class WatchlistItemResult(BaseModel):
    opportunity: WatchlistOpportunity
    opportunity_score: Decimal | None
    confidence_score: Decimal | None
    hype_risk_score: Decimal | None
    momentum_score: Decimal | None
    added_at: datetime


class WatchlistResult(BaseModel):
    items: list[WatchlistItemResult]


class WatchlistMembershipResult(BaseModel):
    opportunity_id: UUID
    watchlisted: bool
    added_at: datetime | None = None


class WatchlistOpportunityNotVisible(RuntimeError):
    pass


class WatchlistService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list_items(self, user_id: UUID) -> WatchlistResult:
        async with self._sessions() as session:
            repository = WatchlistRepository(session)
            watchlists = await repository.get_user_watchlists(user_id)
            if not watchlists:
                return WatchlistResult(items=[])
            rows = await repository.list_product_rows(watchlists[0].id)
            ids = [opportunity.id for _, opportunity in rows]
            radar = RadarQueryRepository(session)
            scores = await radar.latest_scores(ids)
            trends = await radar.latest_trends(ids, "7d")
        return WatchlistResult(
            items=[
                WatchlistItemResult(
                    opportunity=WatchlistOpportunity.model_validate(
                        opportunity, from_attributes=True
                    ),
                    opportunity_score=(
                        scores.get(opportunity.id).opportunity_score
                        if scores.get(opportunity.id)
                        else None
                    ),
                    confidence_score=(
                        scores.get(opportunity.id).confidence_score
                        if scores.get(opportunity.id)
                        else None
                    ),
                    hype_risk_score=(
                        scores.get(opportunity.id).hype_risk_score
                        if scores.get(opportunity.id)
                        else None
                    ),
                    momentum_score=(
                        trends.get(opportunity.id).momentum_score
                        if trends.get(opportunity.id)
                        else None
                    ),
                    added_at=item.added_at,
                )
                for item, opportunity in rows
            ]
        )

    async def add(self, user_id: UUID, opportunity_id: UUID) -> WatchlistMembershipResult:
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            await session.scalar(
                select(UserProfile).where(UserProfile.id == user_id).with_for_update()
            )
            radar = RadarQueryRepository(session)
            opportunity = await radar.get_visible_opportunity(str(opportunity_id))
            if opportunity is None:
                raise WatchlistOpportunityNotVisible("Opportunity was not found")
            repository = WatchlistRepository(session)
            watchlists = await repository.get_user_watchlists(user_id)
            watchlist = (
                watchlists[0]
                if watchlists
                else await repository.create_watchlist(
                    user_profile_id=user_id, name="Watchlist", created_at=now, updated_at=now
                )
            )
            item = await repository.add_item(
                watchlist_id=watchlist.id, opportunity_id=opportunity.id, added_at=now
            )
        return WatchlistMembershipResult(
            opportunity_id=opportunity.id, watchlisted=True, added_at=item.added_at
        )

    async def remove(self, user_id: UUID, opportunity_id: UUID) -> WatchlistMembershipResult:
        async with self._sessions() as session, session.begin():
            repository = WatchlistRepository(session)
            watchlists = await repository.get_user_watchlists(user_id)
            if watchlists:
                await repository.remove_item(watchlists[0].id, opportunity_id)
        return WatchlistMembershipResult(opportunity_id=opportunity_id, watchlisted=False)
