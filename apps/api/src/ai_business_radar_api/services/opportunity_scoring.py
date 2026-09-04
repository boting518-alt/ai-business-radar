import hashlib
import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from ai_business_radar_schemas import OpportunityScoreComponents, OpportunityScoringInput
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..domain.scoring import SCORING_VERSION, score_opportunity
from ..infrastructure.database.models import OpportunityScore, TrendSnapshot
from ..infrastructure.database.repositories import (
    OpportunityRepository,
    OpportunityScoreRepository,
    TrendRepository,
)

TREND_VERSION = "trend-v001"
ELIGIBLE_STATUSES = {"candidate", "active", "review"}


class OpportunityNotFoundError(RuntimeError):
    pass


class OpportunityNotEligibleError(RuntimeError):
    pass


class ScoringRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force: bool = False


class ScoringBatchRequest(ScoringRunRequest):
    limit: int = Field(default=100, ge=1, le=500)


class ScoringRunResult(BaseModel):
    opportunity_id: UUID
    score_id: UUID
    calculated_at: datetime
    scoring_version: str
    input_hash: str
    components: OpportunityScoreComponents
    opportunity_score: Decimal
    confidence_score: Decimal
    hype_risk_score: Decimal
    inputs_snapshot: dict
    reused: bool = False


class ScoringBatchResult(BaseModel):
    requested: int
    processed: int
    reused: int
    items: list[ScoringRunResult]


