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
    Comment,
    Video,
)
from ai_business_radar_api.infrastructure.external.youtube import YouTubeAPIError
from ai_business_radar_api.infrastructure.external.youtube.models import (
    YouTubeComment,
    YouTubeCommentPage,
)
from ai_business_radar_api.services.youtube_comments import (
    CanonicalVideosNotFound,
    CommentCollectionRequest,
    YouTubeCommentCollectionService,
)

NOW = datetime(2026, 9, 4, 9, tzinfo=UTC)


class YouTubeStub:
    def __init__(self, responses: dict[str, list[YouTubeCommentPage | Exception]]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    async def get_comment_threads(self, video_id: str, **kwargs) -> YouTubeCommentPage:
        self.calls.append({"video_id": video_id, **kwargs})
        response = self.responses[video_id].pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest_asyncio.fixture
async def comment_database(
    postgres_url: str,
) -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker]]:
    engine = create_database_engine(postgres_url)
    yield engine, create_session_factory(engine)
    await engine.dispose()


def comment(comment_id: str, *, text: str = "Useful comment", likes: int = 1) -> YouTubeComment:
    return YouTubeComment(
        youtube_comment_id=comment_id,
        video_id="external-video",
        text=text,
        published_at=NOW - timedelta(days=1),
        updated_at=NOW,
        like_count=likes,
        reply_count=2,
    )


def page(*items: YouTubeComment, next_token: str | None = None) -> YouTubeCommentPage:
    return YouTubeCommentPage(items=list(items), next_page_token=next_token)


async def seed_videos(factory: async_sessionmaker, *external_ids: str) -> list[UUID]:
    channel_external_id = f"comments-channel-{uuid4()}"
    async with factory() as session, session.begin():
        channel_id = (
            await session.execute(
                insert(Channel)
                .values(
                    youtube_channel_id=channel_external_id,
                    name="Comment channel",
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                )
                .returning(Channel.id)
            )
        ).scalar_one()
        return list(
            await session.scalars(
                insert(Video)
                .values(
                    [
                        {
                            "youtube_video_id": external_id,
                            "channel_id": channel_id,
                            "title": external_id,
                            "published_at": NOW,
                            "first_seen_at": NOW,
                            "last_seen_at": NOW,
                            "processing_status": "new",
                        }
                        for external_id in external_ids
                    ]
                )
                .returning(Video.id)
            )
        )


@pytest.mark.asyncio
async def test_collects_top_level_comments_with_bounded_pagination(comment_database) -> None:
    _, factory = comment_database
    video_id = (await seed_videos(factory, "comments-v1"))[0]
    youtube = YouTubeStub(
        {
            "comments-v1": [
                page(comment("c1"), comment("c2"), next_token="next"),
                page(comment("c2"), comment("c3"), next_token="ignored"),
            ]
        }
    )
    result = await YouTubeCommentCollectionService(factory, youtube, clock=lambda: NOW).collect(
        CommentCollectionRequest(video_ids=[video_id], max_pages_per_video=2)
    )
    assert result.status == "completed"
    assert result.pages_requested == result.pages_completed == 2
    assert result.comments_discovered == result.comments_processed == 3
    assert result.estimated_quota_units == 2 and len(youtube.calls) == 2
    async with factory() as session:
        comments = list(await session.scalars(select(Comment).where(Comment.video_id == video_id)))
        run = await session.get(CollectionRun, result.collection_run_id)
    assert {item.youtube_comment_id for item in comments} == {"c1", "c2", "c3"}
    assert all(item.author_hash is None for item in comments)
    assert run.run_type == "comment_collection" and run.items_processed == 3


