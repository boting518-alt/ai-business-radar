from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    Channel,
    CollectionRun,
    SearchQuery,
    Video,
    VideoSnapshot,
    YouTubeDiscoveryItem,
)
from ai_business_radar_api.infrastructure.database.repositories import (
    YouTubeDiscoveryItemRepository,
)
from ai_business_radar_api.infrastructure.external.youtube import YouTubeAPIError
from ai_business_radar_api.infrastructure.external.youtube.models import (
    YouTubeChannel,
    YouTubeVideo,
)
from ai_business_radar_api.services.youtube_metadata import (
    MetadataCollectionRequest,
    YouTubeMetadataCollectionService,
)

NOW = datetime(2026, 9, 4, 8, tzinfo=UTC)


class YouTubeStub:
    def __init__(
        self, videos: list[YouTubeVideo] | Exception, channels: list[YouTubeChannel] | Exception
    ):
        self.videos = videos
        self.channels = channels
        self.video_calls: list[list[str]] = []
        self.channel_calls: list[list[str]] = []

    async def get_videos(self, ids: list[str]) -> list[YouTubeVideo]:
        self.video_calls.append(list(ids))
        if isinstance(self.videos, Exception):
            raise self.videos
        return self.videos

    async def get_channels(self, ids: list[str]) -> list[YouTubeChannel]:
        self.channel_calls.append(list(ids))
        if isinstance(self.channels, Exception):
            raise self.channels
        return self.channels


@pytest_asyncio.fixture
async def metadata_database(
    postgres_url: str,
) -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker]]:
    engine = create_database_engine(postgres_url)
    yield engine, create_session_factory(engine)
    await engine.dispose()


def video(
    video_id: str, channel_id: str = "channel-1", *, title: str = "Canonical"
) -> YouTubeVideo:
    return YouTubeVideo(
        youtube_video_id=video_id,
        youtube_channel_id=channel_id,
        title=title,
        description="Canonical description",
        published_at=NOW - timedelta(days=1),
        category_id="28",
        language="en",
        duration_seconds=123,
        thumbnail_url="https://example.test/canonical.jpg",
        view_count=100,
        like_count=10,
        comment_count=2,
        has_captions=True,
    )


def channel(channel_id: str = "channel-1", *, name: str = "Canonical channel") -> YouTubeChannel:
    return YouTubeChannel(
        youtube_channel_id=channel_id,
        name=name,
        description="Channel description",
        country="US",
        subscriber_count=1000,
        video_count=20,
        view_count=5000,
    )


async def seed_staging(factory: async_sessionmaker, *video_ids: str) -> tuple[UUID, list[UUID]]:
    async with factory() as session, session.begin():
        query_id = (
            await session.execute(
                insert(SearchQuery)
                .values(
                    query=f"metadata-{uuid4()}",
                    query_group="discovery",
                    enabled=True,
                    priority=1,
                    discovery_mode="discovery",
                )
                .returning(SearchQuery.id)
            )
        ).scalar_one()
        discovery_run_id = (
            await session.execute(
                insert(CollectionRun)
                .values(
                    source_type="youtube",
                    run_type="discovery",
                    status="completed",
                    started_at=NOW,
                    finished_at=NOW,
                    search_query_id=query_id,
                    items_discovered=len(video_ids),
                )
                .returning(CollectionRun.id)
            )
        ).scalar_one()
        ids = list(
            await session.scalars(
                insert(YouTubeDiscoveryItem)
                .values(
                    [
                        {
                            "collection_run_id": discovery_run_id,
                            "search_query_id": query_id,
                            "youtube_video_id": item,
                            "youtube_channel_id": "search-channel",
                            "title": "Search snippet",
                            "description": "Not authoritative",
                            "discovered_at": NOW,
                            "processing_status": "pending",
                        }
                        for item in video_ids
                    ]
                )
                .returning(YouTubeDiscoveryItem.id)
            )
        )
    return discovery_run_id, ids


@pytest.mark.asyncio
async def test_success_canonicalizes_items_and_creates_snapshots(metadata_database) -> None:
    _, factory = metadata_database
    discovery_run_id, item_ids = await seed_staging(factory, "v1", "v2")
    youtube = YouTubeStub([video("v1"), video("v2")], [channel()])
    result = await YouTubeMetadataCollectionService(factory, youtube, clock=lambda: NOW).collect(
        MetadataCollectionRequest(collection_run_id=discovery_run_id)
    )
    assert result.status == "completed"
    assert (result.items_claimed, result.items_processed, result.items_failed) == (2, 2, 0)
    assert result.snapshots_created == 2 and result.estimated_quota_units == 2
    assert len(youtube.video_calls) == 1 and set(youtube.video_calls[0]) == {"v1", "v2"}
    assert youtube.channel_calls == [["channel-1"]]
    async with factory() as session:
        videos = list(
            await session.scalars(
                select(Video)
                .where(Video.youtube_video_id.in_(["v1", "v2"]))
                .order_by(Video.youtube_video_id)
            )
        )
        items = list(
            await session.scalars(
                select(YouTubeDiscoveryItem).where(YouTubeDiscoveryItem.id.in_(item_ids))
            )
        )
        snapshots = await session.scalar(
            select(func.count())
            .select_from(VideoSnapshot)
            .join(Video)
            .where(Video.youtube_video_id.in_(["v1", "v2"]))
        )
        run = await session.get(CollectionRun, result.collection_run_id)
    assert [item.title for item in videos] == ["Canonical", "Canonical"]
    assert all(item.processing_status == "new" for item in videos)
    assert all(item.processing_status == "processed" and item.canonical_video_id for item in items)
    assert snapshots == 2 and run.run_type == "metadata_collection"


