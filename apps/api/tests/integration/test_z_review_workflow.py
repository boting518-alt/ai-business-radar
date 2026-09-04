from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from ai_business_radar_schemas import ReviewDecisionRequest
from sqlalchemy import func, insert, select

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    Channel,
    Opportunity,
    OpportunityMergeHistory,
    OpportunitySignalLink,
    ReviewTask,
    Signal,
    UserProfile,
    Video,
    Watchlist,
    WatchlistItem,
)
from ai_business_radar_api.services.review_workflow import (
    InvalidMergeTarget,
    InvalidReviewDecision,
    OpportunityMergeCycleError,
    ReviewAssignmentConflict,
    ReviewTaskAlreadyResolved,
    ReviewWorkflowService,
)

NOW = datetime(2026, 9, 5, tzinfo=UTC)


async def seed(factory):
    async with factory() as session, session.begin():
        admins = []
        for role in ("admin", "admin"):
            admins.append(
                (
                    await session.execute(
                        insert(UserProfile)
                        .values(auth_user_id=uuid4(), role=role)
                        .returning(UserProfile.id)
                    )
                ).scalar_one()
            )
        channel_id = (
            await session.execute(
                insert(Channel)
                .values(
                    youtube_channel_id=f"review-channel-{uuid4()}",
                    name="Reviewer source",
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                )
                .returning(Channel.id)
            )
        ).scalar_one()
        video_id = (
            await session.execute(
                insert(Video)
                .values(
                    youtube_video_id=f"review-video-{uuid4()}",
                    channel_id=channel_id,
                    title="Review source",
                    published_at=NOW,
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                    processing_status="review",
                )
                .returning(Video.id)
            )
        ).scalar_one()
        signal_id = (
            await session.execute(
                insert(Signal)
                .values(
                    source_type="video",
                    source_id=video_id,
                    video_id=video_id,
                    signal_type="pain",
                    statement="A traceable pain",
                    evidence_text="Original provenance",
                    claim_status="creator_claim",
                    confidence="0.8",
                    observed_at=NOW,
                    status="review",
                )
                .returning(Signal.id)
            )
        ).scalar_one()
        task_id = (
            await session.execute(
                insert(ReviewTask)
                .values(
                    review_type="signal_validation",
                    target_type="signal",
                    target_id=signal_id,
                    status="pending",
                    priority=1,
                )
                .returning(ReviewTask.id)
            )
        ).scalar_one()
    return admins, video_id, signal_id, task_id


@pytest.mark.asyncio
async def test_claim_defer_and_signal_decision_are_safe(postgres_url) -> None:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    admins, video_id, signal_id, task_id = await seed(factory)
    service = ReviewWorkflowService(factory)

    claimed = await service.claim_task(task_id, admins[0])
    with pytest.raises(ReviewAssignmentConflict):
        await service.claim_task(task_id, admins[1])
    deferred = await service.decide(
        task_id,
        admins[0],
        ReviewDecisionRequest(decision="defer", decision_notes="Need another source"),
    )
    await service.claim_task(task_id, admins[1])
    resolved = await service.decide(
        task_id,
        admins[1],
        ReviewDecisionRequest(decision="approve", decision_notes="Evidence checked"),
    )
    with pytest.raises(ReviewTaskAlreadyResolved):
        await service.decide(
            task_id, admins[1], ReviewDecisionRequest(decision="approve")
        )
    async with factory() as session:
        signal = await session.get(Signal, signal_id)
        task = await session.get(ReviewTask, task_id)
    await engine.dispose()

    assert claimed.status == "in_review"
    assert deferred.status == "pending" and deferred.resolved_at is None
    assert resolved.status == "resolved" and resolved.resolved_by == admins[1]
    assert signal.status == "active" and signal.video_id == video_id
    assert signal.evidence_text == "Original provenance"
    assert task.decision_notes == "Evidence checked"


