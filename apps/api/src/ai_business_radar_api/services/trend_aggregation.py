import logging
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from uuid import UUID

from ai_business_radar_schemas.enums import TrendWindowType
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.database.models import TrendSnapshot
from ..infrastructure.database.repositories import (
    LinkedSignalRow,
    OpportunityRepository,
    TrendRepository,
)

logger = logging.getLogger(__name__)

AGGREGATION_VERSION = "trend-v001"
NEUTRAL_GROWTH = Decimal("50.00")
GROWTH_SCALE = Decimal(50) / Decimal(2).ln()
SCORE_QUANTUM = Decimal("0.01")
WINDOW_DAYS = {"7d": 7, "30d": 30, "90d": 90}
ELIGIBLE_OPPORTUNITY_STATUSES = {"candidate", "active", "review"}
MOMENTUM_WEIGHTS = {
    "signal_growth": Decimal("0.35"),
    "video_growth": Decimal("0.30"),
    "channel_growth": Decimal("0.20"),
    "view_growth": Decimal("0.15"),
}


class OpportunityNotFoundError(RuntimeError):
    pass


class OpportunityNotEligibleError(RuntimeError):
    pass


class TrendAggregationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opportunity_id: UUID | None = None
    window_type: TrendWindowType = TrendWindowType.DAYS_7
    period_end: datetime | None = None
    force: bool = False

    @field_validator("period_end")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("period_end must include a timezone")
        return value.astimezone(UTC) if value else None


class TrendAggregationBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    window_type: TrendWindowType = TrendWindowType.DAYS_7
    period_end: datetime | None = None
    limit: int = Field(default=100, ge=1, le=500)
    force: bool = False

    @field_validator("period_end")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        return TrendAggregationRequest.require_timezone(value)


class TrendAggregationMetrics(BaseModel):
    video_count: int
    new_video_count: int
    unique_channel_count: int
    total_views: int
    comment_count: int
    pain_signal_count: int
    demand_signal_count: int
    purchase_intent_signal_count: int
    revenue_signal_count: int
    competitor_signal_count: int
    momentum_score: Decimal = Field(ge=0, le=100)


class TrendAggregationResult(BaseModel):
    opportunity_id: UUID
    snapshot_id: UUID
    window_type: TrendWindowType
    period_start: datetime
    period_end: datetime
    aggregation_version: str
    metrics: TrendAggregationMetrics
    reused: bool = False


class TrendAggregationBatchResult(BaseModel):
    requested: int
    processed: int
    reused: int
    items: list[TrendAggregationResult]


class _PeriodMetrics(BaseModel):
    signal_count: int
    video_count: int
    new_video_count: int
    unique_channel_count: int
    total_views: int
    comment_count: int
    pain_signal_count: int
    demand_signal_count: int
    purchase_intent_signal_count: int
    revenue_signal_count: int
    competitor_signal_count: int
    views_available: bool


