from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    Opportunity,
    OpportunityScore,
    TrendSnapshot,
    UserProfile,
    Watchlist,
    WatchlistItem,
)
from ai_business_radar_api.services.watchlist import (
    WatchlistOpportunityNotVisible,
    WatchlistService,
)

NOW = datetime(2026, 9, 5, tzinfo=UTC)


async def seed(factory):
    async with factory() as session, session.begin():
        users = [
            (
                await session.execute(
                    insert(UserProfile)
                    .values(auth_user_id=uuid4(), role="user")
                    .returning(UserProfile.id)
                )
            ).scalar_one()
            for _ in range(2)
        ]
        opportunities = []
        for status in ("active", "candidate"):
            opportunities.append(
                (
                    await session.execute(
                        insert(Opportunity)
                        .values(
                            slug=f"watch-{status}-{uuid4()}",
                            name=f"Watch {status}",
                            industry="AI",
                            market_stage="emerging",
                            status=status,
                            first_detected_at=NOW,
                            last_activity_at=NOW,
                        )
                        .returning(Opportunity.id)
                    )
                ).scalar_one()
            )
        await session.execute(
            insert(OpportunityScore).values(
                opportunity_id=opportunities[0],
                scoring_version="score-v001",
                trend_velocity_score=70,
                demand_evidence_score=70,
                revenue_evidence_score=70,
                pain_severity_score=70,
                competition_white_space_score=70,
                build_feasibility_score=70,
                distribution_ease_score=70,
                opportunity_score=71,
                confidence_score=72,
                hype_risk_score=24,
                inputs_snapshot={},
                input_hash=f"watch-{uuid4()}",
                calculated_at=NOW,
            )
        )
        await session.execute(
            insert(TrendSnapshot).values(
                opportunity_id=opportunities[0],
                window_type="7d",
                period_start=NOW - timedelta(days=7),
                period_end=NOW,
                aggregation_version="trend-v001",
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
                momentum_score=63,
            )
        )
    return users, opportunities


@pytest.mark.asyncio
async def test_personal_watchlist_create_list_duplicate_and_remove(postgres_url) -> None:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    users, opportunities = await seed(factory)
    service = WatchlistService(factory)

    empty = await service.list_items(users[0])
    first = await service.add(users[0], opportunities[0])
    duplicate = await service.add(users[0], opportunities[0])
    own = await service.list_items(users[0])
    other = await service.list_items(users[1])
    await service.remove(users[1], opportunities[0])
    still_owned = await service.list_items(users[0])
    removed = await service.remove(users[0], opportunities[0])
    repeated = await service.remove(users[0], opportunities[0])
    final = await service.list_items(users[0])
    async with factory() as session:
        watchlist_count = await session.scalar(
            select(func.count(Watchlist.id)).where(Watchlist.user_profile_id == users[0])
        )
        item_count = await session.scalar(
            select(func.count(WatchlistItem.id))
            .join(Watchlist, Watchlist.id == WatchlistItem.watchlist_id)
            .where(Watchlist.user_profile_id == users[0])
        )
    await engine.dispose()

    assert empty.items == [] and other.items == []
    assert first.watchlisted and duplicate.added_at == first.added_at
    assert watchlist_count == 1 and len(own.items) == 1
    assert own.items[0].opportunity_score == 71
    assert own.items[0].confidence_score == 72
    assert own.items[0].hype_risk_score == 24
    assert own.items[0].momentum_score == 63
    assert len(still_owned.items) == 1
    assert removed.watchlisted is False and repeated.watchlisted is False
    assert final.items == [] and item_count == 0


@pytest.mark.asyncio
async def test_hidden_opportunity_cannot_be_added(postgres_url) -> None:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    users, opportunities = await seed(factory)
    with pytest.raises(WatchlistOpportunityNotVisible):
        await WatchlistService(factory).add(users[0], opportunities[1])
    await engine.dispose()
