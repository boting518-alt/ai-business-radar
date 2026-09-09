import asyncio
from uuid import uuid4

import pytest
from ai_business_radar_schemas import ReviewDecisionRequest
from sqlalchemy import event, insert, select, text

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    ActivationReviewEvent,
    Opportunity,
    OpportunityRevision,
    OpportunityTaxonomyMapping,
    Signal,
    UserProfile,
)
from ai_business_radar_api.services.candidate_workspace import (
    CandidateConflict,
    CandidateEdit,
    CandidateFilters,
    CandidateWorkspaceService,
)
from ai_business_radar_api.services.opportunity_activation import (
    OpportunityActivationReadinessService,
)
from ai_business_radar_api.services.radar_query import OpportunityNotVisibleError, RadarQueryService
from ai_business_radar_api.services.review_workflow import ReviewTaskConflict, ReviewWorkflowService

from .test_z_opportunity_activation import opportunity, supporting_signal


@pytest.mark.asyncio
async def test_candidate_curation_visibility_audit_and_concurrency(postgres_url):
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
        reader_auth = uuid4()
        reader = (
            await session.execute(
                insert(UserProfile)
                .values(auth_user_id=reader_auth, role="user")
                .returning(UserProfile.id)
            )
        ).scalar_one()
        candidates = []
        for index in range(23):
            candidates.append(
                await opportunity(
                    session,
                    name=f"Workspace fixture {index} {uuid4().hex}",
                    customer_type="Orbital laboratories",
                    problem="Sample tracking",
                    solution="Tracking agent",
                )
            )
        active = await opportunity(session, name="Workspace already active", status="active")
        invalid = await opportunity(session, name="Workspace already invalid", status="rejected")
        chosen = candidates[0]
        good = await supporting_signal(session, chosen.id)
        bad = await supporting_signal(session, chosen.id)
        bad.semantic_status = "invalid_semantic"
        bad.status = "review"
        uncertain = await supporting_signal(session, chosen.id)
        uncertain.semantic_status = "under_review"
        await session.flush()
        await session.execute(
            insert(OpportunityTaxonomyMapping).values(
                opportunity_id=chosen.id,
                taxonomy_type="industry",
                taxonomy_code="healthcare",
                mapping_source="manual",
                mapping_status="active",
            )
        )
    workspace = CandidateWorkspaceService(factory)
    activation = OpportunityActivationReadinessService(factory)
    workflow = ReviewWorkflowService(factory)
    public = RadarQueryService(factory)
    statements = []

    def count(*args):
        statements.append(args[2])

    event.listen(engine.sync_engine, "before_cursor_execute", count)
    page = await workspace.list(CandidateFilters(q="Workspace fixture", limit=1))
    one_count = len(statements)
    statements.clear()
    all_page = await workspace.list(CandidateFilters(q="Workspace fixture", limit=100))
    assert len(statements) == one_count < 15
    event.remove(engine.sync_engine, "before_cursor_execute", count)
    assert page.total == 23 and len(page.items) == 1 and page.has_more
    assert len(all_page.items) == 23
    assert active.id not in {i.id for i in all_page.items}
    assert invalid.id not in {i.id for i in all_page.items}
    second = await workspace.list(CandidateFilters(q="Workspace fixture", offset=20))
    assert len(second.items) == 3 and not second.has_more
    filtered = await workspace.list(
        CandidateFilters(
            q="Workspace fixture", has_semantic_warnings=True, industry_code="healthcare"
        )
    )
    assert [i.id for i in filtered.items] == [chosen.id]
    detail = await workspace.detail(chosen.id)
    assert detail.summary.evidence_summary.active_signal_count == 1
    assert detail.summary.evidence_summary.supporting_signal_count == 1
    assert detail.summary.semantic_warning_count == 2
    readiness = await activation.assess(chosen.id)
    assert readiness == detail.summary.readiness
    assert (
        readiness.checks["contradiction_quality"].supporting_metrics["unresolved_review_signals"]
        == 1
    )
    valid = await workspace.evidence(chosen.id, 0, 20, "en-US")
    excluded = await workspace.evidence(chosen.id, 0, 20, "en-US", True)
    assert valid.total == 1 and valid.items[0].signal_id == good.id
    assert excluded.total == 2
    assert {i.semantic_status for i in excluded.items} == {"invalid_semantic", "under_review"}
    with pytest.raises(OpportunityNotVisibleError):
        await public.detail(reader, str(chosen.id))
    with pytest.raises(OpportunityNotVisibleError):
        await public.evidence(str(chosen.id), 0, 20)
    stamp = detail.opportunity["updated_at"]
    edited = await workspace.edit(
        chosen.id,
        admin,
        CandidateEdit(
            expected_updated_at=stamp,
            one_line_thesis="Track orbital sample custody",
            note="Clarify test definition",
        ),
    )
    assert edited.opportunity["status"] == "candidate" and edited.summary.activation_review is None
    assert edited.revisions[0]["old_value"] == chosen.one_line_thesis
    assert edited.revisions[0]["new_value"] == "Track orbital sample custody"
    with pytest.raises(CandidateConflict):
        await workspace.edit(
            chosen.id, admin, CandidateEdit(expected_updated_at=stamp, name="Stale editor")
        )
    with pytest.raises(CandidateConflict):
        await workspace.edit(
            chosen.id,
            admin,
            CandidateEdit(
                expected_updated_at=edited.opportunity["updated_at"],
                typical_price_min=200,
                typical_price_max=100,
            ),
        )
    assert len((await workspace.detail(chosen.id)).revisions) == 1
    submissions = await asyncio.gather(
        activation.create_review(chosen.id, admin), activation.create_review(chosen.id, admin)
    )
    assert sum(r.created for r in submissions) == 1
    assert submissions[0].review_task_id == submissions[1].review_task_id
    review_id = submissions[0].review_task_id
    for note in ("Need another source", "Still awaiting corroboration"):
        await workflow.claim_task(review_id, admin)
        await workflow.decide(
            review_id, admin, ReviewDecisionRequest(decision="defer", decision_notes=note)
        )
    deferred = await workspace.detail(chosen.id)
    assert deferred.summary.review_state == "deferred"
    assert {e["notes"] for e in deferred.review_history if e["event_type"] == "deferred"} == {
        "Need another source",
        "Still awaiting corroboration",
    }
    assert not (await activation.create_review(chosen.id, admin)).created
    await workflow.claim_task(review_id, admin)
    outcomes = await asyncio.gather(
        *(
            workflow.decide(
                review_id,
                admin,
                ReviewDecisionRequest(decision="approve", decision_notes="Fixture verified"),
            )
            for _ in range(2)
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(o, ReviewTaskConflict) for o in outcomes) == 1
    assert (await public.detail(reader, str(chosen.id))).opportunity.id == chosen.id
    assert (await public.evidence(str(chosen.id), 0, 20)).total == 1
    assert chosen.id not in {
        i.id
        for i in (await workspace.list(CandidateFilters(q="Workspace fixture", limit=100))).items
    }
    published = await workspace.detail(chosen.id)
    assert sum(e["event_type"] == "published" for e in published.review_history) == 1
    with pytest.raises(CandidateConflict):
        await workspace.edit(
            chosen.id,
            admin,
            CandidateEdit(
                expected_updated_at=published.opportunity["updated_at"], name="No public edits"
            ),
        )
    async with factory() as session, session.begin():
        await session.execute(text("SET LOCAL ROLE authenticated"))
        await session.execute(
            text("SELECT set_config('request.jwt.claim.sub', :id, true)"), {"id": str(reader_auth)}
        )
        assert not list(await session.scalars(select(OpportunityRevision)))
        assert not list(await session.scalars(select(ActivationReviewEvent)))
        assert await session.get(Opportunity, candidates[1].id) is None
        assert await session.get(Signal, bad.id) is None
    await engine.dispose()