class OpportunityTrendAggregationService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def aggregate(self, request: TrendAggregationRequest) -> TrendAggregationResult:
        if request.opportunity_id is None:
            raise ValueError("opportunity_id is required for single aggregation")
        period_start, period_end = self.period_boundaries(
            request.window_type.value, request.period_end
        )
        async with self._sessions() as session:
            opportunity = await OpportunityRepository(session).get_by_id(request.opportunity_id)
            if opportunity is None:
                raise OpportunityNotFoundError("Opportunity was not found")
            if opportunity.status not in ELIGIBLE_OPPORTUNITY_STATUSES:
                raise OpportunityNotEligibleError("Opportunity is not eligible for aggregation")
            repository = TrendRepository(session)
            existing = await repository.get_snapshot(
                opportunity_id=opportunity.id,
                window_type=request.window_type.value,
                period_start=period_start,
                period_end=period_end,
                aggregation_version=AGGREGATION_VERSION,
            )
            if existing is not None and not request.force:
                return self._result_from_snapshot(existing, reused=True)

        previous_start = period_start - (period_end - period_start)
        async with self._sessions() as session:
            repository = TrendRepository(session)
            current_rows = await repository.load_linked_signals(
                opportunity_id=request.opportunity_id,
                period_start=period_start,
                period_end=period_end,
            )
            previous_rows = await repository.load_linked_signals(
                opportunity_id=request.opportunity_id,
                period_start=previous_start,
                period_end=period_start,
            )
            has_history = await repository.has_signal_history_before(
                opportunity_id=request.opportunity_id, before=period_start
            )
            current = await self._period_metrics(repository, current_rows, period_start, period_end)
            previous = await self._period_metrics(
                repository, previous_rows, previous_start, period_start
            )

        metrics = self._combine_metrics(current, previous, has_history=has_history)
        values = {
            "video_count": metrics.video_count,
            "new_video_count": metrics.new_video_count,
            "unique_channel_count": metrics.unique_channel_count,
            "total_views": metrics.total_views,
            "comment_count": metrics.comment_count,
            "pain_signal_count": metrics.pain_signal_count,
            "demand_signal_count": metrics.demand_signal_count,
            "purchase_intent_signal_count": metrics.purchase_intent_signal_count,
            "revenue_signal_count": metrics.revenue_signal_count,
            "competitor_signal_count": metrics.competitor_signal_count,
            "momentum_score": metrics.momentum_score,
        }
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            repository = TrendRepository(session)
            existing = await repository.get_snapshot(
                opportunity_id=request.opportunity_id,
                window_type=request.window_type.value,
                period_start=period_start,
                period_end=period_end,
                aggregation_version=AGGREGATION_VERSION,
            )
            if existing is not None:
                snapshot = await repository.update_snapshot(existing.id, **values)
            else:
                snapshot = await repository.create_snapshot(
                    opportunity_id=request.opportunity_id,
                    window_type=request.window_type.value,
                    period_start=period_start,
                    period_end=period_end,
                    aggregation_version=AGGREGATION_VERSION,
                    created_at=now,
                    **values,
                )
        logger.info(
            "trend_aggregation_completed opportunity_id=%s window_type=%s period_start=%s "
            "period_end=%s aggregation_version=%s signal_count=%s video_count=%s "
            "channel_count=%s momentum_score=%s",
            request.opportunity_id,
            request.window_type.value,
            period_start.isoformat(),
            period_end.isoformat(),
            AGGREGATION_VERSION,
            current.signal_count,
            current.video_count,
            current.unique_channel_count,
            metrics.momentum_score,
        )
        return TrendAggregationResult(
            opportunity_id=request.opportunity_id,
            snapshot_id=snapshot.id,
            window_type=request.window_type,
            period_start=period_start,
            period_end=period_end,
            aggregation_version=AGGREGATION_VERSION,
            metrics=metrics,
        )

    async def aggregate_batch(
        self, request: TrendAggregationBatchRequest
    ) -> TrendAggregationBatchResult:
        async with self._sessions() as session:
            opportunities = await TrendRepository(session).list_eligible_opportunities(
                limit=request.limit
            )
        items = [
            await self.aggregate(
                TrendAggregationRequest(
                    opportunity_id=opportunity.id,
                    window_type=request.window_type,
                    period_end=request.period_end,
                    force=request.force,
                )
            )
            for opportunity in opportunities
        ]
        return TrendAggregationBatchResult(
            requested=len(opportunities),
            processed=len(items),
            reused=sum(item.reused for item in items),
            items=items,
        )

    @staticmethod
    def period_boundaries(
        window_type: str, period_end: datetime | None
    ) -> tuple[datetime, datetime]:
        if window_type not in WINDOW_DAYS:
            raise ValueError("Unsupported trend window")
        end = (
            period_end.astimezone(UTC)
            if period_end
            else datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        )
        return end - timedelta(days=WINDOW_DAYS[window_type]), end

    @staticmethod
    async def _period_metrics(
        repository: TrendRepository,
        rows: list[LinkedSignalRow],
        period_start: datetime,
        period_end: datetime,
    ) -> _PeriodMetrics:
        video_ids = {row.video_id for row in rows if row.video_id is not None}
        channel_ids = {row.channel_id for row in rows if row.channel_id is not None}
        view_counts = await repository.latest_view_counts(video_ids=video_ids, before=period_end)
        comments = await repository.count_comments(
            video_ids=video_ids, period_start=period_start, period_end=period_end
        )
        counts = {
            signal_type: sum(row.signal_type == signal_type for row in rows)
            for signal_type in ("pain", "demand", "purchase_intent", "revenue", "competition")
        }
        return _PeriodMetrics(
            signal_count=len(rows),
            video_count=len(video_ids),
            new_video_count=len(
                {
                    row.video_id
                    for row in rows
                    if row.video_id is not None
                    and row.video_first_seen_at is not None
                    and period_start <= row.video_first_seen_at < period_end
                }
            ),
            unique_channel_count=len(channel_ids),
            total_views=sum(view_counts.values()),
            comment_count=comments,
            pain_signal_count=counts["pain"],
            demand_signal_count=counts["demand"],
            purchase_intent_signal_count=counts["purchase_intent"],
            revenue_signal_count=counts["revenue"],
            competitor_signal_count=counts["competition"],
            views_available=len(view_counts) == len(video_ids),
        )

    @classmethod
    def _combine_metrics(
        cls, current: _PeriodMetrics, previous: _PeriodMetrics, *, has_history: bool
    ) -> TrendAggregationMetrics:
        if not has_history:
            growth = {name: NEUTRAL_GROWTH for name in MOMENTUM_WEIGHTS}
        else:
            growth = {
                "signal_growth": cls.normalize_growth(current.signal_count, previous.signal_count),
                "video_growth": cls.normalize_growth(
                    current.new_video_count, previous.new_video_count
                ),
                "channel_growth": cls.normalize_growth(
                    current.unique_channel_count, previous.unique_channel_count
                ),
                "view_growth": (
                    cls.normalize_growth(current.total_views, previous.total_views)
                    if current.views_available and previous.views_available
                    else NEUTRAL_GROWTH
                ),
            }
        momentum = sum(growth[name] * weight for name, weight in MOMENTUM_WEIGHTS.items())
        return TrendAggregationMetrics(
            **current.model_dump(exclude={"signal_count", "views_available"}),
            momentum_score=momentum.quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP),
        )

    @staticmethod
    def normalize_growth(current: int, previous: int) -> Decimal:
        with localcontext() as context:
            context.prec = 28
            ratio = (Decimal(current) + 1) / (Decimal(previous) + 1)
            score = Decimal(50) + GROWTH_SCALE * ratio.ln()
        return min(Decimal(100), max(Decimal(0), score)).quantize(
            SCORE_QUANTUM, rounding=ROUND_HALF_UP
        )

    @staticmethod
    def _result_from_snapshot(snapshot: TrendSnapshot, *, reused: bool) -> TrendAggregationResult:
        metrics = TrendAggregationMetrics(
            video_count=snapshot.video_count,
            new_video_count=snapshot.new_video_count,
            unique_channel_count=snapshot.unique_channel_count,
            total_views=snapshot.total_views,
            comment_count=snapshot.comment_count,
            pain_signal_count=snapshot.pain_signal_count,
            demand_signal_count=snapshot.demand_signal_count,
            purchase_intent_signal_count=snapshot.purchase_intent_signal_count,
            revenue_signal_count=snapshot.revenue_signal_count,
            competitor_signal_count=snapshot.competitor_signal_count,
            momentum_score=snapshot.momentum_score or NEUTRAL_GROWTH,
        )
        return TrendAggregationResult(
            opportunity_id=snapshot.opportunity_id,
            snapshot_id=snapshot.id,
            window_type=snapshot.window_type,
            period_start=snapshot.period_start,
            period_end=snapshot.period_end,
            aggregation_version=snapshot.aggregation_version,
            metrics=metrics,
            reused=reused,
        )