@pytest.mark.asyncio
async def test_match_and_merge_preserve_rows_and_collapse_links(postgres_url) -> None:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    admins, _, signal_id, _ = await seed(factory)
    async with factory() as session, session.begin():
        opportunity_ids = []
        for slug in (f"source-{uuid4()}", f"canonical-{uuid4()}"):
            opportunity_ids.append(
                (
                    await session.execute(
                        insert(Opportunity)
                        .values(
                            slug=slug,
                            name=slug,
                            market_stage="unknown",
                            status="candidate",
                            first_detected_at=NOW,
                            last_activity_at=NOW,
                        )
                        .returning(Opportunity.id)
                    )
                ).scalar_one()
            )
        match_task = (
            await session.execute(
                insert(ReviewTask)
                .values(
                    review_type="opportunity_match",
                    target_type="signal",
                    target_id=signal_id,
                    status="pending",
                    priority="0.8",
                    context={
                        "proposed_opportunity_id": str(opportunity_ids[0]),
                        "candidate_ids": [str(opportunity_ids[0])],
                    },
                )
                .returning(ReviewTask.id)
            )
        ).scalar_one()
        watchlist_id = (
            await session.execute(
                insert(Watchlist)
                .values(user_profile_id=admins[0], name=f"Review {uuid4()}")
                .returning(Watchlist.id)
            )
        ).scalar_one()
        await session.execute(
            insert(WatchlistItem).values(
                [
                    {
                        "watchlist_id": watchlist_id,
                        "opportunity_id": opportunity_ids[0],
                        "added_at": NOW - timedelta(days=1),
                    },
                    {
                        "watchlist_id": watchlist_id,
                        "opportunity_id": opportunity_ids[1],
                        "added_at": NOW,
                    },
                ]
            )
        )
    service = ReviewWorkflowService(factory)
    matched = await service.decide(
        match_task, admins[0], ReviewDecisionRequest(decision="approve")
    )
    async with factory() as session, session.begin():
        merge_task = (
            await session.execute(
                insert(ReviewTask)
                .values(
                    review_type="opportunity_merge",
                    target_type="opportunity",
                    target_id=opportunity_ids[0],
                    status="pending",
                    priority=1,
                )
                .returning(ReviewTask.id)
            )
        ).scalar_one()
    merged = await service.decide(
        merge_task,
        admins[0],
        ReviewDecisionRequest(
            decision="merge", merge_target_opportunity_id=opportunity_ids[1]
        ),
    )
    async with factory() as session:
        source = await session.get(Opportunity, opportunity_ids[0])
        canonical = await session.get(Opportunity, opportunity_ids[1])
        link_count = await session.scalar(
            select(func.count(OpportunitySignalLink.id)).where(
                OpportunitySignalLink.signal_id == signal_id
            )
        )
        history = await session.scalar(
            select(OpportunityMergeHistory).where(
                OpportunityMergeHistory.source_opportunity_id == opportunity_ids[0]
            )
        )
        watchlist_items = list(
            await session.scalars(
                select(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist_id)
            )
        )
    await engine.dispose()

    assert matched.side_effects["signal_status"] == "active"
    assert merged.side_effects["source_opportunity_status"] == "merged"
    assert source is not None and source.status == "merged"
    assert canonical is not None and link_count == 1
    assert history.canonical_opportunity_id == opportunity_ids[1]
    assert len(watchlist_items) == 1
    assert watchlist_items[0].opportunity_id == opportunity_ids[1]
    assert watchlist_items[0].added_at == NOW - timedelta(days=1)


@pytest.mark.asyncio
async def test_invalid_decision_rolls_back_task(postgres_url) -> None:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    admins, _, _, task_id = await seed(factory)
    with pytest.raises(InvalidReviewDecision):
        await ReviewWorkflowService(factory).decide(
            task_id,
            admins[0],
            ReviewDecisionRequest(
                decision="merge", merge_target_opportunity_id=uuid4()
            ),
        )
    async with factory() as session:
        task = await session.get(ReviewTask, task_id)
    await engine.dispose()
    assert task.status == "pending" and task.decision is None


@pytest.mark.asyncio
async def test_self_merge_and_lineage_cycle_are_rejected(postgres_url) -> None:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    admins, _, _, _ = await seed(factory)
    async with factory() as session, session.begin():
        opportunity_ids = []
        for index in range(3):
            opportunity_ids.append(
                (
                    await session.execute(
                        insert(Opportunity)
                        .values(
                            slug=f"cycle-{index}-{uuid4()}",
                            name=f"Cycle {index}",
                            market_stage="unknown",
                            status="candidate",
                            first_detected_at=NOW,
                            last_activity_at=NOW,
                        )
                        .returning(Opportunity.id)
                    )
                ).scalar_one()
            )
        session.add_all(
            [
                OpportunityMergeHistory(
                    source_opportunity_id=opportunity_ids[0],
                    canonical_opportunity_id=opportunity_ids[1],
                    merged_at=NOW - timedelta(hours=2),
                    merged_by=admins[0],
                    created_at=NOW - timedelta(hours=2),
                ),
                OpportunityMergeHistory(
                    source_opportunity_id=opportunity_ids[1],
                    canonical_opportunity_id=opportunity_ids[2],
                    merged_at=NOW - timedelta(hours=1),
                    merged_by=admins[0],
                    created_at=NOW - timedelta(hours=1),
                ),
            ]
        )
        task_ids = []
        for target in (opportunity_ids[0], opportunity_ids[2]):
            task_ids.append(
                (
                    await session.execute(
                        insert(ReviewTask)
                        .values(
                            review_type="opportunity_merge",
                            target_type="opportunity",
                            target_id=target,
                            status="pending",
                            priority=1,
                        )
                        .returning(ReviewTask.id)
                    )
                ).scalar_one()
            )
    service = ReviewWorkflowService(factory)
    with pytest.raises(InvalidMergeTarget):
        await service.decide(
            task_ids[0],
            admins[0],
            ReviewDecisionRequest(
                decision="merge", merge_target_opportunity_id=opportunity_ids[0]
            ),
        )
    with pytest.raises(OpportunityMergeCycleError):
        await service.decide(
            task_ids[1],
            admins[0],
            ReviewDecisionRequest(
                decision="merge", merge_target_opportunity_id=opportunity_ids[0]
            ),
        )
    async with factory() as session:
        tasks = [await session.get(ReviewTask, task_id) for task_id in task_ids]
    await engine.dispose()
    assert all(task.status == "pending" for task in tasks)