@pytest.mark.asyncio
async def test_upserts_preserve_first_seen_classification_and_append_snapshot(
    metadata_database,
) -> None:
    _, factory = metadata_database
    first_run, _ = await seed_staging(factory, "v1")
    service = YouTubeMetadataCollectionService(
        factory, YouTubeStub([video("v1")], [channel()]), clock=lambda: NOW
    )
    await service.collect(MetadataCollectionRequest(collection_run_id=first_run))
    async with factory() as session, session.begin():
        await session.execute(
            update(Channel)
            .where(Channel.youtube_channel_id == "channel-1")
            .values(channel_type="vendor")
        )
        await session.execute(
            update(Video).where(Video.youtube_video_id == "v1").values(processing_status="queued")
        )
    second_run, _ = await seed_staging(factory, "v1")
    later = NOW + timedelta(hours=1)
    refreshed = YouTubeStub([video("v1", title="Refreshed")], [channel(name="Refreshed channel")])
    await YouTubeMetadataCollectionService(factory, refreshed, clock=lambda: later).collect(
        MetadataCollectionRequest(collection_run_id=second_run)
    )
    async with factory() as session:
        canonical_channel = await session.scalar(
            select(Channel).where(Channel.youtube_channel_id == "channel-1")
        )
        canonical_video = await session.scalar(select(Video).where(Video.youtube_video_id == "v1"))
        channel_count = await session.scalar(
            select(func.count())
            .select_from(Channel)
            .where(Channel.youtube_channel_id == "channel-1")
        )
        video_count = await session.scalar(
            select(func.count()).select_from(Video).where(Video.youtube_video_id == "v1")
        )
        snapshots = list(
            await session.scalars(
                select(VideoSnapshot)
                .join(Video)
                .where(Video.youtube_video_id == "v1")
                .order_by(VideoSnapshot.captured_at)
            )
        )
    assert channel_count == video_count == 1
    assert canonical_channel.first_seen_at == NOW and canonical_channel.channel_type == "vendor"
    assert canonical_channel.name == "Refreshed channel"
    assert canonical_video.first_seen_at == NOW and canonical_video.processing_status == "queued"
    assert canonical_video.title == "Refreshed" and len(snapshots) == 2


@pytest.mark.asyncio
async def test_missing_video_and_channel_yield_safe_partial_result(metadata_database) -> None:
    _, factory = metadata_database
    discovery_run_id, item_ids = await seed_staging(factory, "good", "missing", "no-channel")
    youtube = YouTubeStub([video("good"), video("no-channel", "unavailable-channel")], [channel()])
    result = await YouTubeMetadataCollectionService(factory, youtube, clock=lambda: NOW).collect(
        MetadataCollectionRequest(collection_run_id=discovery_run_id)
    )
    assert result.status == "partial" and result.items_processed == 1 and result.items_failed == 2
    async with factory() as session:
        items = {
            item.youtube_video_id: item
            for item in await session.scalars(
                select(YouTubeDiscoveryItem).where(YouTubeDiscoveryItem.id.in_(item_ids))
            )
        }
        video_count = await session.scalar(
            select(func.count())
            .select_from(Video)
            .where(Video.youtube_video_id.in_(["good", "missing", "no-channel"]))
        )
    assert items["missing"].error_summary == "video_unavailable"
    assert items["no-channel"].error_summary == "channel_unavailable"
    assert video_count == 1


@pytest.mark.asyncio
async def test_external_failure_fails_run_and_releases_claim(metadata_database) -> None:
    _, factory = metadata_database
    discovery_run_id, item_ids = await seed_staging(factory, "v1")
    result = await YouTubeMetadataCollectionService(
        factory, YouTubeStub(YouTubeAPIError("provider secret"), []), clock=lambda: NOW
    ).collect(MetadataCollectionRequest(collection_run_id=discovery_run_id))
    assert result.status == "failed" and result.reason == "youtube_videos_request_failed"
    async with factory() as session:
        item = await session.get(YouTubeDiscoveryItem, item_ids[0])
        run = await session.get(CollectionRun, result.collection_run_id)
    assert item.processing_status == "pending"
    assert run.status == "failed" and run.error_summary == "youtube_request_failed"


@pytest.mark.asyncio
async def test_claim_pending_uses_skip_locked(metadata_database) -> None:
    _, factory = metadata_database
    discovery_run_id, _ = await seed_staging(factory, "claim-v1")
    async with factory() as first, first.begin():
        claimed = await YouTubeDiscoveryItemRepository(first).claim_pending(
            limit=1, collection_run_id=discovery_run_id
        )
        async with factory() as second, second.begin():
            competing = await YouTubeDiscoveryItemRepository(second).claim_pending(
                limit=1, collection_run_id=discovery_run_id
            )
        assert len(claimed) == 1 and competing == []


@pytest.mark.asyncio
async def test_limit_is_bounded_and_empty_selection_completes(metadata_database) -> None:
    _, factory = metadata_database
    with pytest.raises(ValueError):
        MetadataCollectionRequest(limit=251)
    result = await YouTubeMetadataCollectionService(
        factory, YouTubeStub([], []), clock=lambda: NOW
    ).collect(MetadataCollectionRequest(collection_run_id=uuid4()))
    assert result.status == "completed" and result.items_claimed == 0
