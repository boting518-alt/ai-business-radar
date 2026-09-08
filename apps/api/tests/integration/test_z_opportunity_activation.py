from datetime import UTC, datetime
from uuid import uuid4

import pytest
from ai_business_radar_schemas import ReviewDecisionRequest
from sqlalchemy import insert

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    Channel,
    Opportunity,
    OpportunityScore,
    OpportunitySignalLink,
    ReviewTask,
    Signal,
    UserProfile,
    Video,
)
from ai_business_radar_api.services.opportunity_activation import (
    OpportunityActivationNotEligible,
    OpportunityActivationReadinessService,
)
from ai_business_radar_api.services.radar_query import RadarQueryService, RadarRequest
from ai_business_radar_api.services.review_workflow import (
    InvalidReviewDecision,
    ReviewTaskConflict,
    ReviewWorkflowService,
)

NOW = datetime(2026, 9, 7, tzinfo=UTC)


class TranslationTriggerStub:
    def __init__(self):
        self.calls = []

    async def best_effort_enqueue(self, entity_type, entity_id, *, reason):
        self.calls.append((entity_type, entity_id, reason))
        return True


async def opportunity(session, *, name="Dental AI Receptionist", status="candidate", **values):
    return (
        await session.execute(
            insert(Opportunity)
            .values(
                slug=f"activation-{uuid4()}",
                name=name,
                one_line_thesis=values.pop(
                    "one_line_thesis", "Automates dental appointment intake"
                ),
                customer_type=values.pop("customer_type", "Dental practices"),
                problem=values.pop("problem", "Missed appointment calls"),
                solution=values.pop("solution", "AI receptionist workflow"),
                market_stage="unknown",
                status=status,
                first_detected_at=NOW,
                last_activity_at=NOW,
                **values,
            )
            .returning(Opportunity)
        )
    ).scalar_one()


async def supporting_signal(session, opportunity_id, *, channel=None):
    channel = (
        channel
        or (
            await session.execute(
                insert(Channel)
                .values(
                    youtube_channel_id=f"activation-channel-{uuid4()}",
                    name="Activation source",
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                )
                .returning(Channel)
            )
        ).scalar_one()
    )
    video = (
        await session.execute(
            insert(Video)
            .values(
                youtube_video_id=f"activation-video-{uuid4()}",
                channel_id=channel.id,
                title="Dental workflow evidence",
                published_at=NOW,
                first_seen_at=NOW,
                last_seen_at=NOW,
                processing_status="queued",
            )
            .returning(Video)
        )
    ).scalar_one()
    signal = (
        await session.execute(
            insert(Signal)
            .values(
                source_type="video",
                source_id=video.id,
                video_id=video.id,
                signal_type="pain",
                statement="Dental teams miss inbound appointments",
                claim_status="creator_claim",
                confidence="0.8",
                observed_at=NOW,
                status="active",
            )
            .returning(Signal)
        )
    ).scalar_one()
    await session.execute(
        insert(OpportunitySignalLink).values(
            opportunity_id=opportunity_id,
            signal_id=signal.id,
            relationship_type="supporting",
            confidence="0.8",
        )
    )
    return signal


