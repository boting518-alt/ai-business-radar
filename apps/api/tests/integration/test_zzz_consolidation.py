import asyncio
from uuid import UUID, uuid4

import pytest
from ai_business_radar_schemas.consolidation import OpportunityConsolidationOutput
from sqlalchemy import event, insert, select, text

from ai_business_radar_api.infrastructure.ai.client import AIResponse
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    Opportunity,
    OpportunityConsolidation,
    OpportunityRevision,
    Signal,
    UserProfile,
)
from ai_business_radar_api.services.candidate_workspace import CandidateConflict, CandidateNotFound
from ai_business_radar_api.services.opportunity_consolidation import (
    AcceptProposal,
    OpportunityConsolidationService,
)
from test_consolidation import supported, unknown_output

from .test_z_opportunity_activation import opportunity, supporting_signal


class FakeAI:
    calls = 0
    fail = False

    async def structured_generate(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("do not persist provider secrets")
        result = unknown_output()
        identity = kwargs["input_data"]["signals"][0]["id"]
        result["build_complexity_summary"] = {
            "text": "Hypothetical build challenge",
            "evidence_signal_ids": [],
            "information_class": "hypothesis",
            "support_level": "hypothesis",
            "uncertainty": "Needs technical validation",
        }
        result["solution_pattern"] = supported(identity, "A source-grounded scheduling workflow")
        return AIResponse(
            provider="fake",
            model="test",
            parsed=OpportunityConsolidationOutput.model_validate(result),
            raw_output={"test": True},
        )


@pytest.mark.asyncio
async def test_versioned_case_lifecycle_reference_visibility_and_human_precedence(postgres_url):
    engine = create_database_engine(postgres_url)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        auth = uuid4()
        admin = (
            await session.execute(
                insert(UserProfile)
                .values(auth_user_id=auth, role="admin")
                .returning(UserProfile.id)
            )
        ).scalar_one()
        reader_auth = uuid4()
        await session.execute(insert(UserProfile).values(auth_user_id=reader_auth, role="user"))
        chosen = await opportunity(
            session, name="Case local test " + uuid4().hex, solution="Human original"
        )
        good = await supporting_signal(session, chosen.id)
        for semantic, status in [
            ("invalid_semantic", "active"),
            ("superseded", "active"),
            ("under_review", "active"),
            ("current", "ignored"),
            ("current", "rejected"),
        ]:
            bad = await supporting_signal(session, chosen.id)
            bad.semantic_status, bad.status = semantic, status
            if semantic == "superseded":
                bad.superseded_by = good.id
    service = OpportunityConsolidationService(factory)
    before = await service.current(chosen.id)
    assert before["state"] == "missing"
    assert before["source_diversity"]["signal_count"] == 1
    with pytest.raises(CandidateNotFound):
        await service.current(chosen.id, public=True)
    requests = await asyncio.gather(
        service.request(chosen.id, admin), service.request(chosen.id, admin)
    )
    assert requests[0]["id"] == requests[1]["id"]
    case_id = UUID(requests[0]["id"])
    ai = FakeAI()
    results = await asyncio.gather(
        service.execute(case_id, ai, provider="fake", model="test"),
        service.execute(case_id, ai, provider="fake", model="test"),
    )
    assert ai.calls == 1
    assert any(r["status"] == "completed" for r in results)
    current = await service.current(chosen.id)
    assert current["state"] == "current"
    assert current["case"]["parsed_output"]["pricing_summary"]["text"] is None
    assert (await service.request(chosen.id))["id"] == str(case_id)
    assert ai.calls == 1
    async with factory() as session:
        original = await session.get(Opportunity, chosen.id)
        assert original.solution == "Human original"
        snapshot = (await session.get(OpportunityConsolidation, case_id)).input_snapshot
        assert [s["id"] for s in snapshot["signals"]] == [str(good.id)]
    await service.accept(
        chosen.id,
        case_id,
        admin,
        AcceptProposal(
            dimension="solution_pattern",
            expected_updated_at=original.updated_at,
            note="Verify fixture",
            edited_text="Human accepted workflow",
        ),
    )
    assert (await service.current(chosen.id))["state"] == "stale"
    async with factory() as session:
        edited = await session.get(Opportunity, chosen.id)
        assert edited.solution == "Human accepted workflow" and edited.status == "candidate"
        revision = await session.scalar(
            select(OpportunityRevision).where(OpportunityRevision.opportunity_id == chosen.id)
        )
        assert (
            revision.old_value == "Human original" and revision.source_consolidation_id == case_id
        )
        assert (await session.get(OpportunityConsolidation, case_id)).parsed_output == current[
            "case"
        ]["parsed_output"]
    with pytest.raises(CandidateConflict):
        await service.approve(chosen.id, case_id, admin)
    newer = await service.request(chosen.id)
    assert newer["id"] != str(case_id)
    ai.fail = True
    failed = await service.execute(UUID(newer["id"]), ai, provider="fake", model="test")
    assert failed["status"] == "failed"
    after = await service.current(chosen.id)
    assert after["case"]["id"] == str(case_id) and after["state"] == "stale"
    assert after["latest_attempt"]["error_code"] == "provider_failed"
    ai.fail = False
    retry = await service.request(chosen.id)
    await service.execute(UUID(retry["id"]), ai, provider="fake", model="test")
    await service.approve(chosen.id, UUID(retry["id"]), admin)
    with pytest.raises(CandidateNotFound):
        await service.current(chosen.id, public=True)
    async with factory() as session, session.begin():
        (await session.get(Opportunity, chosen.id)).status = "active"
    public = await service.current(chosen.id, public=True)
    assert public["state"] == "current" and "history" not in public
    assert public["case"]["parsed_output"]["build_complexity_summary"]["text"] is None
    assert "input_snapshot" not in public["case"] and "provider" not in public["case"]
    async with factory() as session, session.begin():
        (await session.get(Signal, good.id)).semantic_status = "invalid_semantic"
    assert (await service.current(chosen.id, public=True))["case"] is None
    # Raw case/audit table remains admin-only even for active opportunities.
    async with factory() as session, session.begin():
        await session.execute(text("SET LOCAL ROLE authenticated"))
        await session.execute(
            text("SELECT set_config('request.jwt.claim.sub', :sub, true)"),
            {"sub": str(reader_auth)},
        )
        assert not list(await session.scalars(select(OpportunityConsolidation)))
    async with factory() as session, session.begin():
        await session.execute(text("SET LOCAL ROLE authenticated"))
        await session.execute(
            text("SELECT set_config('request.jwt.claim.sub', :sub, true)"), {"sub": str(auth)}
        )
        assert await session.get(OpportunityConsolidation, case_id)
    # Completed output is immutable even through application credentials.
    with pytest.raises(Exception, match="immutable"):
        async with factory() as session, session.begin():
            (await session.get(OpportunityConsolidation, case_id)).parsed_output = {
                "tampered": True
            }
    # Fixed joined evidence reads, not one query per Signal.
    statements = []

    def count(*args):
        statements.append(args[2])

    event.listen(engine.sync_engine, "before_cursor_execute", count)
    await service.current(chosen.id)
    assert len(statements) == 4
    event.remove(engine.sync_engine, "before_cursor_execute", count)
    await engine.dispose()
