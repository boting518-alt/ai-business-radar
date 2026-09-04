from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import insert, select

from ai_business_radar_api.infrastructure.database.models import (
    Channel,
    CollectionRun,
    SearchQuery,
    Video,
    YouTubeDiscoveryItem,
)
from ai_business_radar_api.infrastructure.database.repositories import (
    SearchQueryRepository,
    YouTubeDiscoveryItemRepository,
)

NOW = datetime(2026, 9, 4, 10, tzinfo=UTC)


@pytest.mark.asyncio
async def test_stale_claim_recovery_only_resets_expired_processing_rows(db_session) -> None:
    query_id = (
        await db_session.execute(
            insert(SearchQuery)
            .values(
                query=f"worker-{uuid4()}",
                query_group="discovery",
                enabled=True,
                priority=1,
                discovery_mode="discovery",
            )
            .returning(SearchQuery.id)
        )
    ).scalar_one()
    run_id = (
        await db_session.execute(
            insert(CollectionRun)
            .values(
                source_type="youtube",
                run_type="discovery",
                status="completed",
                started_at=NOW,
                finished_at=NOW,
                search_query_id=query_id,
            )
            .returning(CollectionRun.id)
        )
    ).scalar_one()
    channel_id = (
        await db_session.execute(
            insert(Channel)
            .values(
                youtube_channel_id=f"worker-channel-{uuid4()}",
                name="Worker",
                first_seen_at=NOW,
                last_seen_at=NOW,
            )
            .returning(Channel.id)
        )
    ).scalar_one()
    video_id = (
        await db_session.execute(
            insert(Video)
            .values(
                youtube_video_id=f"worker-video-{uuid4()}",
                channel_id=channel_id,
                title="Worker",
                published_at=NOW,
                first_seen_at=NOW,
                last_seen_at=NOW,
                processing_status="new",
            )
            .returning(Video.id)
        )
    ).scalar_one()
    rows = [
        {
            "youtube_video_id": "stale",
            "processing_status": "processing",
            "claimed_at": NOW - timedelta(hours=1),
        },
        {"youtube_video_id": "fresh", "processing_status": "processing", "claimed_at": NOW},
        {"youtube_video_id": "pending", "processing_status": "pending"},
        {
            "youtube_video_id": "processed",
            "processing_status": "processed",
            "processed_at": NOW,
            "canonical_video_id": video_id,
        },
        {
            "youtube_video_id": "failed",
            "processing_status": "failed",
            "processed_at": NOW,
            "error_summary": "terminal",
        },
    ]
    for row in rows:
        row.update(
            collection_run_id=run_id,
            search_query_id=query_id,
            youtube_channel_id="external-channel",
            discovered_at=NOW,
        )
        for field in ("claimed_at", "processed_at", "canonical_video_id", "error_summary"):
            row.setdefault(field, None)
    await db_session.execute(insert(YouTubeDiscoveryItem).values(rows))
    recovered = await YouTubeDiscoveryItemRepository(db_session).recover_stale_claims(
        stale_before=NOW - timedelta(minutes=30), limit=10
    )
    statuses = dict(
        (
            await db_session.execute(
                select(
                    YouTubeDiscoveryItem.youtube_video_id, YouTubeDiscoveryItem.processing_status
                ).where(YouTubeDiscoveryItem.collection_run_id == run_id)
            )
        ).all()
    )
    assert recovered == 1
    assert statuses == {
        "stale": "pending",
        "fresh": "processing",
        "pending": "pending",
        "processed": "processed",
        "failed": "failed",
    }


@pytest.mark.asyncio
async def test_scheduled_query_selection_filters_mode_enabled_and_limit(db_session) -> None:
    marker = str(uuid4())
    for enabled, mode, priority in [
        (True, "discovery", 3),
        (True, "discovery", 2),
        (False, "discovery", 10),
        (True, "monitoring", 10),
    ]:
        await db_session.execute(
            insert(SearchQuery).values(
                query=f"schedule-{marker}-{priority}-{enabled}-{mode}",
                query_group="discovery",
                enabled=enabled,
                priority=priority,
                discovery_mode=mode,
            )
        )
    rows = await SearchQueryRepository(db_session).list_enabled_discovery(limit=2)
    selected = [row for row in rows if marker in row.query]
    assert all(row.enabled and row.discovery_mode == "discovery" for row in rows)
    assert len(rows) == 2
    assert len(selected) == 2