@pytest.mark.asyncio
async def test_readiness_checks_are_deterministic_and_scores_are_advisory(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        empty = await opportunity(
            session, name="AI", customer_type=None, problem=None, solution=None
        )
        strong = await opportunity(session)
        await supporting_signal(session, strong.id)
        await supporting_signal(session, strong.id)
        session.add(
            OpportunityScore(
                opportunity_id=strong.id,
                calculated_at=NOW,
                scoring_version="score-v001",
                input_hash=uuid4().hex,
                trend_velocity_score=1,
                demand_evidence_score=1,
                revenue_evidence_score=1,
                pain_severity_score=1,
                competition_white_space_score=1,
                build_feasibility_score=1,
                distribution_ease_score=1,
                opportunity_score=1,
                confidence_score=1,
                hype_risk_score=99,
                inputs_snapshot={},
                created_at=NOW,
            )
        )
    service = OpportunityActivationReadinessService(factory)
    empty_result = await service.assess(empty.id)
    strong_result = await service.assess(strong.id)
    await engine.dispose()

    assert empty_result.overall == "not_ready"
    assert empty_result.checks["supporting_evidence"].status == "fail"
    assert empty_result.checks["scope_clear"].status == "fail"
    assert empty_result.checks["commercial_definition"].status == "fail"
    assert strong_result.checks["supporting_evidence"].status == "pass"
    assert strong_result.checks["commercial_definition"].supporting_metrics["populated_fields"] == 3
    assert strong_result.checks["source_diversity"].status == "pass"
    assert strong_result.checks["contradiction_quality"].status == "warning"
    assert strong_result.recommendation == "publish"
    assert strong_result.metrics.latest_score == 1


@pytest.mark.asyncio
async def test_duplicate_and_one_source_are_safely_advisory_or_blocking(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        candidate = await opportunity(session, name="Dental Appointment AI Receptionist")
        await supporting_signal(session, candidate.id)
        await opportunity(session, name="Dental Appointment AI Receptionist", status="active")
    result = await OpportunityActivationReadinessService(factory).assess(candidate.id)
    await engine.dispose()

    assert result.checks["source_diversity"].status == "warning"
    assert result.checks["duplicate_risk"].status == "fail"
    assert result.recommendation == "invalid_review"


@pytest.mark.asyncio
async def test_activation_review_lifecycle_revalidates_and_preserves_history(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        admin = (
            await session.execute(
                insert(UserProfile)
                .values(auth_user_id=uuid4(), role="admin")
                .returning(UserProfile.id)
            )
        ).scalar_one()
        publishable = await opportunity(
            session,
            name="Veterinary Voice Scheduling",
            customer_type="Veterinary clinics",
            problem="Missed veterinary calls",
            solution="Voice scheduling agent",
        )
        evidence = await supporting_signal(session, publishable.id)
        session.add(
            OpportunityScore(
                opportunity_id=publishable.id,
                calculated_at=NOW,
                scoring_version="score-v001",
                input_hash=uuid4().hex,
                trend_velocity_score=50,
                demand_evidence_score=50,
                revenue_evidence_score=50,
                pain_severity_score=50,
                competition_white_space_score=50,
                build_feasibility_score=50,
                distribution_ease_score=50,
                opportunity_score=42,
                confidence_score=68,
                hype_risk_score=31,
                inputs_snapshot={},
                created_at=NOW,
            )
        )
        deferred_candidate = await opportunity(
            session,
            name="Legal Intake Workflow",
            customer_type="Law firms",
            problem="Slow legal intake",
            solution="Structured intake assistant",
        )
        await supporting_signal(session, deferred_candidate.id)
        invalid_candidate = await opportunity(
            session,
            name="Retail Inventory Forecasting",
            customer_type="Retailers",
            problem="Inventory uncertainty",
            solution="Forecasting dashboard",
        )
        await supporting_signal(session, invalid_candidate.id)

    trigger = TranslationTriggerStub()
    activation = OpportunityActivationReadinessService(factory, trigger)
    created = await activation.create_review(publishable.id)
    reused = await activation.create_review(publishable.id)
    deferred = await activation.create_review(deferred_candidate.id)
    invalid = await activation.create_review(invalid_candidate.id)
    assert created.created and not reused.created
    assert created.review_task_id == reused.review_task_id

    workflow = ReviewWorkflowService(factory, trigger)
    await workflow.claim_task(deferred.review_task_id, admin)
    deferred_result = await workflow.decide(
        deferred.review_task_id,
        admin,
        ReviewDecisionRequest(decision="defer", decision_notes="Need another source"),
    )
    await workflow.claim_task(invalid.review_task_id, admin)
    invalid_result = await workflow.decide(
        invalid.review_task_id,
        admin,
        ReviewDecisionRequest(decision="reject", decision_notes="Malformed standalone entity"),
    )
    await workflow.claim_task(created.review_task_id, admin)
    with pytest.raises(InvalidReviewDecision):
        await workflow.decide(
            created.review_task_id, admin, ReviewDecisionRequest(decision="ignore")
        )
    published = await workflow.decide(
        created.review_task_id,
        admin,
        ReviewDecisionRequest(decision="approve", decision_notes="Checklist reviewed"),
    )
    with pytest.raises(OpportunityActivationNotEligible):
        await activation.create_review(publishable.id)
    radar = await RadarQueryService(factory).radar(admin, RadarRequest())

    async with factory() as session:
        published_row = await session.get(Opportunity, publishable.id)
        deferred_row = await session.get(Opportunity, deferred_candidate.id)
        invalid_row = await session.get(Opportunity, invalid_candidate.id)
        publish_task = await session.get(ReviewTask, created.review_task_id)
        evidence_row = await session.get(Signal, evidence.id)
    await engine.dispose()

    assert deferred_result.status == "pending" and deferred_row.status == "candidate"
    assert invalid_result.status == "resolved" and invalid_row.status == "rejected"
    assert published.side_effects["opportunity_status"] == "active"
    assert published_row.status == "active"
    assert [item.id for item in radar.items] == [publishable.id]
    assert publish_task.resolved_by == admin and publish_task.decision_notes == "Checklist reviewed"
    assert evidence_row.status == "active"
    assert ("opportunity", publishable.id, "activation_review") in trigger.calls
    assert ("opportunity", publishable.id, "opportunity_active") in trigger.calls


@pytest.mark.asyncio
async def test_publish_rejects_stale_missing_evidence(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        admin = (
            await session.execute(
                insert(UserProfile)
                .values(auth_user_id=uuid4(), role="admin")
                .returning(UserProfile.id)
            )
        ).scalar_one()
        candidate = await opportunity(session, name="Dental Call Intake Assistant")
        signal = await supporting_signal(session, candidate.id)
    activation = OpportunityActivationReadinessService(factory)
    review = await activation.create_review(candidate.id)
    async with factory() as session, session.begin():
        stale_signal = await session.get(Signal, signal.id)
        stale_signal.status = "rejected"
    with pytest.raises(ReviewTaskConflict):
        await ReviewWorkflowService(factory).decide(
            review.review_task_id, admin, ReviewDecisionRequest(decision="approve")
        )
    async with factory() as session:
        candidate_row = await session.get(Opportunity, candidate.id)
        task = await session.get(ReviewTask, review.review_task_id)
    await engine.dispose()
    assert candidate_row.status == "candidate"
    assert task.status == "pending" and task.resolved_by is None


@pytest.mark.asyncio
async def test_non_candidates_and_candidates_without_evidence_get_no_review(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        active = await opportunity(session, status="active")
        empty = await opportunity(session, name="Dental Scheduling Assistant")
    service = OpportunityActivationReadinessService(factory)
    with pytest.raises(OpportunityActivationNotEligible):
        await service.create_review(active.id)
    with pytest.raises(OpportunityActivationNotEligible):
        await service.create_review(empty.id)
    await engine.dispose()
