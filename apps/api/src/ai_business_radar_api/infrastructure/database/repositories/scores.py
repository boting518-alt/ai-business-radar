from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Comment, Opportunity, OpportunityScore, OpportunitySignalLink, Signal, Video


@dataclass(frozen=True)
class ScoringSignalRow:
    signal_id: UUID
    signal_type: str
    claim_status: str
    source_type: str
    effective_time: datetime
    relationship_type: str
    video_id: UUID | None
    channel_id: UUID | None
    revenue_claim_amount: Any
    customer_count_claim: int | None
    price_min: Any
    price_max: Any
    technology: list[str] | None
    distribution_channels: list[str] | None


class OpportunityScoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_input_identity(
        self, *, opportunity_id: UUID, scoring_version: str, input_hash: str
    ) -> OpportunityScore | None:
        return await self.session.scalar(
            select(OpportunityScore).where(
                OpportunityScore.opportunity_id == opportunity_id,
                OpportunityScore.scoring_version == scoring_version,
                OpportunityScore.input_hash == input_hash,
            )
        )

    async def create_score(self, **values: Any) -> OpportunityScore:
        return (
            await self.session.execute(
                insert(OpportunityScore).values(**values).returning(OpportunityScore)
            )
        ).scalar_one()

    async def get_latest(
        self, opportunity_id: UUID, *, scoring_version: str
    ) -> OpportunityScore | None:
        return await self.session.scalar(
            select(OpportunityScore)
            .where(
                OpportunityScore.opportunity_id == opportunity_id,
                OpportunityScore.scoring_version == scoring_version,
            )
            .order_by(OpportunityScore.calculated_at.desc(), OpportunityScore.created_at.desc())
            .limit(1)
        )

    async def list_history(
        self, opportunity_id: UUID, *, scoring_version: str, limit: int = 100
    ) -> list[OpportunityScore]:
        return list(
            await self.session.scalars(
                select(OpportunityScore)
                .where(
                    OpportunityScore.opportunity_id == opportunity_id,
                    OpportunityScore.scoring_version == scoring_version,
                )
                .order_by(OpportunityScore.calculated_at.desc(), OpportunityScore.created_at.desc())
                .limit(limit)
            )
        )

    async def list_eligible_opportunities(self, *, limit: int) -> list[Opportunity]:
        return list(
            await self.session.scalars(
                select(Opportunity)
                .where(Opportunity.status.in_(("candidate", "active", "review")))
                .order_by(Opportunity.last_activity_at.desc(), Opportunity.id)
                .limit(limit)
            )
        )

    async def load_active_signals(self, opportunity_id: UUID) -> list[ScoringSignalRow]:
        effective_time = func.coalesce(Signal.observed_at, Signal.created_at)
        resolved_video_id = func.coalesce(Signal.video_id, Comment.video_id)
        rows = (
            await self.session.execute(
                select(
                    Signal.id,
                    Signal.signal_type,
                    Signal.claim_status,
                    Signal.source_type,
                    effective_time,
                    OpportunitySignalLink.relationship_type,
                    resolved_video_id,
                    Video.channel_id,
                    Signal.revenue_claim_amount,
                    Signal.customer_count_claim,
                    Signal.price_min,
                    Signal.price_max,
                    Signal.technology,
                    Signal.distribution_channels,
                )
                .join(OpportunitySignalLink, OpportunitySignalLink.signal_id == Signal.id)
                .outerjoin(Comment, Comment.id == Signal.comment_id)
                .outerjoin(Video, Video.id == resolved_video_id)
                .where(
                    OpportunitySignalLink.opportunity_id == opportunity_id,
                    Signal.status == "active",
                )
                .order_by(effective_time, Signal.id)
            )
        ).all()
        return [ScoringSignalRow(*row) for row in rows]
