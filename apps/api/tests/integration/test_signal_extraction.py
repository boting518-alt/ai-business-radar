from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from ai_business_radar_schemas import BusinessSignalExtractorOutput
from sqlalchemy import func, select, update

from ai_business_radar_api.infrastructure.ai import (
    AIProviderError,
    AIResponse,
    AIStructuredOutputError,
)
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import AIExtraction, Signal, Video
from ai_business_radar_api.infrastructure.database.repositories import SignalRepository
from ai_business_radar_api.services.signal_extraction import (
    BusinessSignalExtractionService,
    SignalBatchRequest,
)

from .test_ai_relevance import seed_video


@pytest_asyncio.fixture
async def signal_database(postgres_url: str) -> AsyncIterator[tuple[object, object]]:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    yield engine, factory
    await engine.dispose()


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
            model="signal-model",
            parsed=outcome,
            raw_output={"response_id": "safe", "output_text": "{}"},
            provider_request_id="safe-request",
            input_tokens=20,
            output_tokens=10,
            total_tokens=30,
        )


def output():
    return BusinessSignalExtractorOutput.model_validate(
        {
            "industry": "healthcare",
            "customer": "dental clinics",
            "problem": "missed calls",
            "solution": "AI voice agent",
            "business_model": "subscription",
            "technology": ["voice AI"],
            "distribution": ["direct sales"],
            "pricing": {"min": "99", "max": "199", "currency": "USD", "period": "month"},
            "signals": [
                {
                    "type": "pain",
                    "statement": "Dental clinics miss incoming calls.",
                    "evidence": "Clinics are described as missing calls.",
                    "claim_status": "creator_claim",
                    "confidence": "0.80",
                },
                {
                    "type": "pricing",
                    "statement": "The product is offered for 99 to 199 USD monthly.",
                    "evidence": "The description states a monthly price range.",
                    "claim_status": "creator_claim",
                    "confidence": "0.70",
                },
            ],
        }
    )


@pytest.mark.asyncio
async def test_valid_extraction_maps_atomic_review_signals_and_audit(signal_database) -> None:
    _, factory = signal_database
    video_id = await seed_video(factory, status="queued")
    ai = AIStub(output(), output())
    service = BusinessSignalExtractionService(factory, ai, provider="openai", model="signal-model")
    first = await service.extract(video_id)
    reused = await service.extract(video_id)
    forced = await service.extract(video_id, force=True)
    assert first.signals_created == 2 and reused.reused is True and len(ai.calls) == 2
    assert "transcript" not in ai.calls[0]["input_data"]
    async with factory() as session:
        rows = list(
            await session.scalars(
                select(Signal).where(Signal.video_id == video_id).order_by(Signal.created_at)
            )
        )
        extractions = list(
            await session.scalars(
                select(AIExtraction)
                .where(
                    AIExtraction.video_id == video_id, AIExtraction.task_type == "signal_extractor"
                )
                .order_by(AIExtraction.attempt_number)
            )
        )
        video = await session.get(Video, video_id)
    assert len(rows) == 4 and len(extractions) == 2 and forced.extraction_id == extractions[1].id
    assert rows[0].source_type == "video" and rows[0].source_id == video_id
    assert rows[0].ai_extraction_id == extractions[0].id and rows[0].status == "review"
    assert rows[0].claim_status == "creator_claim" and rows[0].confidence == Decimal("0.80")
    assert rows[0].evidence_text.startswith("Clinics") and rows[0].price_min is None
    assert rows[1].price_min == 99 and rows[1].price_max == 199 and rows[1].price_currency == "USD"
    assert rows[0].technology == ["voice AI"] and rows[0].distribution_channels == ["direct sales"]
    assert rows[0].revenue_claim_amount is None and rows[0].geography is None
    assert extractions[0].status == "completed" and extractions[0].total_tokens == 30
    assert extractions[0].prompt_version == "v003"
    assert extractions[0].prompt_hash == (
        "d91be041c6f50c0f97f5c9ba9d3469778ba92f1ee91d7063531df003a1c792e3"
    )
    assert (
        extractions[1].supersedes_extraction_id == extractions[0].id
        and video.processing_status == "queued"
    )


