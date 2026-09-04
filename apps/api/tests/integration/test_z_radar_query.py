from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import insert

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    Opportunity,
    OpportunityScore,
    TrendSnapshot,
    UserProfile,
)
from ai_business_radar_api.services.radar_query import (
    OpportunityNotVisibleError,
    RadarQueryService,
    RadarRequest,
)

NOW = datetime(2026, 9, 5, tzinfo=UTC)


def score_values(opportunity_id, value, when):
    return dict(
        opportunity_id=opportunity_id,
        calculated_at=when,
        scoring_version="score-v001",
        input_hash=f"{opportunity_id}-{value}-{when.isoformat()}",
        trend_velocity_score=value,
        demand_evidence_score=value,
        revenue_evidence_score=value,
        pain_severity_score=value,
        competition_white_space_score=value,
        build_feasibility_score=value,
        distribution_ease_score=value,
        opportunity_score=value,
        confidence_score=value - 5,
        hype_risk_score=100 - value,
        inputs_snapshot={},
        created_at=when,
    )


@pytest.mark.asyncio
async def test_radar_visibility_latest_intelligence_sort_and_detail(postgres_url) -> None:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    marker = f"radar-{uuid4()}"
    async with factory() as session, session.begin():
        user_id = (
            await session.execute(
                insert(UserProfile)
                .values(auth_user_id=uuid4(), role="user")
                .returning(UserProfile.id)
            )
        ).scalar_one()
        active_ids = []
        for index, value in enumerate((80, 60)):
            active_ids.append(
                (
                    await session.execute(
                        insert(Opportunity)
                        .values(
                            slug=f"active-radar-{index}-{uuid4()}",
                            name=f"Active Radar {marker} {index}",
                            industry="Dental" if index == 0 else "Legal",
                            business_model="saas",
                            market_stage="accelerating",
                            status="active",
                            first_detected_at=NOW - timedelta(days=10),
                            last_activity_at=NOW - timedelta(days=index),
                        )
                        .returning(Opportunity.id)
                    )
                ).scalar_one()
            )
            await session.execute(
                insert(OpportunityScore).values(
                    score_values(active_ids[-1], value - 20, NOW - timedelta(days=1))
                )
            )
            await session.execute(
                insert(OpportunityScore).values(score_values(active_ids[-1], value, NOW))
            )
        hidden_id = (
            await session.execute(
                insert(Opportunity)
                .values(
                    slug=f"candidate-{uuid4()}",
                    name="Hidden candidate",
                    market_stage="unknown",
                    status="candidate",
                    first_detected_at=NOW,
                    last_activity_at=NOW,
                )
                .returning(Opportunity.id)
            )
        ).scalar_one()
        await session.execute(
            insert(TrendSnapshot).values(
                opportunity_id=active_ids[0],
                window_type="7d",
                period_start=NOW - timedelta(days=7),
                period_end=NOW,
                aggregation_version="trend-v001",
                video_count=2,
                new_video_count=1,
                unique_channel_count=2,
                total_views=1000,
                comment_count=3,
                pain_signal_count=1,
                demand_signal_count=1,
                purchase_intent_signal_count=0,
                revenue_signal_count=0,
                competitor_signal_count=0,
                momentum_score=75,
                created_at=NOW,
            )
        )
    service = RadarQueryService(factory)
    radar = await service.radar(user_id, RadarRequest(q=marker))
    filtered = await service.radar(user_id, RadarRequest(q=marker, industry=["Dental"]))
    detail = await service.detail(user_id, str(active_ids[0]))
    scores = await service.scores(str(active_ids[0]), 1)
    trends = await service.trends(str(active_ids[0]), "7d", 10)
    signals = await service.signals(limit=10)
    with pytest.raises(OpportunityNotVisibleError):
        await service.detail(user_id, str(hidden_id))
    await engine.dispose()
    assert [item.id for item in radar.items] == active_ids
    assert radar.items[0].opportunity_score == 80 and radar.items[0].trend.momentum_score == 75
    assert radar.items[1].trend is None
    assert [item.id for item in filtered.items] == [active_ids[0]]
    assert detail.current_intelligence.opportunity_score == 80
    assert detail.trend_summary["30d"] is None
    assert len(scores) == 1 and scores[0].opportunity_score == 80
    assert len(trends) == 1
    assert all(not hasattr(item, "author_hash") for item in signals)
