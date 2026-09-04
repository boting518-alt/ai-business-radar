from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from ai_business_radar_schemas import RelevanceFilterOutput
from sqlalchemy import insert, select

from ai_business_radar_api.infrastructure.ai import (
    AIProviderError,
    AIResponse,
    AIStructuredOutputError,
)
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import AIExtraction, Channel, Video
from ai_business_radar_api.services.relevance_filter import (
    RelevanceBatchRequest,
    VideoRelevanceService,
)

NOW = datetime(2026, 9, 4, tzinfo=UTC)


class AIStub:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    async def structured_generate(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return AIResponse(
            provider="openai",
            model="test-model",
            parsed=outcome,
            raw_output={"response_id": "safe", "output_text": "{}"},
            provider_request_id="safe",
            input_tokens=8,
            output_tokens=4,
            total_tokens=12,
        )


@pytest_asyncio.fixture
async def relevance_database(postgres_url: str) -> AsyncIterator[tuple[object, object]]:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    yield engine, factory
    await engine.dispose()


async def seed_video(factory, *, status="new", title="AI workflow"):
    async with factory() as session, session.begin():
        channel_id = (
            await session.execute(
                insert(Channel)
                .values(
                    youtube_channel_id=f"channel-{uuid4()}",
                    name="Builder",
                    channel_type="vendor",
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                    created_at=NOW,
                    updated_at=NOW,
                )
                .returning(Channel.id)
            )
        ).scalar_one()
        return (
            await session.execute(
                insert(Video)
                .values(
                    youtube_video_id=f"video-{uuid4()}",
                    channel_id=channel_id,
                    title=title,
                    description="Customer automation case study",
                    published_at=NOW,
                    duration_seconds=120,
                    language="en",
                    current_view_count=100,
                    current_like_count=10,
                    current_comment_count=2,
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                    processing_status=status,
                    created_at=NOW,
                    updated_at=NOW,
                )
                .returning(Video.id)
            )
        ).scalar_one()


def output(relevant: bool):
    return RelevanceFilterOutput(
        relevant=relevant,
        relevance_score=0.85 if relevant else 0.1,
        content_type="case_study" if relevant else None,
        primary_topic="automation" if relevant else None,
        reason="Business evidence" if relevant else "No business evidence",
    )


@pytest.mark.asyncio
async def test_success_is_audited_reused_and_force_retains_history(relevance_database) -> None:
    _, factory = relevance_database
    video_id = await seed_video(factory)
    ai = AIStub(output(True), output(True))
    service = VideoRelevanceService(factory, ai, provider="openai", model="test-model")

    first = await service.analyze(video_id)
    reused = await service.analyze(video_id)
    forced = await service.analyze(video_id, force=True)

    assert first.status == "completed" and first.relevant is True
    assert reused.reused is True and len(ai.calls) == 2
    assert forced.extraction_id != first.extraction_id
    assert "transcript" not in ai.calls[0]["input_data"]
    async with factory() as session:
        video = await session.get(Video, video_id)
        rows = list(
            await session.scalars(
                select(AIExtraction)
                .where(AIExtraction.video_id == video_id)
                .order_by(AIExtraction.attempt_number)
            )
        )
    assert video.processing_status == "queued"
    assert len(rows) == 2 and rows[1].supersedes_extraction_id == rows[0].id
    assert rows[0].status == "completed" and rows[0].prompt_version == "v001"
    assert rows[0].provider == "openai" and rows[0].model == "test-model"
    assert rows[0].parsed_output["relevant"] is True
    assert str(rows[0].confidence) == "0.85"
    assert rows[0].total_tokens == 12 and rows[0].provider_request_id == "safe"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "extraction_status", "video_status"),
    [
        (output(False), "completed", "ignored"),
        (AIProviderError("safe"), "failed", "failed"),
        (
            AIStructuredOutputError("invalid", raw_output={"response_id": "safe"}),
            "invalid_output",
            "review",
        ),
    ],
)
async def test_terminal_outcomes_are_audited(
    relevance_database, outcome, extraction_status, video_status
) -> None:
    _, factory = relevance_database
    video_id = await seed_video(factory)
    result = await VideoRelevanceService(
        factory, AIStub(outcome), provider="openai", model="test-model"
    ).analyze(video_id)
    async with factory() as session:
        video = await session.get(Video, video_id)
        extraction = await session.get(AIExtraction, result.extraction_id)
    assert video.processing_status == video_status
    assert extraction.status == extraction_status
    assert extraction.started_at is not None and extraction.completed_at is not None


@pytest.mark.asyncio
async def test_batch_continues_after_provider_failure(relevance_database) -> None:
    _, factory = relevance_database
    await seed_video(factory, title="First")
    await seed_video(factory, title="Second")
    ai = AIStub(AIProviderError("safe"), output(True))
    result = await VideoRelevanceService(
        factory, ai, provider="openai", model="test-model"
    ).analyze_batch(RelevanceBatchRequest(limit=2))
    assert result.requested == 2
    assert result.failed == 1 and result.relevant == 1
    assert len(result.items) == 2
