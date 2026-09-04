from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ai_business_radar_api.infrastructure.database.models import (
    AIExtraction,
    Channel,
    OpportunityScore,
    TrendSnapshot,
    UserProfile,
)
from ai_business_radar_api.infrastructure.database.repositories import (
    ChannelRepository,
    CommentRepository,
    OpportunityRepository,
    ReviewTaskRepository,
    SignalRepository,
    UserProfileRepository,
    VideoRepository,
    WatchlistRepository,
)


@pytest.mark.asyncio
async def test_core_repository_flow_and_append_only_records(db_session: AsyncSession) -> None:
    now = datetime.now(UTC)
    channels = ChannelRepository(db_session)
    channel = await channels.upsert_channel(
        youtube_channel_id="UC-1",
        name="Original",
        first_seen_at=now,
        last_seen_at=now,
    )
    original_first_seen = channel.first_seen_at
    channel = await channels.upsert_channel(
        youtube_channel_id="UC-1",
        name="Updated",
        first_seen_at=now + timedelta(days=1),
        last_seen_at=now + timedelta(days=1),
    )
    assert channel.name == "Updated"
    assert channel.first_seen_at == original_first_seen
    assert (await channels.get_by_id(channel.id)).youtube_channel_id == "UC-1"
    assert (await channels.get_by_youtube_channel_id("UC-1")).id == channel.id

    videos = VideoRepository(db_session)
    video = await videos.create_or_update_video(
        youtube_video_id="vid-1",
        channel_id=channel.id,
        title="Video",
        published_at=now,
        first_seen_at=now,
        last_seen_at=now,
        processing_status="new",
    )
    assert (await videos.get_by_id(video.id)).title == "Video"
    assert (await videos.get_by_youtube_video_id("vid-1")).id == video.id
    assert [item.id for item in await videos.list_by_processing_status("new")] == [video.id]
    snapshot = await videos.add_snapshot(video_id=video.id, captured_at=now, view_count=10)
    assert snapshot.video_id == video.id

    comments = CommentRepository(db_session)
    comment = await comments.upsert_comment(
        youtube_comment_id="comment-1",
        video_id=video.id,
        text="Need this",
        published_at=now,
        first_seen_at=now,
    )
    assert (await comments.get_by_youtube_comment_id("comment-1")).id == comment.id
    assert [item.id for item in await comments.list_for_video(video.id)] == [comment.id]

    extraction_id = (
        await db_session.execute(
            insert(AIExtraction)
            .values(
                source_type="video",
                source_id=video.id,
                video_id=video.id,
                task_type="signal_extractor",
                provider="test",
                model="test-model",
                prompt_version="v001",
                input_hash="hash",
                status="completed",
                raw_output={},
                parsed_output={},
                started_at=now,
                completed_at=now,
            )
            .returning(AIExtraction.id)
        )
    ).scalar_one()
    signals = SignalRepository(db_session)
    signal = await signals.create_signal(
        source_type="video",
        source_id=video.id,
        video_id=video.id,
        ai_extraction_id=extraction_id,
        signal_type="demand",
        statement="Demand exists",
        claim_status="creator_claim",
        confidence=Decimal("0.8"),
        status="active",
    )
    assert (await signals.get_by_id(signal.id)).statement == "Demand exists"
    assert [item.id for item in await signals.list_for_video(video.id)] == [signal.id]
    assert (await signals.update_status(signal.id, "review")).status == "review"

    opportunities = OpportunityRepository(db_session)
    opportunity = await opportunities.create_opportunity(
        slug="ai-radar",
        name="AI Radar",
        market_stage="emerging",
        status="candidate",
        first_detected_at=now,
        last_activity_at=now,
    )
    assert (await opportunities.get_by_slug("ai-radar")).id == opportunity.id
    assert [item.id for item in await opportunities.list_candidates()] == [opportunity.id]
    link = await opportunities.link_signal(
        opportunity_id=opportunity.id, signal_id=signal.id, relationship_type="supporting"
    )
    assert link.signal_id == signal.id
    evidence = await opportunities.add_evidence(
        opportunity_id=opportunity.id,
        source_type="youtube_video",
        video_id=video.id,
        signal_id=signal.id,
        evidence_type="demand",
        summary="Evidence",
    )
    assert evidence.opportunity_id == opportunity.id

    await db_session.execute(
        insert(TrendSnapshot).values(
            opportunity_id=opportunity.id,
            window_type="7d",
            period_start=now,
            period_end=now + timedelta(days=7),
        )
    )
    for offset, score in enumerate((40, 70)):
        await db_session.execute(
            insert(OpportunityScore).values(
                opportunity_id=opportunity.id,
                calculated_at=now + timedelta(hours=offset),
                scoring_version="v001",
                trend_velocity_score=score,
                demand_evidence_score=score,
                revenue_evidence_score=score,
                pain_severity_score=score,
                competition_white_space_score=score,
                build_feasibility_score=score,
                distribution_ease_score=score,
                opportunity_score=score,
                inputs_snapshot={},
            )
        )
    assert (await opportunities.get_latest_score(opportunity.id)).opportunity_score == 70
    assert len(await opportunities.list_recent_trends(opportunity.id)) == 1

    reviews = ReviewTaskRepository(db_session)
    review = await reviews.create_review_task(
        review_type="quality_review",
        target_type="opportunity",
        target_id=opportunity.id,
        status="pending",
        priority=1,
    )
    assert [item.id for item in await reviews.list_pending()] == [review.id]

    profile_id = (
        await db_session.execute(
            insert(UserProfile).values(auth_user_id=uuid4(), role="user").returning(UserProfile.id)
        )
    ).scalar_one()
    assert (
        await UserProfileRepository(db_session).get_by_auth_user_id(
            (await db_session.get(UserProfile, profile_id)).auth_user_id
        )
    ).id == profile_id
    watchlists = WatchlistRepository(db_session)
    watchlist = await watchlists.create_watchlist(user_profile_id=profile_id, name="Default")
    await watchlists.add_item(watchlist_id=watchlist.id, opportunity_id=opportunity.id)
    assert len(await watchlists.list_items(watchlist.id)) == 1
    assert await watchlists.remove_item(watchlist.id, opportunity.id)
    assert await watchlists.list_items(watchlist.id) == []


