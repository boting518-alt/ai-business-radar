import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.database.models import (
    ActivationReviewEvent,
    Comment,
    Opportunity,
    OpportunitySignalLink,
    Signal,
    Video,
)
from ..infrastructure.database.repositories import ReviewTaskRepository
from .translation_orchestration import TranslationCoverageReconciliationService

GENERIC_NAMES = {
    "ai",
    "healthcare ai",
    "automation",
    "customer complaints",
    "artificial intelligence",
}
CHECK_NAMES = (
    "supporting_evidence",
    "scope_clear",
    "commercial_definition",
    "duplicate_risk",
    "source_diversity",
    "contradiction_quality",
)


class OpportunityActivationNotFound(RuntimeError):
    pass


class OpportunityActivationNotEligible(ValueError):
    pass


class ReadinessCheck(BaseModel):
    status: Literal["pass", "warning", "fail"]
    message: str
    supporting_metrics: dict[str, Any]


class ActivationMetrics(BaseModel):
    active_signal_count: int
    distinct_video_count: int
    distinct_channel_count: int
    latest_score: Decimal | None
    confidence_score: Decimal | None
    hype_risk: Decimal | None
    momentum_7d: Decimal | None
    first_detected_at: datetime
    last_activity_at: datetime


class DuplicateCandidate(BaseModel):
    opportunity_id: UUID
    name: str
    status: str
    overlap: float


class OpportunityActivationReadiness(BaseModel):
    opportunity_id: UUID
    checks: dict[str, ReadinessCheck]
    overall: Literal["ready", "needs_review", "not_ready"]
    recommendation: Literal["publish", "defer", "invalid_review"]
    metrics: ActivationMetrics
    duplicate_candidates: list[DuplicateCandidate]


class ActivationReviewResult(BaseModel):
    review_task_id: UUID
    created: bool
    readiness: OpportunityActivationReadiness


