from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Channel,
    Comment,
    Opportunity,
    OpportunityEvidence,
    OpportunityScore,
    OpportunitySignalLink,
    Signal,
    TrendSnapshot,
    Video,
    Watchlist,
    WatchlistItem,
)


class RadarQueryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active_opportunities(self):
        return list(
            await self.session.scalars(
                select(Opportunity).where(Opportunity.status == "active").order_by(Opportunity.id)
            )
        )

    async def get_visible_opportunity(self, identifier: str):
        try:
            entity_id = UUID(identifier)
        except ValueError:
            entity_id = None
        return await self.session.scalar(
            select(Opportunity).where(
                Opportunity.status == "active",
                or_(Opportunity.id == entity_id, Opportunity.slug == identifier)
                if entity_id
                else Opportunity.slug == identifier,
            )
        )

    async def latest_scores(self, ids):
        if not ids:
            return {}
        rows = await self.session.scalars(
            select(OpportunityScore)
            .distinct(OpportunityScore.opportunity_id)
            .where(
                OpportunityScore.opportunity_id.in_(ids),
                OpportunityScore.scoring_version == "score-v001",
            )
            .order_by(
                OpportunityScore.opportunity_id,
                OpportunityScore.calculated_at.desc(),
                OpportunityScore.id.desc(),
            )
        )
        return {row.opportunity_id: row for row in rows}

    async def latest_trends(self, ids, window):
        if not ids:
            return {}
        rows = await self.session.scalars(
            select(TrendSnapshot)
            .distinct(TrendSnapshot.opportunity_id)
            .where(
                TrendSnapshot.opportunity_id.in_(ids),
                TrendSnapshot.window_type == window,
                TrendSnapshot.aggregation_version == "trend-v001",
            )
            .order_by(
                TrendSnapshot.opportunity_id,
                TrendSnapshot.period_end.desc(),
                TrendSnapshot.id.desc(),
            )
        )
        return {row.opportunity_id: row for row in rows}

    async def evidence_summaries(self, ids):
        if not ids:
            return {}
        rows = await self.session.execute(
            select(
                OpportunitySignalLink.opportunity_id.label("opportunity_id"),
                func.count(func.distinct(Signal.id)).label("active_signal_count"),
                func.count(func.distinct(Video.id)).label("distinct_video_count"),
                func.count(func.distinct(Channel.id)).label("distinct_channel_count"),
                func.count(func.distinct(Signal.id))
                .filter(Signal.signal_type == "pain")
                .label("pain_signal_count"),
                func.count(func.distinct(Signal.id))
                .filter(Signal.signal_type == "demand")
                .label("demand_signal_count"),
                func.count(func.distinct(Signal.id))
                .filter(Signal.signal_type == "purchase_intent")
                .label("purchase_intent_signal_count"),
                func.count(func.distinct(Signal.id))
                .filter(Signal.signal_type == "revenue")
                .label("revenue_signal_count"),
            )
            .join(Signal, Signal.id == OpportunitySignalLink.signal_id)
            .outerjoin(Comment, Comment.id == Signal.comment_id)
            .outerjoin(Video, Video.id == func.coalesce(Signal.video_id, Comment.video_id))
            .outerjoin(Channel, Channel.id == Video.channel_id)
            .where(OpportunitySignalLink.opportunity_id.in_(ids), Signal.status == "active")
            .group_by(OpportunitySignalLink.opportunity_id)
        )
        return {
            row.opportunity_id: {
                key: value for key, value in row._mapping.items() if key != "opportunity_id"
            }
            for row in rows
        }

    async def watchlisted_ids(self, user_id, ids):
        if not ids:
            return set()
        return set(
            await self.session.scalars(
                select(WatchlistItem.opportunity_id)
                .join(Watchlist)
                .where(Watchlist.user_profile_id == user_id, WatchlistItem.opportunity_id.in_(ids))
                .distinct()
            )
        )

    async def trend_history(self, opportunity_id, window, limit):
        query = select(TrendSnapshot).where(TrendSnapshot.opportunity_id == opportunity_id)
        if window:
            query = query.where(TrendSnapshot.window_type == window)
        rows = list(
            await self.session.scalars(
                query.order_by(TrendSnapshot.period_end.desc(), TrendSnapshot.id.desc()).limit(
                    limit
                )
            )
        )
        return list(reversed(rows))

    async def score_history(self, opportunity_id, limit):
        rows = list(
            await self.session.scalars(
                select(OpportunityScore)
                .where(OpportunityScore.opportunity_id == opportunity_id)
                .order_by(OpportunityScore.calculated_at.desc(), OpportunityScore.id.desc())
                .limit(limit)
            )
        )
        return list(reversed(rows))

    async def evidence(self, opportunity_id, offset, limit):
        return list(
            await self.session.execute(
                select(
                    OpportunityEvidence.id.label("evidence_id"),
                    OpportunityEvidence.evidence_type,
                    OpportunityEvidence.summary,
                    OpportunityEvidence.source_type,
                    OpportunityEvidence.observed_at,
                    OpportunityEvidence.strength,
                    OpportunityEvidence.confidence,
                    Video.youtube_video_id,
                    Video.title.label("video_title"),
                )
                .outerjoin(Video, Video.id == OpportunityEvidence.video_id)
                .where(OpportunityEvidence.opportunity_id == opportunity_id)
                .order_by(
                    OpportunityEvidence.observed_at.desc().nulls_last(), OpportunityEvidence.id
                )
                .offset(offset)
                .limit(limit)
            )
        )

    async def active_signals(
        self,
        *,
        signal_type=None,
        industry=None,
        customer_type=None,
        opportunity_id=None,
        observed_after=None,
        offset=0,
        limit=50,
    ):
        opportunity_ids = func.array_agg(
            func.distinct(OpportunitySignalLink.opportunity_id)
        ).filter(
            OpportunitySignalLink.opportunity_id.is_not(None),
            Opportunity.status == "active",
        )
        query = (
            select(
                Signal.id,
                Signal.signal_type,
                Signal.statement,
                Signal.evidence_text,
                Signal.industry,
                Signal.customer_type,
                Signal.claim_status,
                Signal.confidence,
                Signal.evidence_strength,
                Signal.observed_at,
                Signal.source_type,
                Video.title.label("video_title"),
                opportunity_ids.label("opportunity_ids"),
            )
            .outerjoin(Comment, Comment.id == Signal.comment_id)
            .outerjoin(Video, Video.id == func.coalesce(Signal.video_id, Comment.video_id))
            .outerjoin(OpportunitySignalLink, OpportunitySignalLink.signal_id == Signal.id)
            .outerjoin(Opportunity, Opportunity.id == OpportunitySignalLink.opportunity_id)
            .where(Signal.status == "active")
            .group_by(Signal.id, Video.title)
        )
        if signal_type:
            query = query.where(Signal.signal_type == signal_type)
        if industry:
            query = query.where(Signal.industry == industry)
        if customer_type:
            query = query.where(Signal.customer_type == customer_type)
        if opportunity_id:
            query = query.where(
                OpportunitySignalLink.opportunity_id == opportunity_id,
                Opportunity.status == "active",
            )
        if observed_after:
            query = query.where(Signal.observed_at >= observed_after)
        return list(
            await self.session.execute(
                query.order_by(
                    Signal.observed_at.desc().nulls_last(), Signal.created_at.desc(), Signal.id
                )
                .offset(offset)
                .limit(limit)
            )
        )
