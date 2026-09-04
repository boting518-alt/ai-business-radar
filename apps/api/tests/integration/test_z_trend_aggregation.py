from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    Channel,
    Comment,
    Opportunity,
    OpportunityScore,
    OpportunitySignalLink,
    Signal,
    TrendSnapshot,
    Video,
    VideoSnapshot,
)
from ai_business_radar_api.services.trend_aggregation import (
    AGGREGATION_VERSION,
    OpportunityTrendAggregationService,
    TrendAggregationBatchRequest,
    TrendAggregationRequest,
)

END = datetime(2026, 9, 1, tzinfo=UTC)
START = END - timedelta(days=7)


async def seed_opportunity(session, status="active"):
    return (
        await session.execute(
            insert(Opportunity)
            .values(
                slug=f"trend-{uuid4()}",
                name="Trend fixture",
                market_stage="unknown",
                status=status,
                first_detected_at=START - timedelta(days=20),
                last_activity_at=END - timedelta(hours=1),
            )
            .returning(Opportunity.id)
        )
    ).scalar_one()


async def seed_video(session, *, channel_id, first_seen_at, name):
    return (
        await session.execute(
            insert(Video)
            .values(
                youtube_video_id=f"{name}-{uuid4()}",
                channel_id=channel_id,
                title=name,
                published_at=first_seen_at,
                first_seen_at=first_seen_at,
                last_seen_at=END,
                processing_status="processed",
            )
            .returning(Video.id)
        )
    ).scalar_one()


async def seed_signal(
    session,
    *,
    opportunity_id,
    signal_type,
    observed_at,
    status="active",
    video_id=None,
    comment_id=None,
):
    source_id = video_id or comment_id
    signal_id = (
        await session.execute(
            insert(Signal)
            .values(
                source_type="video" if video_id else "comment",
                source_id=source_id,
                video_id=video_id,
                comment_id=comment_id,
                signal_type=signal_type,
                statement=f"{signal_type} fixture",
                claim_status="unknown",
                confidence=Decimal("0.8"),
                observed_at=observed_at,
                status=status,
            )
            .returning(Signal.id)
        )
    ).scalar_one()
    await session.execute(
        insert(OpportunitySignalLink).values(
            opportunity_id=opportunity_id,
            signal_id=signal_id,
            relationship_type="supporting",
            confidence=Decimal("0.8"),
        )
    )
    return signal_id


@pytest.mark.asyncio
async def test_linked_active_evidence_metrics_boundaries_views_reuse_and_force(
    postgres_url,
) -> None:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        opportunity_id = await seed_opportunity(session)
        channel_ids = []
        for index in range(2):
            channel_ids.append(
                (
                    await session.execute(
                        insert(Channel)
                        .values(
                            youtube_channel_id=f"trend-channel-{uuid4()}",
                            name=f"Channel {index}",
                            first_seen_at=START - timedelta(days=20),
                            last_seen_at=END,
                        )
                        .returning(Channel.id)
                    )
                ).scalar_one()
            )
        older_video = await seed_video(
            session,
            channel_id=channel_ids[0],
            first_seen_at=START - timedelta(days=10),
            name="older",
        )
        new_video = await seed_video(
            session,
            channel_id=channel_ids[1],
            first_seen_at=START + timedelta(hours=1),
            name="new",
        )
        comment_id = (
            await session.execute(
                insert(Comment)
                .values(
                    youtube_comment_id=f"trend-comment-{uuid4()}",
                    video_id=new_video,
                    text="Persisted demand",
                    published_at=START + timedelta(days=2),
                    first_seen_at=START + timedelta(days=2),
                )
                .returning(Comment.id)
            )
        ).scalar_one()
        await session.execute(
            insert(Comment).values(
                youtube_comment_id=f"outside-{uuid4()}",
                video_id=older_video,
                text="At exclusive end",
                published_at=END,
                first_seen_at=END,
            )
        )
        await session.execute(
            insert(VideoSnapshot).values(
                [
                    {
                        "video_id": older_video,
                        "captured_at": START - timedelta(hours=1),
                        "view_count": 50,
                    },
                    {
                        "video_id": older_video,
                        "captured_at": END - timedelta(hours=1),
                        "view_count": 100,
                    },
                    {
                        "video_id": older_video,
                        "captured_at": END + timedelta(hours=1),
                        "view_count": 999,
                    },
                ]
            )
        )
        await seed_signal(
            session,
            opportunity_id=opportunity_id,
            signal_type="pain",
            observed_at=START - timedelta(days=1),
            video_id=older_video,
        )
        for signal_type, video_id, source_comment in [
            ("pain", older_video, None),
            ("demand", None, comment_id),
            ("purchase_intent", older_video, None),
            ("revenue", older_video, None),
            ("competition", older_video, None),
        ]:
            await seed_signal(
                session,
                opportunity_id=opportunity_id,
                signal_type=signal_type,
                observed_at=START,
                video_id=video_id,
                comment_id=source_comment,
            )
        await seed_signal(
            session,
            opportunity_id=opportunity_id,
            signal_type="pain",
            observed_at=START + timedelta(days=1),
            status="review",
            video_id=older_video,
        )
        await seed_signal(
            session,
            opportunity_id=opportunity_id,
            signal_type="demand",
            observed_at=START + timedelta(days=1),
            status="rejected",
            video_id=older_video,
        )
        await seed_signal(
            session,
            opportunity_id=opportunity_id,
            signal_type="revenue",
            observed_at=END,
            video_id=older_video,
        )

    service = OpportunityTrendAggregationService(factory)
    async with factory() as session:
        score_count_before = await session.scalar(select(func.count(OpportunityScore.id)))
    request = TrendAggregationRequest(
        opportunity_id=opportunity_id, window_type="7d", period_end=END
    )
    first = await service.aggregate(request)
    reused = await service.aggregate(request)
    forced = await service.aggregate(request.model_copy(update={"force": True}))
    metrics = first.metrics
    assert (metrics.video_count, metrics.new_video_count, metrics.unique_channel_count) == (2, 1, 2)
    assert metrics.total_views == 100 and metrics.comment_count == 1
    assert (
        metrics.pain_signal_count,
        metrics.demand_signal_count,
        metrics.purchase_intent_signal_count,
        metrics.revenue_signal_count,
        metrics.competitor_signal_count,
    ) == (1, 1, 1, 1, 1)
    assert Decimal(0) <= metrics.momentum_score <= Decimal(100)
    assert reused.reused and reused.snapshot_id == first.snapshot_id == forced.snapshot_id
    assert reused.metrics == first.metrics == forced.metrics
    assert first.aggregation_version == AGGREGATION_VERSION
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count(TrendSnapshot.id)).where(
                    TrendSnapshot.opportunity_id == opportunity_id
                )
            )
            == 1
        )
        assert await session.scalar(select(func.count(OpportunityScore.id))) == score_count_before
    await engine.dispose()


@pytest.mark.asyncio
async def test_batch_excludes_merged_and_includes_candidate_active_review(postgres_url) -> None:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        eligible = [
            await seed_opportunity(session, status=status)
            for status in ("candidate", "active", "review")
        ]
        merged = await seed_opportunity(session, status="merged")
    result = await OpportunityTrendAggregationService(factory).aggregate_batch(
        TrendAggregationBatchRequest(window_type="30d", period_end=END, limit=500)
    )
    returned = {item.opportunity_id for item in result.items}
    assert set(eligible) <= returned and merged not in returned
    await engine.dispose()
