from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, update
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

    async def list_lexical_candidates(
        self, *, terms: list[str], limit: int = 100
    ) -> list[Opportunity]:
        query = select(Opportunity).where(Opportunity.status.in_(("candidate", "active", "review")))
        if terms:
            columns = (
                Opportunity.name,
                Opportunity.one_line_thesis,
                Opportunity.industry,
                Opportunity.customer_type,
                Opportunity.problem,
                Opportunity.solution,
            )
            query = query.where(
                or_(*(column.ilike(f"%{term}%") for term in terms for column in columns))
            )
        rows = await self.session.scalars(
            query.order_by(Opportunity.last_activity_at.desc(), Opportunity.id).limit(limit)
        )
        return list(rows)

    async def get_link_for_signal(self, signal_id: UUID) -> OpportunitySignalLink | None:
        return await self.session.scalar(
            select(OpportunitySignalLink).where(OpportunitySignalLink.signal_id == signal_id)
        )

    async def update_last_activity(self, opportunity_id: UUID, last_activity_at: datetime) -> None:
        opportunity = await self.get_by_id(opportunity_id)
        if opportunity is not None and last_activity_at > opportunity.last_activity_at:
            await self.session.execute(
                update(Opportunity)
                .where(Opportunity.id == opportunity_id)
                .values(
                    last_activity_at=last_activity_at,
                    updated_at=datetime.now(last_activity_at.tzinfo),
                )
            )

    async def link_signal(self, **values: Any) -> OpportunitySignalLink:
        statement = (
            insert(OpportunitySignalLink)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["opportunity_id", "signal_id"])
            .returning(OpportunitySignalLink)
        )
        created = (await self.session.execute(statement)).scalar_one_or_none()
        if created is not None:
            return created
        existing = await self.get_link_for_signal(values["signal_id"])
        if existing is None:
            raise RuntimeError("Opportunity signal link conflict could not be resolved")
        return existing

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
