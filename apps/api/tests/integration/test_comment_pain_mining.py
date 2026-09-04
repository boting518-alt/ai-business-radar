from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from ai_business_radar_schemas import CommentPainMinerOutput
from sqlalchemy import delete, func, insert, select

from ai_business_radar_api.infrastructure.ai import AIProviderError, AIResponse
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    AIExtraction,
    Channel,
    Comment,
    Signal,
    Video,
)
from ai_business_radar_api.infrastructure.database.repositories import SignalRepository
from ai_business_radar_api.services.comment_pain_mining import (
    CommentPainBatchRequest,
    CommentPainMiningService,
)
from ai_business_radar_api.services.relevance_filter import canonical_input_hash

NOW = datetime(2026, 9, 4, tzinfo=UTC)


class AIStub:
    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), []

    async def structured_generate(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return AIResponse(
            provider="openai",
            model="pain-model",
            parsed=outcome,
            raw_output={"response_id": "safe"},
            provider_request_id="safe",
            input_tokens=10,
            output_tokens=8,
            total_tokens=18,
        )


@pytest_asyncio.fixture
async def pain_database(postgres_url: str) -> AsyncIterator[object]:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    yield factory
    await engine.dispose()


async def seed_comment(factory, *, text="We miss calls and use a spreadsheet workaround."):
    async with factory() as session, session.begin():
        channel_id = (
            await session.execute(
                insert(Channel)
                .values(
                    youtube_channel_id=f"channel-{uuid4()}",
                    name="Channel",
                    channel_type="vendor",
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                    created_at=NOW,
                    updated_at=NOW,
                )
                .returning(Channel.id)
            )
        ).scalar_one()
        video_id = (
            await session.execute(
                insert(Video)
                .values(
                    youtube_video_id=f"video-{uuid4()}",
                    channel_id=channel_id,
                    title="AI workflow",
                    published_at=NOW,
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                    processing_status="queued",
                    created_at=NOW,
                    updated_at=NOW,
                )
                .returning(Video.id)
            )
        ).scalar_one()
        comment_id = (
            await session.execute(
                insert(Comment)
                .values(
                    youtube_comment_id=f"comment-{uuid4()}",
                    video_id=video_id,
                    text=text,
                    published_at=NOW,
                    source_updated_at=NOW,
                    like_count=3,
                    reply_count=0,
                    author_hash="must-not-send",
                    language="en",
                    first_seen_at=NOW,
                    created_at=NOW,
                    updated_at=NOW,
                )
                .returning(Comment.id)
            )
        ).scalar_one()
    return comment_id, video_id


def output(comment_id, categories=("existing pain", "current workaround")):
    return CommentPainMinerOutput.model_validate(
        {
            "signals": [
                {
                    "category": category,
                    "pain": f"Observation: {category}",
                    "current_solution": "spreadsheet" if category == "current workaround" else None,
                    "requested_solution": "automation" if category == "feature request" else None,
                    "spend": "200" if category == "existing spending" else None,
                    "purchase_intent": category in {"purchase intent", "willingness to pay"},
                    "evidence_strength": "0.8",
                    "comment_id": str(comment_id),
                }
                for category in categories
            ]
        }
    )


@pytest.mark.asyncio
async def test_categories_provenance_privacy_reuse_and_force(pain_database) -> None:
    factory = pain_database
    comment_id, video_id = await seed_comment(factory)
    categories = (
        "existing pain",
        "current workaround",
        "purchase intent",
        "feature request",
        "competitor usage",
        "existing spending",
    )
    ai = AIStub(output(comment_id, categories), output(comment_id, categories))
    service = CommentPainMiningService(factory, ai, provider="openai", model="pain-model")
    first, reused = await service.mine(comment_id), await service.mine(comment_id)
    forced = await service.mine(comment_id, force=True)
    assert first.signals_created == 6 and reused.reused and len(ai.calls) == 2
    supplied = str(ai.calls[0]["input_data"])
    assert (
        "must-not-send" not in supplied
        and "author" not in supplied
        and "transcript" not in supplied
    )
    async with factory() as session:
        rows = list(
            await session.scalars(
                select(Signal).where(Signal.comment_id == comment_id).order_by(Signal.created_at)
            )
        )
        extractions = list(
            await session.scalars(
                select(AIExtraction)
                .where(AIExtraction.comment_id == comment_id)
                .order_by(AIExtraction.attempt_number)
            )
        )
        video = await session.get(Video, video_id)
    assert len(rows) == 12 and forced.extraction_id == extractions[1].id
    assert [row.signal_type for row in rows[:6]] == [
        "pain",
        "workflow",
        "purchase_intent",
        "feature_request",
        "competition",
        "pricing",
    ]
    assert all(row.source_type == "comment" and row.source_id == comment_id for row in rows)
    assert all(
        row.video_id is None and row.status == "review" and row.claim_status == "unknown"
        for row in rows
    )
    assert (
        rows[0].ai_extraction_id == extractions[0].id
        and rows[0].evidence_strength == rows[0].confidence
    )
    assert rows[-1].price_min is None and video.processing_status == "queued"
    assert (
        extractions[0].status == "completed"
        and extractions[1].supersedes_extraction_id == extractions[0].id
    )


@pytest.mark.asyncio
async def test_empty_is_success_and_mismatch_is_invalid(pain_database) -> None:
    factory = pain_database
    empty_id, _ = await seed_comment(factory, text="Great video")
    mismatch_id, _ = await seed_comment(factory, text="I would pay for this")
    ai = AIStub(output(empty_id, ()), output(uuid4(), ("purchase intent",)))
    service = CommentPainMiningService(factory, ai, provider="openai", model="pain-model")
    empty = await service.mine(empty_id)
    mismatch = await service.mine(mismatch_id)
    assert empty.status == "completed" and empty.mined and empty.signals_created == 0
    assert mismatch.status == "invalid_output"
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count(Signal.id)).where(Signal.comment_id.in_([empty_id, mismatch_id]))
            )
            == 0
        )


