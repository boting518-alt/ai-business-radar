from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    CollectionRun,
    SearchQuery,
    YouTubeDiscoveryItem,
)
from ai_business_radar_api.infrastructure.database.repositories import (
    YouTubeDiscoveryItemRepository,
)
from ai_business_radar_api.infrastructure.external.youtube import YouTubeAPIError
from ai_business_radar_api.infrastructure.external.youtube.models import (
    YouTubeSearchItem,
    YouTubeSearchPage,
)
from ai_business_radar_api.services.youtube_discovery import (
    DiscoveryRequest,
    InvalidDiscoveryMode,
    SearchQueryDisabled,
    YouTubeDiscoveryService,
)


class YouTubeStub:
    def __init__(self, responses: list[YouTubeSearchPage | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def search_videos(self, query: str, **kwargs: Any) -> YouTubeSearchPage:
        self.calls.append({"query": query, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest_asyncio.fixture
async def discovery_database(
    postgres_url: str,
) -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker]]:
    engine = create_database_engine(postgres_url)
    yield engine, create_session_factory(engine)
    await engine.dispose()


def page(*video_ids: str, next_token: str | None = None) -> YouTubeSearchPage:
    return YouTubeSearchPage(
        items=[
            YouTubeSearchItem(
                youtube_video_id=video_id,
                youtube_channel_id=f"channel-{video_id}",
                title=f"Title {video_id}",
                description="Description",
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
                channel_title="Channel",
            )
            for video_id in video_ids
        ],
        next_page_token=next_token,
    )


async def create_query(
    factory: async_sessionmaker,
    *,
    enabled: bool = True,
    mode: str = "discovery",
) -> UUID:
    async with factory() as session, session.begin():
        return (
            await session.execute(
                insert(SearchQuery)
                .values(
                    query=f"AI business {uuid4()}",
                    query_group="discovery",
                    language="en",
                    region="US",
                    enabled=enabled,
                    priority=1,
                    discovery_mode=mode,
                )
                .returning(SearchQuery.id)
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_enabled_query_completes_and_persists_run_and_staging(
    discovery_database: tuple[AsyncEngine, async_sessionmaker],
) -> None:
    _, factory = discovery_database
    query_id = await create_query(factory)
    youtube = YouTubeStub([page("v1", "v2")])
    result = await YouTubeDiscoveryService(factory, youtube).discover(
        DiscoveryRequest(search_query_id=query_id)
    )
    assert result.status == "completed"
    assert result.items_discovered == result.unique_video_count == 2
    assert result.pages_requested == result.pages_completed == 1
    assert result.estimated_quota_units == 100
    async with factory() as session:
        run = await session.get(CollectionRun, result.collection_run_id)
        items = list(
            await session.scalars(
                select(YouTubeDiscoveryItem).where(
                    YouTubeDiscoveryItem.collection_run_id == result.collection_run_id
                )
            )
        )
        query = await session.get(SearchQuery, query_id)
    assert run.status == "completed" and run.finished_at is not None
    assert run.items_discovered == 2 and run.metadata_["estimated_quota_units"] == 100
    assert query.last_run_at == result.started_at
    assert {item.youtube_video_id for item in items} == {"v1", "v2"}
    assert youtube.calls[0]["region_code"] == "US"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("enabled", "mode", "exception"),
    [(False, "discovery", SearchQueryDisabled), (True, "monitoring", InvalidDiscoveryMode)],
)
async def test_invalid_managed_query_is_rejected_without_external_call(
    discovery_database: tuple[AsyncEngine, async_sessionmaker],
    enabled: bool,
    mode: str,
    exception: type[Exception],
) -> None:
    _, factory = discovery_database
    query_id = await create_query(factory, enabled=enabled, mode=mode)
    youtube = YouTubeStub([])
    with pytest.raises(exception):
        await YouTubeDiscoveryService(factory, youtube).discover(
            DiscoveryRequest(search_query_id=query_id)
        )
    assert youtube.calls == []


@pytest.mark.asyncio
async def test_zero_results_is_a_completed_run(
    discovery_database: tuple[AsyncEngine, async_sessionmaker],
) -> None:
    _, factory = discovery_database
    query_id = await create_query(factory)
    result = await YouTubeDiscoveryService(factory, YouTubeStub([page()])).discover(
        DiscoveryRequest(search_query_id=query_id)
    )
    assert result.status == "completed" and result.items_discovered == 0


@pytest.mark.asyncio
async def test_multiple_pages_deduplicate_and_stop_at_max_pages(
    discovery_database: tuple[AsyncEngine, async_sessionmaker],
) -> None:
    _, factory = discovery_database
    query_id = await create_query(factory)
    youtube = YouTubeStub(
        [page("v1", "v1", "v2", next_token="two"), page("v2", "v3", next_token="three")]
    )
    result = await YouTubeDiscoveryService(factory, youtube).discover(
        DiscoveryRequest(search_query_id=query_id, max_pages=2, max_results=None)
    )
    assert result.pages_completed == 2 and result.unique_video_count == 3
    assert result.next_page_token == "three"
    assert result.estimated_quota_units == 200
    assert len(youtube.calls) == 2


@pytest.mark.asyncio
async def test_max_results_limits_persisted_items_without_another_page(
    discovery_database: tuple[AsyncEngine, async_sessionmaker],
) -> None:
    _, factory = discovery_database
    query_id = await create_query(factory)
    youtube = YouTubeStub([page("v1", "v2", "v3", next_token="more")])
    result = await YouTubeDiscoveryService(factory, youtube).discover(
        DiscoveryRequest(search_query_id=query_id, max_pages=5, max_results=2)
    )
    assert result.unique_video_count == 2 and result.next_page_token == "more"
    assert len(youtube.calls) == 1 and youtube.calls[0]["max_results"] == 2


@pytest.mark.asyncio
async def test_quota_budget_stops_after_progress_as_partial(
    discovery_database: tuple[AsyncEngine, async_sessionmaker],
) -> None:
    _, factory = discovery_database
    query_id = await create_query(factory)
    youtube = YouTubeStub([page("v1", next_token="more")])
    result = await YouTubeDiscoveryService(factory, youtube, max_quota_units_per_run=100).discover(
        DiscoveryRequest(search_query_id=query_id, max_pages=3)
    )
    assert result.status == "partial" and result.reason == "quota_budget_reached"
    assert result.pages_completed == 1 and result.estimated_quota_units == 100
    assert result.next_page_token == "more" and len(youtube.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("successful_pages", [0, 1])
async def test_youtube_failure_finalizes_failed_or_partial(
    discovery_database: tuple[AsyncEngine, async_sessionmaker], successful_pages: int
) -> None:
    _, factory = discovery_database
    query_id = await create_query(factory)
    responses: list[YouTubeSearchPage | Exception] = []
    if successful_pages:
        responses.append(page("v1", next_token="next"))
    responses.append(YouTubeAPIError("safe failure", reason="backendError"))
    result = await YouTubeDiscoveryService(factory, YouTubeStub(responses)).discover(
        DiscoveryRequest(search_query_id=query_id, max_pages=2)
    )
    assert result.status == ("partial" if successful_pages else "failed")
    async with factory() as session:
        run = await session.get(CollectionRun, result.collection_run_id)
    assert run.status == result.status
    assert "safe failure" not in (run.error_summary or "")


@pytest.mark.asyncio
async def test_staging_repository_uniqueness_is_idempotent(
    discovery_database: tuple[AsyncEngine, async_sessionmaker],
) -> None:
    _, factory = discovery_database
    query_id = await create_query(factory)
    result = await YouTubeDiscoveryService(factory, YouTubeStub([page("v1")])).discover(
        DiscoveryRequest(search_query_id=query_id)
    )
    values = [
        {
            "collection_run_id": result.collection_run_id,
            "search_query_id": query_id,
            "youtube_video_id": "v1",
            "youtube_channel_id": "channel-v1",
            "discovered_at": datetime.now(UTC),
            "processing_status": "pending",
        }
    ]
    async with factory() as session, session.begin():
        inserted = await YouTubeDiscoveryItemRepository(session).add_discovered_items(values)
    assert inserted == 0
