from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select

from ai_business_radar_api.domain.scoring import score_opportunity
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    Channel,
    Opportunity,
    OpportunityScore,
    OpportunitySignalLink,
    Signal,
    TrendSnapshot,
    Video,
)
from ai_business_radar_api.services.opportunity_scoring import OpportunityScoringService

NOW = datetime(2026, 9, 5, 12, 5, tzinfo=UTC)


@pytest.mark.asyncio
async def test_score_history_reuse_force_reproduction_and_no_opportunity_mutation(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        opportunity_id = (
            await session.execute(
                insert(Opportunity)
                .values(
                    slug=f"scoring-{uuid4()}",
                    name="Scoring fixture",
                    industry="Dental",
                    customer_type="SMB",
                    business_model="SaaS subscription",
                    primary_technology="API automation software",
                    market_stage="unknown",
                    status="candidate",
                    first_detected_at=NOW - timedelta(days=30),
                    last_activity_at=NOW,
                )
                .returning(Opportunity.id)
            )
        ).scalar_one()
        channel_id = (
            await session.execute(
                insert(Channel)
                .values(
                    youtube_channel_id=f"score-channel-{uuid4()}",
                    name="Customer channel",
                    first_seen_at=NOW - timedelta(days=30),
                    last_seen_at=NOW,
                )
                .returning(Channel.id)
            )
        ).scalar_one()
        video_id = (
            await session.execute(
                insert(Video)
                .values(
                    youtube_video_id=f"score-video-{uuid4()}",
                    channel_id=channel_id,
                    title="Customer demand",
                    published_at=NOW - timedelta(days=2),
                    first_seen_at=NOW - timedelta(days=2),
                    last_seen_at=NOW,
                    processing_status="processed",
                )
                .returning(Video.id)
            )
        ).scalar_one()
        await session.execute(
            insert(TrendSnapshot).values(
                opportunity_id=opportunity_id,
                window_type="30d",
                period_start=NOW - timedelta(days=30),
                period_end=NOW,
                aggregation_version="trend-v001",
                video_count=1,
                new_video_count=1,
                unique_channel_count=1,
                total_views=5000,
                comment_count=2,
                demand_signal_count=1,
                momentum_score=Decimal(72),
            )
        )
        signal_id = (
            await session.execute(
                insert(Signal)
                .values(
                    source_type="video",
                    source_id=video_id,
                    video_id=video_id,
                    signal_type="revenue",
                    statement="Customer reports revenue",
                    revenue_claim_amount=1000,
                    revenue_claim_currency="USD",
                    claim_status="creator_claim",
                    confidence=Decimal("0.9"),
                    observed_at=NOW - timedelta(days=1),
                    status="active",
                    technology=["API"],
                    distribution_channels=["outbound"],
                )
                .returning(Signal.id)
            )
        ).scalar_one()
        await session.execute(
            insert(OpportunitySignalLink).values(
                opportunity_id=opportunity_id,
                signal_id=signal_id,
                relationship_type="supporting",
            )
        )

    service = OpportunityScoringService(factory, clock=lambda: NOW)
    first = await service.score(opportunity_id)
    reused = await service.score(opportunity_id)
    forced = await service.score(opportunity_id, force=True)
    async with factory() as session:
        opportunity = await session.get(Opportunity, opportunity_id)
        rows = list(
            await session.scalars(
                select(OpportunityScore)
                .where(OpportunityScore.opportunity_id == opportunity_id)
                .order_by(OpportunityScore.calculated_at)
            )
        )
    assert first.inputs_snapshot["trend"]["window_type"] == "30d"
    assert reused.reused and reused.score_id == first.score_id
    assert forced.score_id != first.score_id and len(rows) == 2
    assert opportunity.market_stage == "unknown" and not hasattr(opportunity, "opportunity_score")
    reproduced = score_opportunity(rows[0].inputs_snapshot)
    assert reproduced.opportunity_score == rows[0].opportunity_score
    assert reproduced.components.trend_velocity_score == rows[0].trend_velocity_score
    assert reproduced.confidence_score == rows[0].confidence_score
    assert reproduced.hype_risk_score == rows[0].hype_risk_score
    assert rows[0].input_hash != rows[1].input_hash
    await engine.dispose()


@pytest.mark.asyncio
async def test_sparse_scoring_and_batch_exclude_merged(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        ids = {}
        for status in ("candidate", "active", "review", "merged"):
            ids[status] = (
                await session.execute(
                    insert(Opportunity)
                    .values(
                        slug=f"score-{status}-{uuid4()}",
                        name=status,
                        market_stage="unknown",
                        status=status,
                        first_detected_at=NOW,
                        last_activity_at=NOW,
                    )
                    .returning(Opportunity.id)
                )
            ).scalar_one()
    sparse = await OpportunityScoringService(factory, clock=lambda: NOW).score(ids["candidate"])
    assert sparse.components.trend_velocity_score == Decimal(50)
    assert sparse.confidence_score < Decimal(50)
    from ai_business_radar_api.services.opportunity_scoring import ScoringBatchRequest

    batch = await OpportunityScoringService(factory, clock=lambda: NOW).score_batch(
        ScoringBatchRequest(limit=500)
    )
    returned = {item.opportunity_id for item in batch.items}
    assert ids["active"] in returned and ids["review"] in returned and ids["merged"] not in returned
    async with factory() as session:
        assert await session.scalar(select(func.count(OpportunityScore.id))) >= 1
    await engine.dispose()
