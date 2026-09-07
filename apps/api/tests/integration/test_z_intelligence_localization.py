from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    Channel,
    IntelligenceLocalization,
    Opportunity,
    OpportunitySignalLink,
    Signal,
    UserProfile,
    Video,
)
from ai_business_radar_api.services.intelligence_localization import source_text_hash
from ai_business_radar_api.services.radar_query import RadarQueryService, RadarRequest

NOW = datetime(2026, 9, 7, tzinfo=UTC)


@pytest.mark.asyncio
async def test_localized_product_reads_preserve_visibility_and_provenance(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    marker = uuid4().hex
    async with factory() as session, session.begin():
        user_id = (
            await session.execute(
                insert(UserProfile)
                .values(auth_user_id=uuid4(), role="user")
                .returning(UserProfile.id)
            )
        ).scalar_one()
        channel_id = (
            await session.execute(
                insert(Channel)
                .values(
                    youtube_channel_id=f"channel-{marker}",
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
                    youtube_video_id=f"video-{marker}",
                    channel_id=channel_id,
                    title="How VitalDesk Works",
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
                    statement="Dental leads enter the VitalDesk dashboard.",
                    evidence_text="Leads are organized inside the dashboard.",
                    industry="Dental",
                    customer_type="Dental practices",
                    claim_status="creator_claim",
                    confidence="0.96",
                    observed_at=NOW,
                    status="active",
                )
                .returning(Signal.id)
            )
        ).scalar_one()
        active_id = (
            await session.execute(
                insert(Opportunity)
                .values(
                    slug=f"active-localized-{marker}",
                    name="Dental lead workflow",
                    one_line_thesis="Organize appointment leads.",
                    market_stage="emerging",
                    status="active",
                    first_detected_at=NOW,
                    last_activity_at=NOW,
                )
                .returning(Opportunity.id)
            )
        ).scalar_one()
        candidate_id = (
            await session.execute(
                insert(Opportunity)
                .values(
                    slug=f"candidate-localized-{marker}",
                    name="Hidden candidate",
                    market_stage="unknown",
                    status="candidate",
                    first_detected_at=NOW,
                    last_activity_at=NOW,
                )
                .returning(Opportunity.id)
            )
        ).scalar_one()
        await session.execute(
            insert(OpportunitySignalLink).values(
                opportunity_id=active_id, signal_id=signal_id, relationship_type="supporting"
            )
        )
        rows = [
            dict(
                entity_type="signal",
                entity_id=signal_id,
                field_name="statement",
                locale="zh-CN",
                translated_text="牙科线索进入 VitalDesk 仪表盘。",
                source_text_hash=source_text_hash("Dental leads enter the VitalDesk dashboard."),
                translation_version="test-v1",
                status="current",
            ),
            dict(
                entity_type="signal",
                entity_id=signal_id,
                field_name="evidence_text",
                locale="zh-CN",
                translated_text="线索会整理到仪表盘中。",
                source_text_hash=source_text_hash("Leads are organized inside the dashboard."),
                translation_version="test-v1",
                status="current",
            ),
            dict(
                entity_type="opportunity",
                entity_id=active_id,
                field_name="name",
                locale="zh-CN",
                translated_text="牙科线索工作流",
                source_text_hash=source_text_hash("Dental lead workflow"),
                translation_version="test-v1",
                status="current",
            ),
            dict(
                entity_type="opportunity",
                entity_id=candidate_id,
                field_name="name",
                locale="zh-CN",
                translated_text="不可见候选机会",
                source_text_hash=source_text_hash("Hidden candidate"),
                translation_version="test-v1",
                status="current",
            ),
        ]
        await session.execute(insert(IntelligenceLocalization), rows)

    service = RadarQueryService(factory)
    signals = await service.signals(locale="zh-CN", opportunity_id=active_id)
    radar = await service.radar(user_id, RadarRequest(sort="recent"), "zh-CN")
    detail = await service.detail(user_id, str(active_id), "zh-CN")
    await engine.dispose()

    item = next(signal for signal in signals if signal.id == signal_id)
    assert item.statement == "牙科线索进入 VitalDesk 仪表盘。"
    assert item.evidence_text == "线索会整理到仪表盘中。"
    assert item.original_evidence_text == "Leads are organized inside the dashboard."
    assert item.evidence_localized is True and item.claim_status == "creator_claim"
    assert item.video_title == "How VitalDesk Works"
    assert item.channel_name == "Creative World Prime"
    assert item.opportunities[0].name == "牙科线索工作流"
    assert any(item.name == "牙科线索工作流" for item in radar.items)
    assert all(item.id != candidate_id for item in radar.items)
    assert detail.opportunity.name == "牙科线索工作流"


@pytest.mark.asyncio
async def test_localization_projection_uniqueness_is_version_safe(db_session):
    entity_id = uuid4()
    values = dict(
        entity_type="signal",
        entity_id=entity_id,
        field_name="statement",
        locale="zh-CN",
        translated_text="译文",
        source_text_hash=source_text_hash("source"),
        translation_version="test-v1",
        status="current",
    )
    await db_session.execute(insert(IntelligenceLocalization).values(**values))
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(insert(IntelligenceLocalization).values(**values))
            await db_session.flush()
