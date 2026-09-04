from datetime import UTC, datetime
from uuid import uuid4

import pytest
from ai_business_radar_schemas import OpportunityNormalizerOutput
from sqlalchemy import func, insert, select

from ai_business_radar_api.infrastructure.ai import AIResponse
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    AIExtraction,
    Channel,
    Opportunity,
    OpportunitySignalLink,
    ReviewTask,
    Signal,
    Video,
)
from ai_business_radar_api.services.opportunity_normalization import (
    OpportunityNormalizationService,
)

NOW = datetime(2026, 9, 4, tzinfo=UTC)


class AIStub:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    async def structured_generate(self, **kwargs):
        self.calls.append(kwargs)
        output = self.outputs.pop(0)
        return AIResponse(
            provider="openai",
            model="normalizer-model",
            parsed=output,
            raw_output={"safe": True},
        )


async def seed_signal(factory, *, statement="Dental clinics miss calls"):
    async with factory() as session, session.begin():
        channel_id = (
            await session.execute(
                insert(Channel)
                .values(
                    youtube_channel_id=f"channel-{uuid4()}",
                    name="Channel",
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
                    youtube_video_id=f"video-{uuid4()}",
                    channel_id=channel_id,
                    title="Dental workflow",
                    published_at=NOW,
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                    processing_status="queued",
                )
                .returning(Video.id)
            )
        ).scalar_one()
        return (
            await session.execute(
                insert(Signal)
                .values(
                    source_type="video",
                    source_id=video_id,
                    video_id=video_id,
                    signal_type="pain",
                    statement=statement,
                    industry="Dental",
                    customer_type="Clinic",
                    problem=statement,
                    claim_status="creator_claim",
                    confidence="0.8",
                    observed_at=NOW,
                    status="review",
                )
                .returning(Signal.id)
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_create_is_atomic_audited_and_reused(postgres_url) -> None:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    signal_id = await seed_signal(factory)
    output = OpportunityNormalizerOutput(
        action="CREATE",
        opportunity_id=None,
        canonical_name="AI Dental Receptionist",
        confidence="0.9",
        reason="Distinct grounded opportunity",
    )
    ai = AIStub(output)
    service = OpportunityNormalizationService(
        factory, ai, provider="openai", model="normalizer-model"
    )
    first = await service.normalize(signal_id)
    reused = await service.normalize(signal_id)
    async with factory() as session:
        signal = await session.get(Signal, signal_id)
        opportunity = await session.get(Opportunity, first.opportunity_id)
        links = await session.scalar(
            select(func.count(OpportunitySignalLink.id)).where(
                OpportunitySignalLink.signal_id == signal_id
            )
        )
        extraction = await session.get(AIExtraction, first.extraction_id)
    await engine.dispose()
    assert first.action == "CREATE" and reused.reused and len(ai.calls) == 1
    assert opportunity.slug == "ai-dental-receptionist" and opportunity.status == "candidate"
    assert signal.status == "active" and links == 1
    assert extraction.source_type == "signal" and extraction.signal_id == signal_id


@pytest.mark.asyncio
async def test_low_confidence_create_routes_to_actionable_review(postgres_url) -> None:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    signal_id = await seed_signal(factory, statement="Maybe automate a niche workflow")
    output = OpportunityNormalizerOutput(
        action="CREATE",
        opportunity_id=None,
        canonical_name="Niche Automation",
        confidence="0.5",
        reason="Uncertain",
    )
    result = await OpportunityNormalizationService(
        factory, AIStub(output), provider="openai", model="normalizer-model"
    ).normalize(signal_id)
    async with factory() as session:
        review = await session.get(ReviewTask, result.review_task_id)
        opportunity_count = await session.scalar(
            select(func.count(Opportunity.id)).where(Opportunity.slug == "niche-automation")
        )
    await engine.dispose()
    assert result.action == "REVIEW" and opportunity_count == 0
    assert review.review_type == "opportunity_creation"
    assert review.context["reason"] == "create_confidence_below_threshold"


@pytest.mark.asyncio
async def test_match_is_bounded_and_hallucinated_id_is_invalid(postgres_url) -> None:
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    signal_id = await seed_signal(factory, statement="Dental clinic call automation demand")
    async with factory() as session, session.begin():
        opportunity_id = (
            await session.execute(
                insert(Opportunity)
                .values(
                    slug=f"dental-call-{uuid4()}",
                    name="Dental Call Automation",
                    one_line_thesis="Original canonical thesis",
                    industry="Dental",
                    customer_type="Clinic",
                    problem="Missed calls",
                    market_stage="unknown",
                    status="active",
                    first_detected_at=NOW,
                    last_activity_at=NOW,
                )
                .returning(Opportunity.id)
            )
        ).scalar_one()
    output = OpportunityNormalizerOutput(
        action="MATCH",
        opportunity_id=opportunity_id,
        canonical_name="Model must not overwrite this",
        confidence="0.9",
        reason="Candidate matches",
    )
    service = OpportunityNormalizationService(
        factory, AIStub(output), provider="openai", model="normalizer-model"
    )
    result = await service.normalize(signal_id)
    async with factory() as session:
        opportunity = await session.get(Opportunity, opportunity_id)
    assert result.action == "MATCH" and opportunity.one_line_thesis == "Original canonical thesis"

    bad_signal_id = await seed_signal(factory, statement="Dental clinic call automation demand")
    hallucinated = OpportunityNormalizerOutput(
        action="MATCH",
        opportunity_id=uuid4(),
        canonical_name="Fake",
        confidence="0.99",
        reason="Not supplied",
    )
    invalid = await OpportunityNormalizationService(
        factory, AIStub(hallucinated), provider="openai", model="normalizer-model"
    ).normalize(bad_signal_id)
    async with factory() as session:
        link_count = await session.scalar(
            select(func.count(OpportunitySignalLink.id)).where(
                OpportunitySignalLink.signal_id == bad_signal_id
            )
        )
    await engine.dispose()
    assert invalid.status == "invalid_output" and link_count == 0
