from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Comment,
    Opportunity,
    OpportunitySignalLink,
    Signal,
    TrendSnapshot,
    Video,
    VideoSnapshot,
)


@dataclass(frozen=True)
class LinkedSignalRow:
    signal_id: UUID
    signal_type: str
    effective_time: datetime
    video_id: UUID | None
    channel_id: UUID | None
    video_first_seen_at: datetime | None


class TrendRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_snapshot(
        self,
        *,
        opportunity_id: UUID,
        window_type: str,
        period_start: datetime,
        period_end: datetime,
        aggregation_version: str,
    ) -> TrendSnapshot | None:
        return await self.session.scalar(
            select(TrendSnapshot).where(
                TrendSnapshot.opportunity_id == opportunity_id,
                TrendSnapshot.window_type == window_type,
                TrendSnapshot.period_start == period_start,
                TrendSnapshot.period_end == period_end,
                TrendSnapshot.aggregation_version == aggregation_version,
            )
        )

    async def create_snapshot(self, **values: Any) -> TrendSnapshot:
        return (
            await self.session.execute(
                insert(TrendSnapshot).values(**values).returning(TrendSnapshot)
            )
        ).scalar_one()

    async def update_snapshot(self, snapshot_id: UUID, **values: Any) -> TrendSnapshot:
        return (
            await self.session.execute(
                update(TrendSnapshot)
                .where(TrendSnapshot.id == snapshot_id)
                .values(**values)
                .returning(TrendSnapshot)
            )
        ).scalar_one()

    async def list_snapshots(
        self, opportunity_id: UUID, *, window_type: str | None = None, limit: int = 100
    ) -> list[TrendSnapshot]:
        query = select(TrendSnapshot).where(TrendSnapshot.opportunity_id == opportunity_id)
        if window_type is not None:
            query = query.where(TrendSnapshot.window_type == window_type)
        return list(
            await self.session.scalars(
                query.order_by(
                    TrendSnapshot.period_end.desc(), TrendSnapshot.created_at.desc()
                ).limit(limit)
            )
        )

    async def get_latest_snapshot(
        self,
        opportunity_id: UUID,
        *,
        window_type: str,
        aggregation_version: str,
    ) -> TrendSnapshot | None:
        return await self.session.scalar(
            select(TrendSnapshot)
            .where(
                TrendSnapshot.opportunity_id == opportunity_id,
                TrendSnapshot.window_type == window_type,
                TrendSnapshot.aggregation_version == aggregation_version,
            )
            .order_by(TrendSnapshot.period_end.desc(), TrendSnapshot.created_at.desc())
            .limit(1)
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

    async def load_linked_signals(
        self, *, opportunity_id: UUID, period_start: datetime, period_end: datetime
    ) -> list[LinkedSignalRow]:
        effective_time = func.coalesce(Signal.observed_at, Signal.created_at)
        resolved_video_id = func.coalesce(Signal.video_id, Comment.video_id)
        rows = (
            await self.session.execute(
                select(
                    Signal.id,
                    Signal.signal_type,
                    effective_time,
                    resolved_video_id,
                    Video.channel_id,
                    Video.first_seen_at,
                )
                .join(OpportunitySignalLink, OpportunitySignalLink.signal_id == Signal.id)
                .outerjoin(Comment, Comment.id == Signal.comment_id)
                .outerjoin(Video, Video.id == resolved_video_id)
                .where(
                    OpportunitySignalLink.opportunity_id == opportunity_id,
                    Signal.status == "active",
                    effective_time >= period_start,
                    effective_time < period_end,
                )
                .order_by(effective_time, Signal.id)
            )
        ).all()
        return [LinkedSignalRow(*row) for row in rows]

    async def has_signal_history_before(self, *, opportunity_id: UUID, before: datetime) -> bool:
        effective_time = func.coalesce(Signal.observed_at, Signal.created_at)
        return bool(
            await self.session.scalar(
                select(func.count(Signal.id))
                .join(OpportunitySignalLink, OpportunitySignalLink.signal_id == Signal.id)
                .where(
                    OpportunitySignalLink.opportunity_id == opportunity_id,
                    Signal.status == "active",
                    effective_time < before,
                )
            )
        )

    async def count_comments(
        self, *, video_ids: set[UUID], period_start: datetime, period_end: datetime
    ) -> int:
        if not video_ids:
            return 0
        return int(
            await self.session.scalar(
                select(func.count(Comment.id)).where(
                    Comment.video_id.in_(video_ids),
                    Comment.published_at >= period_start,
                    Comment.published_at < period_end,
                )
            )
            or 0
        )

    async def latest_view_counts(
        self, *, video_ids: set[UUID], before: datetime
    ) -> dict[UUID, int]:
        if not video_ids:
            return {}
        ranked = (
            select(
                VideoSnapshot.video_id,
                VideoSnapshot.view_count,
                func.row_number()
                .over(
                    partition_by=VideoSnapshot.video_id,
                    order_by=VideoSnapshot.captured_at.desc(),
                )
                .label("position"),
            )
            .where(VideoSnapshot.video_id.in_(video_ids), VideoSnapshot.captured_at < before)
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(ranked.c.video_id, ranked.c.view_count).where(ranked.c.position == 1)
            )
        ).all()
        return {video_id: int(count) for video_id, count in rows if count is not None}