class OpportunityActivationReadinessService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        translation_orchestrator: TranslationCoverageReconciliationService | None = None,
    ) -> None:
        self._sessions = session_factory
        self._translation = translation_orchestrator

    async def assess(self, opportunity_id: UUID) -> OpportunityActivationReadiness:
        async with self._sessions() as session:
            opportunity = await session.get(Opportunity, opportunity_id)
            if opportunity is None:
                raise OpportunityActivationNotFound("Opportunity was not found")
            return await self.assess_in_session(session, opportunity)

    async def assess_in_session(
        self, session: AsyncSession, opportunity: Opportunity
    ) -> OpportunityActivationReadiness:
        return (await self.assess_many(session, [opportunity]))[opportunity.id]

    async def assess_many(self, session, opportunities):
        """Fixed-query batch; the same checks also run under the publication lock."""
        from ..infrastructure.database.repositories.radar_queries import RadarQueryRepository

        ids = [item.id for item in opportunities]
        if not ids:
            return {}
        rows = (
            await session.execute(
                select(
                    OpportunitySignalLink.opportunity_id,
                    OpportunitySignalLink.relationship_type,
                    Signal.status,
                    Signal.semantic_status,
                    Signal.id,
                    Signal.video_id,
                    Comment.video_id,
                    Video.channel_id,
                )
                .join(Signal, Signal.id == OpportunitySignalLink.signal_id)
                .outerjoin(Comment, Signal.comment_id == Comment.id)
                .outerjoin(Video, Video.id == func.coalesce(Signal.video_id, Comment.video_id))
                .where(OpportunitySignalLink.opportunity_id.in_(ids))
            )
        ).all()
        grouped = {identity: [] for identity in ids}
        for row in rows:
            grouped[row[0]].append(row)
        repo = RadarQueryRepository(session)
        scores = await repo.latest_scores(ids)
        trends = await repo.latest_trends(ids, "7d")
        pool = list(
            await session.scalars(
                select(Opportunity)
                .where(Opportunity.status.in_(("candidate", "active", "review")))
                .order_by(Opportunity.last_activity_at.desc(), Opportunity.id)
            )
        )
        result = {}
        for opportunity in opportunities:
            linked = grouped[opportunity.id]
            supporting = [
                r for r in linked if r[1] == "supporting" and r[2] == "active" and r[3] == "current"
            ]
            result[opportunity.id] = self._compose(
                opportunity,
                supporting,
                sum(
                    r[1] == "contradicting" and r[2] == "active" and r[3] == "current"
                    for r in linked
                ),
                sum(
                    (r[2] == "review" and r[3] == "current")
                    or (r[2] in {"active", "review"} and r[3] == "under_review")
                    for r in linked
                ),
                self._duplicate_pool(opportunity, pool),
                scores.get(opportunity.id),
                trends.get(opportunity.id),
            )
        return result

    def _compose(
        self,
        opportunity,
        source_rows,
        contradicting_count,
        unresolved_review_count,
        duplicate_candidates,
        score,
        trend,
    ):
        active_signal_count = len(source_rows)
        video_ids = {row[5] or row[6] for row in source_rows if row[5] or row[6]}
        channel_ids = {row[7] for row in source_rows if row[7]}
        commercial_count = sum(
            bool(value and value.strip())
            for value in (opportunity.customer_type, opportunity.problem, opportunity.solution)
        )
        exact_duplicate = any(item.overlap == 1 for item in duplicate_candidates)
        near_duplicate = bool(duplicate_candidates)
        scope_status, scope_message = self._scope(opportunity)
        checks = {
            "supporting_evidence": ReadinessCheck(
                status="pass" if active_signal_count else "fail",
                message="Active supporting evidence exists."
                if active_signal_count
                else "No active supporting signal exists.",
                supporting_metrics={"active_signal_count": active_signal_count},
            ),
            "scope_clear": ReadinessCheck(
                status=scope_status,
                message=scope_message,
                supporting_metrics={"name": opportunity.name},
            ),
            "commercial_definition": ReadinessCheck(
                status="pass" if commercial_count >= 2 else "fail",
                message=f"{commercial_count} of customer, problem, and solution are populated.",
                supporting_metrics={"populated_fields": commercial_count, "required": 2},
            ),
            "duplicate_risk": ReadinessCheck(
                status="fail" if exact_duplicate else "warning" if near_duplicate else "pass",
                message="An obvious duplicate opportunity exists."
                if exact_duplicate
                else "A possible near duplicate needs human review."
                if near_duplicate
                else "No strong lexical duplicate was found.",
                supporting_metrics={"candidate_count": len(duplicate_candidates)},
            ),
            "source_diversity": ReadinessCheck(
                status="pass" if len(video_ids) >= 2 or len(channel_ids) >= 2 else "warning",
                message="Evidence spans multiple source videos or channels."
                if len(video_ids) >= 2 or len(channel_ids) >= 2
                else "Evidence comes from fewer than two videos and channels.",
                supporting_metrics={
                    "distinct_video_count": len(video_ids),
                    "distinct_channel_count": len(channel_ids),
                },
            ),
            "contradiction_quality": ReadinessCheck(
                status="warning" if contradicting_count or unresolved_review_count else "warning",
                message="Contradicting or unresolved linked signals require review."
                if contradicting_count or unresolved_review_count
                else (
                    "No contradiction is recorded; automated contradiction coverage is incomplete."
                ),
                supporting_metrics={
                    "contradicting_active_signals": contradicting_count,
                    "unresolved_review_signals": unresolved_review_count,
                },
            ),
        }
        hard_failure = opportunity.status != "candidate" or any(
            checks[name].status == "fail"
            for name in (
                "supporting_evidence",
                "scope_clear",
                "commercial_definition",
                "duplicate_risk",
            )
        )
        pass_count = sum(item.status == "pass" for item in checks.values())
        invalid_scope = scope_status == "fail"
        recommendation = (
            "invalid_review"
            if invalid_scope or exact_duplicate
            else "defer"
            if hard_failure or pass_count < 4
            else "publish"
        )
        overall = (
            "not_ready"
            if hard_failure
            else "ready"
            if recommendation == "publish"
            else "needs_review"
        )
        return OpportunityActivationReadiness(
            opportunity_id=opportunity.id,
            checks=checks,
            overall=overall,
            recommendation=recommendation,
            metrics=ActivationMetrics(
                active_signal_count=active_signal_count,
                distinct_video_count=len(video_ids),
                distinct_channel_count=len(channel_ids),
                latest_score=score.opportunity_score if score else None,
                confidence_score=score.confidence_score if score else None,
                hype_risk=score.hype_risk_score if score else None,
                momentum_7d=trend.momentum_score if trend else None,
                first_detected_at=opportunity.first_detected_at,
                last_activity_at=opportunity.last_activity_at,
            ),
            duplicate_candidates=duplicate_candidates,
        )

    async def create_review(
        self, opportunity_id: UUID, actor_id: UUID | None = None
    ) -> ActivationReviewResult:
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            opportunity = await session.scalar(
                select(Opportunity).where(Opportunity.id == opportunity_id).with_for_update()
            )
            if opportunity is None:
                raise OpportunityActivationNotFound("Opportunity was not found")
            if opportunity.status != "candidate":
                raise OpportunityActivationNotEligible("Only candidate opportunities are eligible")
            readiness = await self.assess_in_session(session, opportunity)
            if readiness.metrics.active_signal_count < 1:
                raise OpportunityActivationNotEligible("Active supporting evidence is required")
            existing = await ReviewTaskRepository(session).find_open_for_target(
                target_type="opportunity",
                target_id=opportunity.id,
                review_type="opportunity_activation",
            )
            if existing:
                result = ActivationReviewResult(
                    review_task_id=existing.id, created=False, readiness=readiness
                )
            else:
                task = await ReviewTaskRepository(session).create_review_task(
                    review_type="opportunity_activation",
                    target_type="opportunity",
                    target_id=opportunity.id,
                    status="pending",
                    priority=Decimal(
                        sum(item.status == "pass" for item in readiness.checks.values())
                    )
                    / Decimal(6),
                    context={
                        "readiness": readiness.model_dump(mode="json"),
                        "recommendation": readiness.recommendation,
                        "metrics": readiness.metrics.model_dump(mode="json"),
                        "duplicate_candidates": [
                            item.model_dump(mode="json") for item in readiness.duplicate_candidates
                        ],
                    },
                    created_at=now,
                    updated_at=now,
                )
                session.add(
                    ActivationReviewEvent(
                        review_task_id=task.id,
                        opportunity_id=opportunity.id,
                        actor_id=actor_id,
                        event_type="submitted",
                        previous_status=None,
                        status="pending",
                        notes=None,
                        created_at=now,
                    )
                )
                result = ActivationReviewResult(
                    review_task_id=task.id, created=True, readiness=readiness
                )
        if self._translation is not None:
            await self._translation.best_effort_enqueue(
                "opportunity", opportunity_id, reason="activation_review"
            )
        return result

    @staticmethod
    def _scope(opportunity: Opportunity) -> tuple[Literal["pass", "warning", "fail"], str]:
        normalized = " ".join((opportunity.name or "").lower().split())
        words = re.findall(r"[\w-]+", normalized)
        if not normalized or normalized in GENERIC_NAMES or len(words) < 2:
            return "fail", "Opportunity name is empty or obviously generic."
        if not any((opportunity.one_line_thesis, opportunity.problem, opportunity.solution)):
            return "warning", "Name is specific, but no thesis, problem, or solution is available."
        return "pass", "Opportunity scope is specific and supported by descriptive fields."

    def _duplicate_pool(self, opportunity, pool):
        terms = self._terms(opportunity)
        # Same recent-first lexical candidate cap as OpportunityRepository.
        fields = ("name", "one_line_thesis", "industry", "customer_type", "problem", "solution")
        pool = [
            item
            for item in pool
            if not terms
            or any(
                term in (getattr(item, field) or "").lower() for term in terms for field in fields
            )
        ][:20]
        result = []
        normalized_name = " ".join(opportunity.name.lower().split())
        for item in pool:
            if item.id == opportunity.id or item.status in {"merged", "rejected"}:
                continue
            item_terms = self._terms(item)
            overlap = len(set(terms) & set(item_terms)) / max(1, len(set(terms) | set(item_terms)))
            exact = " ".join(item.name.lower().split()) == normalized_name
            if exact or overlap >= 0.6:
                result.append(
                    DuplicateCandidate(
                        opportunity_id=item.id,
                        name=item.name,
                        status=item.status,
                        overlap=1 if exact else round(overlap, 2),
                    )
                )
        return sorted(result, key=lambda item: (-item.overlap, item.name))[:5]

    @staticmethod
    def _terms(opportunity: Opportunity) -> list[str]:
        text = " ".join(
            filter(
                None,
                (
                    opportunity.name,
                    opportunity.industry,
                    opportunity.customer_type,
                    opportunity.problem,
                    opportunity.solution,
                ),
            )
        ).lower()
        return sorted({word for word in re.findall(r"[\w-]{3,}", text) if not word.isdigit()})[:30]