@pytest.mark.asyncio
async def test_provider_failure_and_transaction_rollback_create_no_signals(
    pain_database, monkeypatch
) -> None:
    factory = pain_database
    failed_id, _ = await seed_comment(factory)
    rollback_id, _ = await seed_comment(factory)
    failed = await CommentPainMiningService(
        factory, AIStub(AIProviderError("safe")), provider="openai", model="pain-model"
    ).mine(failed_id)
    original = SignalRepository.create_many

    async def insert_then_fail(repository, values):
        await original(repository, values[:1])
        from sqlalchemy.exc import SQLAlchemyError

        raise SQLAlchemyError("rollback")

    monkeypatch.setattr(SignalRepository, "create_many", insert_then_fail)
    rolled_back = await CommentPainMiningService(
        factory, AIStub(output(rollback_id)), provider="openai", model="pain-model"
    ).mine(rollback_id)
    async with factory() as session:
        count = await session.scalar(
            select(func.count(Signal.id)).where(Signal.comment_id.in_([failed_id, rollback_id]))
        )
    assert failed.status == "failed" and rolled_back.status == "failed" and count == 0


@pytest.mark.asyncio
async def test_batch_failure_isolated_and_comment_change_changes_hash(pain_database) -> None:
    factory = pain_database
    async with factory() as session, session.begin():
        await session.execute(delete(Signal))
        await session.execute(delete(AIExtraction))
        await session.execute(delete(Comment))
    first_id, _ = await seed_comment(factory, text="pain one")
    second_id, _ = await seed_comment(factory, text="pain two")
    async with factory() as session:
        ordered = list(
            await session.scalars(
                select(Comment).order_by(Comment.first_seen_at, Comment.id).limit(2)
            )
        )
    ai = AIStub(AIProviderError("safe"), output(ordered[1].id, ("unmet need",)))
    result = await CommentPainMiningService(
        factory, ai, provider="openai", model="pain-model"
    ).mine_batch(CommentPainBatchRequest(limit=2))
    assert result.requested == 2 and result.failed == 1 and result.signals_created == 1
    before = ai.calls[0]["input_data"]
    before_hash = canonical_input_hash(
        before, prompt_version="v001", task_type="comment_pain_miner"
    )
    before["comment"]["text"] = "changed"
    after_hash = canonical_input_hash(before, prompt_version="v001", task_type="comment_pain_miner")
    assert before_hash != after_hash and first_id != second_id
