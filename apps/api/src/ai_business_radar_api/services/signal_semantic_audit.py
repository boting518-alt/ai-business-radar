"""Bounded transactional semantic repair, shared by the operator CLI and integration tests."""

from sqlalchemy import select

from ..infrastructure.database.models import OpportunitySignalLink, Signal
from .signal_semantics import RISK_TYPES, evaluate_signal, exact_current_duplicate, persist_decision


async def audit(sessions, *, limit=100, apply=False, signal_ids=None):
    report = dict(
        scanned=0,
        accepted=0,
        flagged_review=0,
        invalid_semantic=0,
        supersession_candidates=0,
        score_impact_candidates=[],
        changes=[],
        applied=apply,
    )
    impacts = set()
    async with sessions() as session, session.begin():
        query = (
            select(Signal)
            .where(Signal.status == "active", Signal.signal_type.in_(RISK_TYPES))
            .order_by(Signal.created_at, Signal.id)
            .limit(limit)
        )
        if signal_ids is not None:
            query = query.where(Signal.id.in_(signal_ids))
        if apply:
            query = query.with_for_update()
        for signal in await session.scalars(query):
            report["scanned"] += 1
            if (
                signal.semantic_status != "current"
                or signal.guardrail_reason_code == "human_semantic_approval"
            ):
                continue
            decision = evaluate_signal(signal)
            duplicate = (
                await exact_current_duplicate(session, signal)
                if decision.decision == "accept"
                else None
            )
            report[
                {
                    "accept": "accepted",
                    "review": "flagged_review",
                    "reject_semantic": "invalid_semantic",
                }[decision.decision]
            ] += 1
            report["supersession_candidates"] += bool(duplicate)
            status = "superseded" if duplicate else decision.semantic_status
            row = dict(
                signal_id=str(signal.id),
                statement=signal.statement,
                signal_type=signal.signal_type,
                before=signal.semantic_status,
                after=status,
                decision=decision.decision,
                reason="duplicate_current_evidence" if duplicate else decision.reason,
                actor_role=decision.actor_role,
                evidence_role=decision.evidence_role,
                superseded_by=str(duplicate.id) if duplicate else None,
            )
            if status != "current":
                impacts.update(
                    await session.scalars(
                        select(OpportunitySignalLink.opportunity_id).where(
                            OpportunitySignalLink.signal_id == signal.id
                        )
                    )
                )
            if apply:
                row["changed"] = await persist_decision(
                    session,
                    signal,
                    decision,
                    duplicate=duplicate,
                    operator_note="bounded historical semantic audit",
                )
            report["changes"].append(row)
    report["score_impact_candidates"] = sorted(map(str, impacts))
    return report