class OpportunityScoringService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    async def score(self, opportunity_id: UUID, *, force: bool = False) -> ScoringRunResult:
        now = self._clock().astimezone(UTC)
        calculated_at = now if force else now.replace(minute=0, second=0, microsecond=0)
        async with self._sessions() as session:
            opportunity = await OpportunityRepository(session).get_by_id(opportunity_id)
            if opportunity is None:
                raise OpportunityNotFoundError("Opportunity was not found")
            if opportunity.status not in ELIGIBLE_STATUSES:
                raise OpportunityNotEligibleError("Opportunity is not eligible for scoring")
            trends = TrendRepository(session)
            selected_trend = await self._select_trend(trends, opportunity_id)
            signals = await OpportunityScoreRepository(session).load_active_signals(opportunity_id)

        inputs = self._build_inputs(opportunity, selected_trend, signals, calculated_at)
        pure_result = score_opportunity(inputs)
        json_inputs = self._json_value(pure_result.inputs_snapshot)
        input_hash = self.input_hash(json_inputs)
        async with self._sessions() as session:
            repository = OpportunityScoreRepository(session)
            existing = await repository.find_by_input_identity(
                opportunity_id=opportunity_id,
                scoring_version=SCORING_VERSION,
                input_hash=input_hash,
            )
            if existing is not None:
                return self._result(existing, reused=True)

        values = pure_result.components.model_dump(mode="python")
        async with self._sessions() as session, session.begin():
            repository = OpportunityScoreRepository(session)
            existing = await repository.find_by_input_identity(
                opportunity_id=opportunity_id,
                scoring_version=SCORING_VERSION,
                input_hash=input_hash,
            )
            if existing is not None:
                score = existing
                reused = True
            else:
                score = await repository.create_score(
                    opportunity_id=opportunity_id,
                    calculated_at=calculated_at,
                    scoring_version=SCORING_VERSION,
                    input_hash=input_hash,
                    opportunity_score=pure_result.opportunity_score,
                    confidence_score=pure_result.confidence_score,
                    hype_risk_score=pure_result.hype_risk_score,
                    inputs_snapshot=json_inputs,
                    created_at=now,
                    **values,
                )
                reused = False
        return self._result(score, reused=reused)

    async def score_batch(self, request: ScoringBatchRequest) -> ScoringBatchResult:
        async with self._sessions() as session:
            opportunities = await OpportunityScoreRepository(session).list_eligible_opportunities(
                limit=request.limit
            )
        items = [await self.score(item.id, force=request.force) for item in opportunities]
        return ScoringBatchResult(
            requested=len(opportunities),
            processed=len(items),
            reused=sum(item.reused for item in items),
            items=items,
        )

    @staticmethod
    async def _select_trend(repository: TrendRepository, opportunity_id: UUID):
        for window_type in ("7d", "30d", "90d"):
            snapshot = await repository.get_latest_snapshot(
                opportunity_id,
                window_type=window_type,
                aggregation_version=TREND_VERSION,
            )
            if snapshot is not None:
                return snapshot
        return None

    @staticmethod
    def _build_inputs(opportunity, trend: TrendSnapshot | None, signals, calculated_at):
        counts = Counter(item.signal_type for item in signals)
        claim_counts = Counter(item.claim_status for item in signals)
        relationship_counts = Counter(item.relationship_type for item in signals)
        video_ids = {str(item.video_id) for item in signals if item.video_id}
        channel_ids = {str(item.channel_id) for item in signals if item.channel_id}
        technologies = sorted(
            {value for item in signals for value in (item.technology or []) if value}
        )
        distribution_channels = sorted(
            {value for item in signals for value in (item.distribution_channels or []) if value}
        )
        latest_signal_at = max((item.effective_time for item in signals), default=None)
        if trend is None:
            period_end = calculated_at
            period_start = period_end - timedelta(days=7)
            shared_trend = OpportunityScoringInput(
                opportunity_id=opportunity.id,
                window_type="7d",
                period_start=period_start,
                period_end=period_end,
                video_count=0,
                new_video_count=0,
                unique_channel_count=0,
                total_views=0,
                comment_count=0,
                pain_signal_count=0,
                demand_signal_count=0,
                purchase_intent_signal_count=0,
                revenue_signal_count=0,
                competitor_signal_count=0,
                momentum_score=None,
            )
            trend_meta = {"snapshot_id": None, "aggregation_version": None}
        else:
            shared_trend = OpportunityScoringInput(
                opportunity_id=opportunity.id,
                window_type=trend.window_type,
                period_start=trend.period_start,
                period_end=trend.period_end,
                video_count=trend.video_count,
                new_video_count=trend.new_video_count,
                unique_channel_count=trend.unique_channel_count,
                total_views=trend.total_views,
                comment_count=trend.comment_count,
                pain_signal_count=trend.pain_signal_count,
                demand_signal_count=trend.demand_signal_count,
                purchase_intent_signal_count=trend.purchase_intent_signal_count,
                revenue_signal_count=trend.revenue_signal_count,
                competitor_signal_count=trend.competitor_signal_count,
                momentum_score=trend.momentum_score,
            )
            trend_meta = {
                "snapshot_id": str(trend.id),
                "aggregation_version": trend.aggregation_version,
            }
        trend_data = shared_trend.model_dump(mode="python", exclude={"opportunity_id"})
        trend_data.update(trend_meta)
        return {
            "scoring_version": SCORING_VERSION,
            "calculated_at": calculated_at,
            "opportunity_id": str(opportunity.id),
            "trend": trend_data,
            "counts": dict(sorted(counts.items())),
            "claim_status_counts": dict(sorted(claim_counts.items())),
            "relationship_counts": {
                "supporting": relationship_counts.get("supporting", 0),
                "contradicting": relationship_counts.get("contradicting", 0),
            },
            "signals": [
                {
                    "signal_id": str(item.signal_id),
                    "signal_type": item.signal_type,
                    "claim_status": item.claim_status,
                }
                for item in signals
            ],
            "video_count": len(video_ids),
            "channel_count": len(channel_ids),
            "source_types": sorted({item.source_type for item in signals}),
            "latest_signal_at": latest_signal_at,
            "explicit_numeric_count": sum(
                item.revenue_claim_amount is not None or item.customer_count_claim is not None
                for item in signals
            ),
            "spend_evidence_count": sum(
                item.price_min is not None or item.price_max is not None for item in signals
            ),
            "primary_technology": opportunity.primary_technology,
            "technologies": technologies,
            "industry": opportunity.industry,
            "business_model": opportunity.business_model,
            "customer_type": opportunity.customer_type,
            "distribution_channels": distribution_channels,
        }

    @staticmethod
    def input_hash(inputs: dict) -> str:
        payload = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _json_value(value):
        return json.loads(json.dumps(value, default=str, sort_keys=True))

    @staticmethod
    def _result(score: OpportunityScore, *, reused: bool) -> ScoringRunResult:
        return ScoringRunResult(
            opportunity_id=score.opportunity_id,
            score_id=score.id,
            calculated_at=score.calculated_at,
            scoring_version=score.scoring_version,
            input_hash=score.input_hash,
            components=OpportunityScoreComponents(
                trend_velocity_score=score.trend_velocity_score,
                demand_evidence_score=score.demand_evidence_score,
                revenue_evidence_score=score.revenue_evidence_score,
                pain_severity_score=score.pain_severity_score,
                competition_white_space_score=score.competition_white_space_score,
                build_feasibility_score=score.build_feasibility_score,
                distribution_ease_score=score.distribution_ease_score,
            ),
            opportunity_score=score.opportunity_score,
            confidence_score=score.confidence_score,
            hype_risk_score=score.hype_risk_score,
            inputs_snapshot=score.inputs_snapshot,
            reused=reused,
        )
