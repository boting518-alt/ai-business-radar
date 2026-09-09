from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from ai_business_radar_schemas import ReviewDecisionRequest
from sqlalchemy import func, insert, select, text

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    AIExtraction,
    Channel,
    Opportunity,
    OpportunityEvidence,
    OpportunitySignalLink,
    ReviewTask,
    Signal,
    UserProfile,
    Video,
)
from ai_business_radar_api.infrastructure.database.models.fact import SignalSemanticAudit
from ai_business_radar_api.infrastructure.database.repositories.scores import (
    OpportunityScoreRepository,
)
from ai_business_radar_api.services.opportunity_normalization import OpportunityNormalizationService
from ai_business_radar_api.services.opportunity_scoring import OpportunityScoringService
from ai_business_radar_api.services.radar_query import RadarQueryService
from ai_business_radar_api.services.review_workflow import ReviewTaskConflict, ReviewWorkflowService
from ai_business_radar_api.services.signal_semantic_audit import audit
from ai_business_radar_api.services.signal_semantics import (
    SemanticDecision,
    persist_decision,
)
from ai_business_radar_api.services.translation_orchestration import (
    TranslationCoverageReconciliationService,
)

NOW = datetime(2026, 9, 9, tzinfo=UTC)


@pytest.mark.asyncio
async def test_semantic_projection_preserves_history_and_blocks_all_consumers(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    marker = uuid4().hex
    async with factory() as session, session.begin():

        async def add(entity_model, **values):
            return (
                await session.execute(
                    insert(entity_model).values(**values).returning(entity_model.id)
                )
            ).scalar_one()

        channel = await add(
            Channel,
            youtube_channel_id=marker,
            name="Semantic channel",
            first_seen_at=NOW,
            last_seen_at=NOW,
        )
        video = await add(
            Video,
            youtube_video_id=marker[:11],
            channel_id=channel,
            title="Semantic product",
            published_at=NOW,
            first_seen_at=NOW,
            last_seen_at=NOW,
            processing_status="queued",
        )
        opportunity = await add(
            Opportunity,
            slug=marker,
            name="Dental workflow",
            status="active",
            market_stage="unknown",
            first_detected_at=NOW,
            last_activity_at=NOW,
        )
        cases = [
            ("cta", "purchase_intent", "Pre-order now."),
            ("buyer", "purchase_intent", "I ordered one"),
            ("affiliate", "revenue", "As an Amazon Associate I earn from qualifying purchases"),
            ("ambiguous", "purchase_intent", "When will it launch?"),
            ("pricing", "pricing", "$499 pre-order"),
            ("same", "purchase_intent", "I ordered one"),
            ("paraphrase", "purchase_intent", "I already ordered one"),
        ]
        ids = {}
        for index, (name, kind, words) in enumerate(cases):
            extraction = await add(
                AIExtraction,
                source_type="video",
                source_id=video,
                video_id=video,
                task_type="signal_extractor",
                provider="test",
                model="test",
                prompt_version="v001" if index < 5 else "v003",
                input_hash=uuid4().hex,
                status="completed",
                raw_output={"kept": name},
                parsed_output={"kept": name},
                attempt_number=index + 1,
            )
            ids[name] = await add(
                Signal,
                source_type="video",
                source_id=video,
                video_id=video,
                ai_extraction_id=extraction,
                signal_type=kind,
                statement=words,
                evidence_text=words,
                status="active",
                claim_status="creator_claim",
                confidence=1,
                industry=marker,
                created_at=NOW + timedelta(seconds=index),
                observed_at=NOW,
            )
            await add(
                OpportunitySignalLink,
                opportunity_id=opportunity,
                signal_id=ids[name],
                relationship_type="supporting",
                confidence=1,
            )
    score_service = OpportunityScoringService(factory, clock=lambda: NOW + timedelta(hours=2))
    before = await score_service.score(opportunity)
    planned = await audit(factory, signal_ids=list(ids.values()))
    assert planned["invalid_semantic"] == 2
    assert planned["flagged_review"] == 1
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count(SignalSemanticAudit.id)).where(
                    SignalSemanticAudit.signal_id.in_(ids.values())
                )
            )
            == 0
        )
    applied = await audit(factory, signal_ids=list(ids.values()), apply=True)
    assert applied["supersession_candidates"] == 1
    repeated = await audit(factory, signal_ids=list(ids.values()), apply=True)
    assert not any(row.get("changed") for row in repeated["changes"])
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count(SignalSemanticAudit.id)).where(
                    SignalSemanticAudit.signal_id.in_(ids.values())
                )
            )
            == 7
        )
        assert (
            await session.scalar(
                select(func.count(ReviewTask.id)).where(ReviewTask.target_id.in_(ids.values()))
            )
            == 3
        )
    async with factory() as session, session.begin():
        buyer = await session.get(Signal, ids["buyer"])
        assert not await persist_decision(session, buyer)
        same = await session.get(Signal, ids["same"])
        assert same.semantic_status == "superseded" and same.superseded_by == buyer.id
        assert (await session.get(Signal, ids["paraphrase"])).semantic_status == "current"
        invalid = await session.get(Signal, ids["cta"])
        assert invalid.status == "active" and invalid.signal_type == "purchase_intent"
        assert invalid.claim_status == "creator_claim"
        assert (await session.get(AIExtraction, invalid.ai_extraction_id)).raw_output == {
            "kept": "cta"
        }
        assert len(await OpportunityScoreRepository(session).load_active_signals(opportunity)) == 3
        assert not await TranslationCoverageReconciliationService._eligible(
            session, "signal", invalid
        )
        task = await session.scalar(select(ReviewTask).where(ReviewTask.target_id == invalid.id))
        task_id = task.id
    normalizer = OpportunityNormalizationService(factory, object(), provider="test", model="test")
    blocked = await normalizer.normalize(ids["cta"], force=True)
    assert blocked.status == "semantic_blocked" and blocked.extraction_id is None
    with pytest.raises(ReviewTaskConflict, match="Semantic guardrail"):
        await ReviewWorkflowService(factory).decide(
            task_id, uuid4(), ReviewDecisionRequest(decision="approve")
        )
    radar = RadarQueryService(factory)
    feed = await radar.signals(industry=marker, offset=0, limit=100)
    assert {x.id for x in feed} == {ids["buyer"], ids["pricing"], ids["paraphrase"]}
    page = await radar.evidence(str(opportunity), 0, 100)
    assert page.total == 3 and all(x.evidence_role != "creator_monetization" for x in page.items)
    after = await OpportunityScoringService(factory, clock=lambda: NOW + timedelta(hours=3)).score(
        opportunity, force=True
    )
    assert after.scoring_version == before.scoring_version == "score-v001"
    assert after.score_id != before.score_id
    assert after.components.demand_evidence_score < before.components.demand_evidence_score
    assert after.components.revenue_evidence_score < before.components.revenue_evidence_score
    async with factory() as session:
        history = await OpportunityScoreRepository(session).list_history(
            opportunity, scoring_version="score-v001"
        )
        assert len(history) == 2
        assert (
            await session.scalar(
                select(func.count(OpportunitySignalLink.id)).where(
                    OpportunitySignalLink.opportunity_id == opportunity
                )
            )
            == 7
        )
    with pytest.raises(RuntimeError, match="rollback probe"):
        async with factory() as session, session.begin():
            signal = await session.get(Signal, ids["paraphrase"])
            await persist_decision(session, signal, SemanticDecision("review", "rollback_probe"))
            raise RuntimeError("rollback probe")
    user_auth = uuid4()
    async with factory() as session, session.begin():
        session.add(
            UserProfile(auth_user_id=user_auth, role="user", created_at=NOW, updated_at=NOW)
        )
        session.add(
            OpportunityEvidence(
                opportunity_id=opportunity,
                signal_id=ids["cta"],
                evidence_type="demand",
                summary="Retained CTA",
                created_at=NOW,
                source_type="manual",
            )
        )
    async with factory() as session, session.begin():
        assert (await session.get(Signal, ids["paraphrase"])).semantic_status == "current"
        await session.execute(
            text("SELECT set_config('request.jwt.claim.sub', :auth, true)"),
            {"auth": str(user_auth)},
        )
        await session.execute(text("SET LOCAL ROLE authenticated"))
        visible = list(await session.scalars(select(Signal.id).where(Signal.id.in_(ids.values()))))
        assert set(visible) == {ids["buyer"], ids["pricing"], ids["paraphrase"]}
        assert await session.scalar(select(func.count(SignalSemanticAudit.id))) == 0
        assert (
            await session.scalar(
                select(func.count(OpportunityEvidence.id)).where(
                    OpportunityEvidence.signal_id == ids["cta"]
                )
            )
            == 0
        )
    await engine.dispose()
