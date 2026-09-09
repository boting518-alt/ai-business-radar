from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import event, insert

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    Channel,
    Comment,
    IntelligenceLocalization,
    Opportunity,
    OpportunityEvidence,
    OpportunitySignalLink,
    Signal,
    Video,
)
from ai_business_radar_api.infrastructure.database.repositories.radar_queries import (
    RadarQueryRepository,
)
from ai_business_radar_api.services.intelligence_localization import source_text_hash
from ai_business_radar_api.services.radar_query import (
    OpportunityNotVisibleError,
    RadarQueryService,
)

NOW = datetime(2026, 9, 9, tzinfo=UTC)


@pytest.mark.asyncio
async def test_evidence_union_visibility_provenance_localization_and_pagination(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    marker = uuid4().hex
    async with factory() as session, session.begin():

        async def add(model, **values):
            return (
                await session.execute(insert(model).values(**values).returning(model.id))
            ).scalar_one()

        channel = await add(
            Channel,
            youtube_channel_id=marker,
            name="Persisted channel",
            first_seen_at=NOW,
            last_seen_at=NOW,
        )
        video = await add(
            Video,
            youtube_video_id=marker[:11],
            channel_id=channel,
            title="Persisted title",
            published_at=NOW,
            first_seen_at=NOW,
            last_seen_at=NOW,
            processing_status="processed",
        )
        broken = await add(
            Video,
            youtube_video_id=f"invalid/{marker}",
            channel_id=channel,
            title="Stored evidence, unusable external identity",
            published_at=NOW,
            first_seen_at=NOW,
            last_seen_at=NOW,
            processing_status="processed",
        )
        comment = await add(
            Comment,
            youtube_comment_id=f"comment-{marker}",
            video_id=video,
            text="原始评论，不是英文规范文本。",
            published_at=NOW,
            first_seen_at=NOW,
            author_hash="DO-NOT-EXPOSE",
        )
        active = await add(
            Opportunity,
            slug=f"evidence-{marker}",
            name="Evidence test",
            status="active",
            market_stage="unknown",
            first_detected_at=NOW,
            last_activity_at=NOW,
        )
        candidate = await add(
            Opportunity,
            slug=f"hidden-{marker}",
            name="Hidden",
            status="candidate",
            market_stage="unknown",
            first_detected_at=NOW,
            last_activity_at=NOW,
        )
        ids = {}
        for label, status, kind, relation in [
            ("video", "active", "video", "supporting"),
            ("comment", "active", "comment", "contradicting"),
            ("same_text", "active", "video", "supporting"),
            ("broken", "active", "video", "context"),
            ("review", "review", "video", "supporting"),
            ("rejected", "rejected", "video", "supporting"),
            ("ignored", "ignored", "video", "supporting"),
            ("unlinked", "active", "video", None),
            ("explicit_only", "active", "video", None),
        ]:
            source = comment if kind == "comment" else broken if label == "broken" else video
            ids[label] = await add(
                Signal,
                source_type=kind,
                source_id=source,
                comment_id=source if kind == "comment" else None,
                video_id=source if kind == "video" else None,
                signal_type="pricing" if kind == "comment" else "pain",
                industry=marker,
                statement="Canonical statement",
                evidence_text="Canonical excerpt",
                claim_status="unknown" if kind == "comment" else "creator_claim",
                confidence="0.8",
                observed_at=NOW,
                status=status,
            )
            if relation:
                await add(
                    OpportunitySignalLink,
                    opportunity_id=active,
                    signal_id=ids[label],
                    relationship_type=relation,
                )
        await add(
            OpportunitySignalLink,
            opportunity_id=candidate,
            signal_id=ids["unlinked"],
            relationship_type="supporting",
        )
        # Two references to one Signal, plus a reference already in the linked read model.
        for label in ("video", "explicit_only", "explicit_only", "rejected", "ignored", "review"):
            await add(
                OpportunityEvidence,
                opportunity_id=active,
                signal_id=ids[label],
                source_type="manual",
                evidence_type="pain",
                summary="Explicit reference",
            )
        manual = await add(
            OpportunityEvidence,
            opportunity_id=active,
            source_type="manual",
            evidence_type="market_context",
            summary="Editorial evidence",
            source_url="https://example.org/research",
            observed_at=None,
        )
        await add(
            IntelligenceLocalization,
            entity_type="signal",
            entity_id=ids["video"],
            field_name="statement",
            locale="zh-CN",
            translated_text="规范陈述译文",
            source_text_hash=source_text_hash("Canonical statement"),
            translation_version="translation-zh-CN-v001",
            status="current",
        )
        await add(
            IntelligenceLocalization,
            entity_type="signal",
            entity_id=ids["video"],
            field_name="evidence_text",
            locale="zh-CN",
            translated_text="摘录译文",
            source_text_hash=source_text_hash("Canonical excerpt"),
            translation_version="translation-zh-CN-v001",
            status="current",
        )
        await add(
            IntelligenceLocalization,
            entity_type="signal",
            entity_id=ids["comment"],
            field_name="statement",
            locale="zh-CN",
            translated_text="OUTDATED",
            source_text_hash=source_text_hash("Old text"),
            translation_version="translation-zh-CN-v001",
            status="current",
        )

    statements = []

    def count_queries(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", count_queries)
    service = RadarQueryService(factory)
    page = await service.evidence(str(active), 0, 100, "zh-CN")
    assert len(statements) == 4  # visibility, count, page, one localization batch
    statements.clear()
    first = await service.evidence(str(active), 0, 1, "zh-CN")
    assert len(statements) == 4
    event.remove(engine.sync_engine, "before_cursor_execute", count_queries)
    assert page.total == 6 and len(page.items) == 6 and not page.has_more
    assert first.total == 6 and first.has_more and first.items == page.items[:1]
    rest = await service.evidence(str(active), 1, 100, "zh-CN")
    assert first.items + rest.items == page.items
    beyond = await service.evidence(str(active), 99, 20)
    assert beyond.total == 6 and not beyond.items and not beyond.has_more
    pricing = await service.evidence(str(active), 0, 20, "en-US", "pricing")
    assert pricing.total == 1 and pricing.items[0].signal_id == ids["comment"]
    missing = await service.evidence(str(active), 0, 20, "en-US", "revenue")
    assert missing.total == 0 and not missing.items
    with pytest.raises(OpportunityNotVisibleError):
        await service.evidence(str(candidate), 0, 20)
    by_signal = {item.signal_id: item for item in page.items}
    assert set(by_signal) == {
        ids[k] for k in ("video", "comment", "same_text", "broken", "explicit_only")
    } | {None}
    item = by_signal[ids["video"]]
    assert item.evidence_kind == "linked_signal"
    assert item.statement == "规范陈述译文" and item.evidence_text == "摘录译文"
    assert (
        item.original_statement == "Canonical statement"
        and item.original_evidence_text == "Canonical excerpt"
    )
    assert item.statement_localized and item.evidence_localized and not item.localization_stale
    assert item.claim_status == "creator_claim" and item.observed_at == NOW
    assert item.source_url == f"https://www.youtube.com/watch?v={marker[:11]}"
    assert item.source_video_id == video and item.video_title == "Persisted title"
    assert item.channel_name == "Persisted channel"
    comment_item = by_signal[ids["comment"]]
    assert comment_item.source_url == item.source_url
    assert comment_item.source_navigation == "parent_video"
    assert comment_item.source_comment_id == comment
    assert comment_item.source_comment_text == "原始评论，不是英文规范文本。"
    assert comment_item.relationship_type == "contradicting"
    assert comment_item.statement == "Canonical statement" and comment_item.localization_stale
    assert by_signal[ids["same_text"]].statement == "Canonical statement"
    assert by_signal[ids["broken"]].source_navigation == "unavailable"
    assert by_signal[ids["broken"]].statement == "Canonical statement"
    assert by_signal[None].evidence_id == manual
    assert by_signal[None].source_url == "https://example.org/research"
    assert by_signal[None].claim_status is None
    assert page.items[-1].evidence_id == manual  # NULL observed_at sorts last
    async with factory() as session:
        summary = (await RadarQueryRepository(session).evidence_summaries([active]))[active]
    assert summary["active_signal_count"] == 4 and summary["supporting_signal_count"] == 2
    assert summary["distinct_video_count"] == 2 and summary["distinct_channel_count"] == 1
    global_feed = await service.signals(industry=marker, limit=100)
    # Dedicated filter by source observation allows all test records to fit the shared DB fixture.
    test_feed = await service.signals(opportunity_id=active, locale="zh-CN")
    assert {i.id for i in test_feed} == {
        ids[k] for k in ("video", "comment", "same_text", "broken")
    }
    assert any(i.id == ids["unlinked"] and not i.opportunities for i in global_feed)
    assert next(i for i in test_feed if i.id == ids["comment"]).source_url == item.source_url
    public = page.model_dump_json()
    assert (
        "DO-NOT-EXPOSE" not in public and "raw_output" not in public and "author_hash" not in public
    )
    await engine.dispose()
