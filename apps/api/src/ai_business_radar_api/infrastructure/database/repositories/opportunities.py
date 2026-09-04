from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Opportunity,
    OpportunityEvidence,
    OpportunityScore,
    OpportunitySignalLink,
    TrendSnapshot,
)


class OpportunityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: UUID) -> Opportunity | None:
        return await self.session.get(Opportunity, entity_id)

    async def get_by_slug(self, slug: str) -> Opportunity | None:
        return await self.session.scalar(select(Opportunity).where(Opportunity.slug == slug))

    async def create_opportunity(self, **values: Any) -> Opportunity:
        statement = insert(Opportunity).values(**values).returning(Opportunity)
        return (await self.session.execute(statement)).scalar_one()

    async def list_candidates(self, *, limit: int = 100) -> list[Opportunity]:
        rows = await self.session.scalars(
            select(Opportunity)
            .where(Opportunity.status == "candidate")
            .order_by(Opportunity.first_detected_at.desc())
            .limit(limit)
        )
        return list(rows)

    async def link_signal(self, **values: Any) -> OpportunitySignalLink:
        statement = insert(OpportunitySignalLink).values(**values).returning(OpportunitySignalLink)
        return (await self.session.execute(statement)).scalar_one()

    async def add_evidence(self, **values: Any) -> OpportunityEvidence:
        statement = insert(OpportunityEvidence).values(**values).returning(OpportunityEvidence)
        return (await self.session.execute(statement)).scalar_one()

    async def get_latest_score(self, opportunity_id: UUID) -> OpportunityScore | None:
        return await self.session.scalar(
            select(OpportunityScore)
            .where(OpportunityScore.opportunity_id == opportunity_id)
            .order_by(OpportunityScore.calculated_at.desc())
            .limit(1)
        )

    async def list_recent_trends(
        self, opportunity_id: UUID, *, since: datetime | None = None
    ) -> list[TrendSnapshot]:
        query = select(TrendSnapshot).where(TrendSnapshot.opportunity_id == opportunity_id)
        if since is not None:
            query = query.where(TrendSnapshot.period_end >= since)
        return list(await self.session.scalars(query.order_by(TrendSnapshot.period_end.desc())))