@pytest.mark.asyncio
async def test_prompt_rollback_creates_separate_history_without_mutating_v003(
    signal_database,
) -> None:
    _, factory = signal_database
    video_id = await seed_video(factory, status="queued")
    ai = AIStub(output(), output())
    current = BusinessSignalExtractionService(
        factory, ai, provider="openai", model="signal-model", prompt_version="v003"
    )
    rollback = BusinessSignalExtractionService(
        factory, ai, provider="openai", model="signal-model", prompt_version="v001"
    )
    await current.extract(video_id)
    await rollback.extract(video_id, force=True)
    async with factory() as session:
        rows = list(
            await session.scalars(
                select(AIExtraction)
                .where(AIExtraction.video_id == video_id)
                .order_by(AIExtraction.created_at)
            )
        )
    assert [row.prompt_version for row in rows] == ["v003", "v001"]
    assert rows[0].prompt_hash == "d91be041c6f50c0f97f5c9ba9d3469778ba92f1ee91d7063531df003a1c792e3"
    assert rows[1].prompt_hash == "e129d096c32b51356fd5a2280f80877a21759b70b0e4fa5d9c05b7bc945ff641"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "extraction_status", "video_status"),
    [
        (AIProviderError("safe"), "failed", "failed"),
        (
            AIStructuredOutputError("bad", raw_output={"response_id": "safe"}),
            "invalid_output",
            "review",
        ),
    ],
)
async def test_failure_creates_no_signals(
    signal_database, outcome, extraction_status, video_status
) -> None:
    _, factory = signal_database
    video_id = await seed_video(factory, status="queued")
    result = await BusinessSignalExtractionService(
        factory, AIStub(outcome), provider="openai", model="signal-model"
    ).extract(video_id)
    async with factory() as session:
        count = await session.scalar(
            select(func.count(Signal.id)).where(Signal.video_id == video_id)
        )
        extraction, video = (
            await session.get(AIExtraction, result.extraction_id),
            await session.get(Video, video_id),
        )
    assert (
        count == 0
        and extraction.status == extraction_status
        and video.processing_status == video_status
    )


@pytest.mark.asyncio
async def test_batch_isolates_one_provider_failure(signal_database) -> None:
    _, factory = signal_database
    async with factory() as session, session.begin():
        await session.execute(
            update(Video)
            .where(Video.processing_status == "queued")
            .values(processing_status="processed")
        )
    await seed_video(factory, status="queued", title="First")
    await seed_video(factory, status="queued", title="Second")
    result = await BusinessSignalExtractionService(
        factory, AIStub(AIProviderError("safe"), output()), provider="openai", model="signal-model"
    ).extract_batch(SignalBatchRequest(limit=2))
    assert result.requested == 2 and result.failed == 1 and result.processed == 1
    assert result.signals_created == 2


@pytest.mark.asyncio
async def test_signal_insert_failure_rolls_back_entire_signal_set(
    signal_database, monkeypatch
) -> None:
    _, factory = signal_database
    video_id = await seed_video(factory, status="queued")
    original = SignalRepository.create_many

    async def insert_then_fail(repository, values):
        await original(repository, values[:1])
        from sqlalchemy.exc import SQLAlchemyError

        raise SQLAlchemyError("forced rollback")

    monkeypatch.setattr(SignalRepository, "create_many", insert_then_fail)
    result = await BusinessSignalExtractionService(
        factory, AIStub(output()), provider="openai", model="signal-model"
    ).extract(video_id)
    async with factory() as session:
        count = await session.scalar(
            select(func.count(Signal.id)).where(Signal.video_id == video_id)
        )
    assert result.status == "failed" and count == 0
