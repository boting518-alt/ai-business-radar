from datetime import UTC, datetime
from uuid import uuid4

import pytest
from ai_business_radar_schemas import IntelligenceTranslationOutput, TranslationField
from sqlalchemy import func, insert, select, update

from ai_business_radar_api.infrastructure.ai.client import AIResponse
from ai_business_radar_api.infrastructure.ai.errors import AITransientError
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    Channel,
    IntelligenceLocalization,
    Opportunity,
    Signal,
    Video,
)
from ai_business_radar_api.services.intelligence_translation import (
    IntelligenceTranslationService,
    PermanentTranslationError,
    TranslationBatchRequest,
    TranslationRequest,
)

NOW = datetime(2026, 9, 8, tzinfo=UTC)


class FakeAI:
    def __init__(self, outputs=None, error=None):
        self.outputs = outputs or {}
        self.error = error
        self.calls = []

    async def structured_generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        requested = kwargs["input_data"]["fields"]
        fields = [
            TranslationField(
                field_name=item["field_name"],
                translated_text=self.outputs.get(
                    item["field_name"], f"译文：{item['source_text']}"
                ),
            )
            for item in requested
            if item["field_name"] not in self.outputs.get("omit", [])
        ]
        parsed = IntelligenceTranslationOutput(
            translations=fields,
            preserved_terms=["VitalDesk"]
            if any("VitalDesk" in item["source_text"] for item in requested)
            else [],
            warnings=[],
        )
        return AIResponse(
            provider="openai",
            model="translation-test-model",
            parsed=parsed,
            raw_output={"safe": True},
            provider_request_id="response-test",
            input_tokens=31,
            output_tokens=17,
            total_tokens=48,
        )


async def seed(factory):
    async with factory() as session, session.begin():
        channel_id = (
            await session.execute(
                insert(Channel)
                .values(
                    youtube_channel_id=f"translation-channel-{uuid4()}",
                    name="Creative World Prime",
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
                    youtube_video_id=f"translation-video-{uuid4()}",
                    channel_id=channel_id,
                    title="VitalDesk Source Video",
                    published_at=NOW,
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                    processing_status="processed",
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
                    signal_type="workflow",
                    statement="Creator claims VitalDesk reduces missed calls.",
                    evidence_text="VitalDesk organizes dental appointment leads.",
                    claim_status="creator_claim",
                    confidence="0.9",
                    status="active",
                )
                .returning(Signal.id)
            )
        ).scalar_one()
        opportunity_id = (
            await session.execute(
                insert(Opportunity)
                .values(
                    slug=f"translation-{uuid4()}",
                    name="VitalDesk dental workflow",
                    one_line_thesis="Creator claims fewer missed calls.",
                    problem="Dental practices miss calls.",
                    solution="VitalDesk organizes appointment leads.",
                    market_stage="emerging",
                    status="active",
                    first_detected_at=NOW,
                    last_activity_at=NOW,
                )
                .returning(Opportunity.id)
            )
        ).scalar_one()
    return signal_id, opportunity_id


@pytest.mark.asyncio
async def test_translation_generation_reuse_force_staleness_and_audit(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    signal_id, _ = await seed(factory)
    ai = FakeAI(
        {
            "statement": "创作者称 VitalDesk 可减少漏接电话。",
            "evidence_text": "VitalDesk 会整理牙科预约线索。",
        }
    )
    service = IntelligenceTranslationService(
        factory, ai, provider="openai", model="translation-test-model"
    )
    request = TranslationRequest(entity_type="signal", entity_id=signal_id)
    generated = await service.translate_entity(request)
    reused = await service.translate_entity(request)
    forced = await service.translate_entity(request.model_copy(update={"force": True}))
    async with factory() as session, session.begin():
        canonical = await session.get(Signal, signal_id)
        canonical_statement = canonical.statement
        canonical_evidence_text = canonical.evidence_text
        rows = list(
            await session.scalars(
                select(IntelligenceLocalization).where(
                    IntelligenceLocalization.entity_id == signal_id
                )
            )
        )
        await session.execute(
            update(Signal)
            .where(Signal.id == signal_id)
            .values(statement="Creator claims VitalDesk reduces missed calls substantially.")
        )
    stale_regenerated = await service.translate_entity(request)
    async with factory() as session:
        all_rows = list(
            await session.scalars(
                select(IntelligenceLocalization).where(
                    IntelligenceLocalization.entity_id == signal_id
                )
            )
        )
    await engine.dispose()

    assert generated.translated_fields == ["statement", "evidence_text"]
    assert reused.reused_fields == ["statement", "evidence_text"] and len(ai.calls) == 3
    assert forced.translated_fields == ["statement", "evidence_text"]
    assert stale_regenerated.translated_fields == ["statement"]
    assert canonical_statement == "Creator claims VitalDesk reduces missed calls."
    assert canonical_evidence_text == "VitalDesk organizes dental appointment leads."
    assert len(rows) == 2 and all(
        row.translation_version == "translation-zh-CN-v001" for row in rows
    )
    assert all(row.translation_provider == "openai" for row in rows)
    assert all(row.prompt_hash and len(row.prompt_hash) == 64 for row in rows)
    assert all(row.provider_request_id == "response-test" for row in rows)
    assert all(row.input_tokens == 31 and row.output_tokens == 17 for row in rows)
    assert next(row for row in rows if row.field_name == "statement").translated_text.startswith(
        "创作者称"
    )
    assert "VitalDesk" in next(
        row for row in rows if row.field_name == "evidence_text"
    ).translated_text
    assert len(all_rows) == 3
    assert any(row.status == "stale" and row.field_name == "statement" for row in all_rows)


@pytest.mark.asyncio
async def test_opportunity_translation_dry_run_and_atomic_failure(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    _, opportunity_id = await seed(factory)
    dry_ai = FakeAI(error=AssertionError("must not call"))
    dry_service = IntelligenceTranslationService(
        factory, dry_ai, provider="openai", model="translation-test-model"
    )
    dry = await dry_service.translate_entity(
        TranslationRequest(entity_type="opportunity", entity_id=opportunity_id, dry_run=True)
    )
    dry_batch = await dry_service.translate_batch(
        TranslationBatchRequest(
            entity_type="opportunities", limit=1, dry_run=True, only_missing=True
        )
    )
    invalid_ai = FakeAI({"omit": ["solution"]})
    invalid_service = IntelligenceTranslationService(
        factory, invalid_ai, provider="openai", model="translation-test-model"
    )
    with pytest.raises(PermanentTranslationError):
        await invalid_service.translate_entity(
            TranslationRequest(entity_type="opportunity", entity_id=opportunity_id)
        )
    transient = IntelligenceTranslationService(
        factory,
        FakeAI(error=AITransientError("temporary")),
        provider="openai",
        model="translation-test-model",
    )
    with pytest.raises(AITransientError):
        await transient.translate_entity(
            TranslationRequest(entity_type="opportunity", entity_id=opportunity_id)
        )
    async with factory() as session:
        count = await session.scalar(
            select(func.count(IntelligenceLocalization.id)).where(
                IntelligenceLocalization.entity_id == opportunity_id
            )
        )
        canonical = await session.get(Opportunity, opportunity_id)
    await engine.dispose()
    assert dry_ai.calls == [] and dry.translated_fields == []
    assert all(item.would_translate for item in dry.plan)
    assert dry_batch.translated == 0 and dry_batch.reused == 0
    assert count == 0
    assert canonical.name == "VitalDesk dental workflow"