@pytest.mark.asyncio
async def test_recollection_is_idempotent_and_refreshes_source_fields(comment_database) -> None:
    _, factory = comment_database
    video_id = (await seed_videos(factory, "comments-refresh"))[0]
    await YouTubeCommentCollectionService(
        factory,
        YouTubeStub({"comments-refresh": [page(comment("refresh-c1"))]}),
        clock=lambda: NOW,
    ).collect(CommentCollectionRequest(video_ids=[video_id]))
    async with factory() as session, session.begin():
        await session.execute(
            update(Comment)
            .where(Comment.youtube_comment_id == "refresh-c1")
            .values(is_question=True)
        )
    later = NOW + timedelta(hours=1)
    await YouTubeCommentCollectionService(
        factory,
        YouTubeStub({"comments-refresh": [page(comment("refresh-c1", text="Edited", likes=9))]}),
        clock=lambda: later,
    ).collect(CommentCollectionRequest(video_ids=[video_id]))
    async with factory() as session:
        stored = await session.scalar(
            select(Comment).where(Comment.youtube_comment_id == "refresh-c1")
        )
        count = await session.scalar(
            select(func.count())
            .select_from(Comment)
            .where(Comment.youtube_comment_id == "refresh-c1")
        )
    assert count == 1 and stored.first_seen_at == NOW
    assert stored.text == "Edited" and stored.like_count == 9 and stored.reply_count == 2
    assert stored.is_question is True and stored.source_updated_at == NOW
    assert stored.updated_at == later


@pytest.mark.asyncio
async def test_comment_limit_and_page_limit_stop_without_exhausting(comment_database) -> None:
    _, factory = comment_database
    video_id = (await seed_videos(factory, "comments-limits"))[0]
    youtube = YouTubeStub(
        {
            "comments-limits": [
                page(comment("limit-c1"), comment("limit-c2"), next_token="more"),
                page(comment("limit-c3"), next_token="still-more"),
            ]
        }
    )
    result = await YouTubeCommentCollectionService(factory, youtube, clock=lambda: NOW).collect(
        CommentCollectionRequest(
            video_ids=[video_id], max_pages_per_video=5, max_comments_per_video=2
        )
    )
    assert result.comments_processed == 2 and result.pages_completed == 1
    assert len(youtube.calls) == 1 and youtube.calls[0]["max_results"] == 2


@pytest.mark.asyncio
async def test_quota_stop_after_progress_is_partial(comment_database) -> None:
    _, factory = comment_database
    video_ids = await seed_videos(factory, "comments-quota-1", "comments-quota-2")
    youtube = YouTubeStub(
        {
            "comments-quota-1": [page(comment("quota-c1"))],
            "comments-quota-2": [page(comment("quota-c2"))],
        }
    )
    result = await YouTubeCommentCollectionService(
        factory, youtube, max_quota_units_per_run=1, clock=lambda: NOW
    ).collect(CommentCollectionRequest(video_ids=video_ids))
    assert result.status == "partial" and result.reason == "quota_budget_reached"
    assert result.pages_completed == 1 and len(youtube.calls) == 1


@pytest.mark.asyncio
async def test_disabled_zero_and_failed_videos_have_safe_independent_outcomes(
    comment_database,
) -> None:
    _, factory = comment_database
    video_ids = await seed_videos(factory, "comments-disabled", "comments-zero", "comments-failed")
    youtube = YouTubeStub(
        {
            "comments-disabled": [YouTubeAPIError("secret", reason="commentsDisabled")],
            "comments-zero": [page()],
            "comments-failed": [YouTubeAPIError("secret", reason="videoNotFound")],
        }
    )
    result = await YouTubeCommentCollectionService(factory, youtube, clock=lambda: NOW).collect(
        CommentCollectionRequest(video_ids=video_ids)
    )
    assert result.status == "partial"
    assert (result.videos_completed, result.videos_skipped, result.videos_failed) == (1, 1, 1)
    async with factory() as session:
        statuses = list(
            await session.scalars(select(Video.processing_status).where(Video.id.in_(video_ids)))
        )
        run = await session.get(CollectionRun, result.collection_run_id)
    assert statuses == ["new", "new", "new"]
    assert "secret" not in str(run.metadata_) and run.items_failed == 1


@pytest.mark.asyncio
async def test_all_external_failures_fail_and_explicit_missing_video_is_rejected(
    comment_database,
) -> None:
    _, factory = comment_database
    video_id = (await seed_videos(factory, "comments-all-failed"))[0]
    result = await YouTubeCommentCollectionService(
        factory,
        YouTubeStub({"comments-all-failed": [YouTubeAPIError("api-key", reason="backendError")]}),
        clock=lambda: NOW,
    ).collect(CommentCollectionRequest(video_ids=[video_id]))
    assert result.status == "failed" and result.reason == "all_videos_failed"
    with pytest.raises(CanonicalVideosNotFound):
        await YouTubeCommentCollectionService(factory, YouTubeStub({})).collect(
            CommentCollectionRequest(video_ids=[uuid4()])
        )