@pytest.mark.asyncio
async def test_database_constraints_are_enforced(db_session: AsyncSession) -> None:
    now = datetime.now(UTC)
    channels = ChannelRepository(db_session)
    channel = await channels.upsert_channel(
        youtube_channel_id="UC-constraints",
        name="Channel",
        first_seen_at=now,
        last_seen_at=now,
    )
    videos = VideoRepository(db_session)
    video = await videos.create_or_update_video(
        youtube_video_id="vid-constraints",
        channel_id=channel.id,
        title="Video",
        published_at=now,
        first_seen_at=now,
        last_seen_at=now,
        processing_status="new",
    )
    await videos.add_snapshot(video_id=video.id, captured_at=now)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await videos.add_snapshot(video_id=video.id, captured_at=now)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await SignalRepository(db_session).create_signal(
                source_type="video",
                source_id=video.id,
                signal_type="demand",
                statement="bad",
                claim_status="fact",
                confidence=1,
                status="active",
            )

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                insert(AIExtraction).values(
                    source_type="video",
                    source_id=video.id,
                    task_type="signal_extractor",
                    provider="test",
                    model="model",
                    prompt_version="v001",
                    input_hash="hash",
                    status="pending",
                )
            )

    reviews = ReviewTaskRepository(db_session)
    target_id = uuid4()
    await reviews.create_review_task(
        review_type="quality_review",
        target_type="opportunity",
        target_id=target_id,
        status="pending",
        priority=1,
    )
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await reviews.create_review_task(
                review_type="quality_review",
                target_type="opportunity",
                target_id=target_id,
                status="in_review",
                priority=2,
            )

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(delete(Channel).where(Channel.id == channel.id))


@pytest.mark.asyncio
async def test_transaction_rollback(postgres_url: str) -> None:
    from ai_business_radar_api.infrastructure.database import (
        create_database_engine,
        create_session_factory,
    )

    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    external_id = "rolled-back"
    with pytest.raises(RuntimeError):
        async with factory() as session, session.begin():
            await ChannelRepository(session).upsert_channel(
                youtube_channel_id=external_id,
                name="Rollback",
                first_seen_at=datetime.now(UTC),
                last_seen_at=datetime.now(UTC),
            )
            raise RuntimeError("force rollback")
    async with factory() as session:
        assert await ChannelRepository(session).get_by_youtube_channel_id(external_id) is None
    await engine.dispose()
