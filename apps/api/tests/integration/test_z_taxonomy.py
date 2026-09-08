from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import insert, select

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    Opportunity,
    Signal,
    SignalTaxonomyMapping,
)
from ai_business_radar_api.services.radar_query import RadarQueryService, RadarRequest
from ai_business_radar_api.services.taxonomy import TaxonomyMappingService

from .test_ai_relevance import seed_video


@pytest.mark.asyncio
async def test_taxonomy_labels_alias_mapping_filters_and_free_text_preservation(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    now = datetime.now(UTC)
    video_id = await seed_video(factory, status="processed")
    async with factory() as session, session.begin():
        opportunity_id = (
            await session.execute(
                insert(Opportunity)
                .values(
                    slug=f"tax-{uuid4()}",
                    name="Dental AI",
                    industry="Dental practices and dental offices",
                    customer_type="Dental practices",
                    market_stage="emerging",
                    status="active",
                    first_detected_at=now,
                    last_activity_at=now,
                )
                .returning(Opportunity.id)
            )
        ).scalar_one()
        signal_id = (
            await session.execute(
                insert(Signal)
                .values(
                    source_type="video",
                    source_id=video_id,
                    video_id=video_id,
                    signal_type="pain",
                    statement="Calls are missed",
                    industry="Dental practices",
                    customer_type="Dental practices",
                    claim_status="unknown",
                    confidence=1,
                    observed_at=now,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
                .returning(Signal.id)
            )
        ).scalar_one()
    service = TaxonomyMappingService(factory)
    assert (
        await service.map_text("signal", signal_id, "industry", "Dental Practices!")
    ).taxonomy_code == "healthcare.dental"
    assert (
        await service.map_text("signal", signal_id, "customer", "Dental patients")
    ).taxonomy_code is None
    assert (
        await service.map_text("signal", signal_id, "industry", "Shopify")
    ).taxonomy_code is None
    await service.apply_rule("signal", signal_id, "industry")
    await service.apply_rule("signal", signal_id, "customer")
    await service.set_mapping("opportunity", opportunity_id, "industry", "healthcare.dental")
    await service.set_mapping(
        "opportunity", opportunity_id, "customer", "organization.dental_practice"
    )
    zh = await service.nodes("industry", "zh-CN")
    assert next(item for item in zh if item.code == "healthcare.dental").label == "牙科"
    radar = await RadarQueryService(factory).radar(
        uuid4(), RadarRequest(sort="recent", industry_code="healthcare.dental"), "zh-CN"
    )
    assert radar.total == 1 and radar.items[0].industry_taxonomy.label == "牙科"
    signals = await RadarQueryService(factory).signals(
        customer_code="organization.dental_practice", locale="en-US"
    )
    assert any(
        item.id == signal_id and item.customer_taxonomy.label == "Dental Practice"
        for item in signals
    )
    async with factory() as session:
        opportunity = await session.get(Opportunity, opportunity_id)
        signal = await session.get(Signal, signal_id)
        assert opportunity.industry == "Dental practices and dental offices"
        assert signal.customer_type == "Dental practices"
    await service.clear_mapping("signal", signal_id, "customer")
    async with factory() as session:
        assert (
            await session.scalar(
                select(SignalTaxonomyMapping).where(
                    SignalTaxonomyMapping.signal_id == signal_id,
                    SignalTaxonomyMapping.taxonomy_type == "customer",
                    SignalTaxonomyMapping.mapping_status == "active",
                )
            )
            is None
        )
    await engine.dispose()
