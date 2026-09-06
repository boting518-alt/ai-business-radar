import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ai_business_radar_schemas import ReviewDecisionRequest
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.database.models import (
    AIExtraction,
    Opportunity,
    OpportunityEvidence,
    OpportunityMergeHistory,
    OpportunitySignalLink,
    ReviewTask,
    Signal,
    WatchlistItem,
)
from ..infrastructure.database.repositories import OpportunityRepository, ReviewTaskRepository
from .opportunity_activation import OpportunityActivationReadinessService

DECISION_MATRIX = {
    "signal_validation": {"approve", "reject", "ignore", "defer"},
    "opportunity_match": {"approve", "merge", "create_new", "reject", "defer"},
    "opportunity_creation": {"approve", "create_new", "reject", "defer"},
    "opportunity_merge": {"merge", "reject", "defer"},
    "opportunity_activation": {"approve", "reject", "defer"},
    "hype_review": {"approve", "reject", "defer"},
    "quality_review": {"approve", "reject", "ignore", "defer"},
}


class ReviewTaskNotFound(RuntimeError):
    pass


class ReviewTaskConflict(RuntimeError):
    pass


class ReviewTaskAlreadyResolved(ReviewTaskConflict):
    pass


class InvalidReviewDecision(ValueError):
    pass


class ReviewAssignmentConflict(ReviewTaskConflict):
    pass


class ReviewTargetNotFound(RuntimeError):
    pass


class InvalidMergeTarget(ValueError):
    pass


class OpportunityMergeCycleError(InvalidMergeTarget):
    pass


class ReviewListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str | None = None
    review_type: str | None = None
    assigned_to: UUID | None = None
    priority: float | None = Field(default=None, ge=0)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=200)


class ReviewTaskResult(BaseModel):
    id: UUID
    review_type: str
    target_type: str
    target_id: UUID
    status: str
    priority: float
    assigned_to: UUID | None
    resolved_by: UUID | None
    decision: str | None
    decision_notes: str | None
    context: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class ReviewListResult(BaseModel):
    items: list[ReviewTaskResult]
    offset: int
    limit: int


class ReviewWorkflowResult(BaseModel):
    review_task_id: UUID
    review_type: str
    previous_status: str
    status: str
    decision: str | None
    target_type: str
    target_id: UUID
    assigned_to: UUID | None
    resolved_by: UUID | None
    resolved_at: datetime | None
    side_effects: dict[str, Any] = Field(default_factory=dict)


class ReviewWorkflowService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def list_tasks(self, request: ReviewListRequest) -> ReviewListResult:
        async with self._sessions() as session:
            rows = await ReviewTaskRepository(session).list_tasks(**request.model_dump())
        return ReviewListResult(
            items=[self._task_result(row) for row in rows],
            offset=request.offset,
            limit=request.limit,
        )

    async def get_task(self, task_id: UUID) -> ReviewTaskResult:
        async with self._sessions() as session:
            task = await ReviewTaskRepository(session).get_by_id(task_id)
            if task is None:
                raise ReviewTaskNotFound("Review task was not found")
            result = self._task_result(task)
            result.context = await self._presentation_context(session, task)
            return result

    async def _presentation_context(self, session, task) -> dict[str, Any]:
        """Project persisted IDs into safe, human-readable review detail."""
        stored = task.context if isinstance(task.context, dict) else {}
        context = {
            key: stored.get(key)
            for key in (
                "reason",
                "model_action",
                "proposed_opportunity_id",
                "readiness",
                "recommendation",
                "metrics",
                "duplicate_candidates",
            )
            if stored.get(key) is not None
        }
        if task.target_type == "signal":
            signal = await session.get(Signal, task.target_id)
            if signal is not None:
                context["signal"] = self._signal_context(signal)

        raw_candidate_ids = stored.get("candidate_ids")
        candidate_ids = [self._uuid(value) for value in raw_candidate_ids or []]
        candidate_ids = [value for value in candidate_ids if value is not None]
        canonical_id = next(
            (
                self._uuid(stored.get(key))
                for key in (
                    "canonical_opportunity_id",
                    "merge_target_opportunity_id",
                    "target_opportunity_id",
                )
                if self._uuid(stored.get(key)) is not None
            ),
            None,
        )
        opportunity_ids = set(candidate_ids)
        if task.target_type == "opportunity":
            opportunity_ids.add(task.target_id)
        if canonical_id is not None:
            opportunity_ids.add(canonical_id)
        opportunities = (
            list(
                await session.scalars(
                    select(Opportunity).where(Opportunity.id.in_(opportunity_ids))
                )
            )
            if opportunity_ids
            else []
        )
        by_id = {item.id: self._opportunity_context(item) for item in opportunities}
        if candidate_ids:
            context["candidates"] = [by_id[value] for value in candidate_ids if value in by_id]
        if task.target_type == "opportunity" and task.target_id in by_id:
            context["source_opportunity"] = by_id[task.target_id]
        if canonical_id is not None and canonical_id in by_id:
            context["canonical_opportunity"] = by_id[canonical_id]
        return context

    @staticmethod
    def _signal_context(signal) -> dict[str, Any]:
        return {
            key: getattr(signal, key)
            for key in (
                "id",
                "signal_type",
                "statement",
                "evidence_text",
                "claim_status",
                "confidence",
                "evidence_strength",
                "industry",
                "customer_type",
                "problem",
                "solution",
                "observed_at",
                "source_type",
            )
        }

    @staticmethod
    def _opportunity_context(opportunity) -> dict[str, Any]:
        return {
            key: getattr(opportunity, key)
            for key in (
                "id",
                "slug",
                "name",
                "one_line_thesis",
                "industry",
                "customer_type",
                "problem",
                "solution",
                "market_stage",
                "first_detected_at",
                "last_activity_at",
            )
        }

    async def claim_task(self, task_id: UUID, admin_user_id: UUID) -> ReviewWorkflowResult:
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            task = await ReviewTaskRepository(session).get_for_update(task_id)
            if task is None:
                raise ReviewTaskNotFound("Review task was not found")
            previous = task.status
            if task.status in {"resolved", "ignored"}:
                raise ReviewTaskAlreadyResolved("Resolved review tasks cannot be claimed")
            if task.status == "in_review":
                if task.assigned_to == admin_user_id:
                    return self._workflow_result(task, previous, {})
                raise ReviewAssignmentConflict("Review task is assigned to another administrator")
            task.status = "in_review"
            task.assigned_to = admin_user_id
            task.updated_at = now
            await session.flush()
            return self._workflow_result(task, previous, {})

    async def decide(
        self, task_id: UUID, admin_user_id: UUID, request: ReviewDecisionRequest
    ) -> ReviewWorkflowResult:
        now = datetime.now(UTC)
        decision = request.decision.value
        async with self._sessions() as session, session.begin():
            task = await ReviewTaskRepository(session).get_for_update(task_id)
            if task is None:
                raise ReviewTaskNotFound("Review task was not found")
            previous = task.status
            if task.status in {"resolved", "ignored"}:
                raise ReviewTaskAlreadyResolved("Review task is already resolved")
            if task.status == "in_review" and task.assigned_to != admin_user_id:
                raise ReviewAssignmentConflict("Review task is assigned to another administrator")
            if decision not in DECISION_MATRIX.get(task.review_type, set()):
                raise InvalidReviewDecision(
                    f"Decision {decision!r} is not valid for {task.review_type!r}"
                )
            await self._validate_target(session, task)
            if decision == "defer":
                task.status = "pending"
                task.assigned_to = None
                task.decision = decision
                task.decision_notes = request.decision_notes
                task.resolved_by = None
                task.resolved_at = None
                task.updated_at = now
                await session.flush()
                return self._workflow_result(task, previous, {})

            effects = await self._apply_decision(session, task, admin_user_id, request, now)
            task.status = "ignored" if decision == "ignore" else "resolved"
            if task.assigned_to is None:
                task.assigned_to = admin_user_id
            task.resolved_by = admin_user_id
            task.decision = decision
            task.decision_notes = request.decision_notes
            task.resolved_at = now
            task.updated_at = now
            await session.flush()
            return self._workflow_result(task, previous, effects)

    async def _validate_target(self, session: AsyncSession, task: ReviewTask) -> None:
        expected = {
            "signal_validation": "signal",
            "opportunity_match": "signal",
            "opportunity_creation": "signal",
            "opportunity_merge": "opportunity",
            "opportunity_activation": "opportunity",
        }.get(task.review_type)
        if expected is not None and task.target_type != expected:
            raise ReviewTargetNotFound("Review task target type is invalid")
        model = Signal if task.target_type == "signal" else Opportunity
        if await session.get(model, task.target_id) is None:
            raise ReviewTargetNotFound("Review target was not found")

    async def _apply_decision(self, session, task, admin_id, request, now):
        decision = request.decision.value
        if task.review_type == "signal_validation":
            status = {"approve": "active", "reject": "rejected", "ignore": "ignored"}[decision]
            await session.execute(
                update(Signal).where(Signal.id == task.target_id).values(status=status)
            )
            return {"signal_status": status}
        if task.review_type in {"opportunity_match", "opportunity_creation"}:
            if decision == "reject":
                return {"normalization_rejected": True, "signal_status": "review"}
            if decision == "merge":
                context = task.context if isinstance(task.context, dict) else {}
                source_id = self._uuid(context.get("source_opportunity_id"))
                if source_id is None:
                    raise InvalidMergeTarget("Persisted match context has no source opportunity")
                return await self._merge(
                    session,
                    source_id,
                    request.merge_target_opportunity_id,
                    admin_id,
                    request.decision_notes,
                    now,
                )
            return await self._match_or_create(session, task, decision, now)
        if task.review_type == "opportunity_merge" and decision == "merge":
            return await self._merge(
                session,
                task.target_id,
                request.merge_target_opportunity_id,
                admin_id,
                request.decision_notes,
                now,
            )
        if task.review_type == "opportunity_activation":
            return await self._activate(session, task, decision, now)
        # Hype/quality decisions are audit-only and never rewrite scores in v0.1.
        return {"review_only": True}

    async def _activate(self, session, task, decision, now):
        opportunity = await session.scalar(
            select(Opportunity).where(Opportunity.id == task.target_id).with_for_update()
        )
        if opportunity is None:
            raise ReviewTargetNotFound("Opportunity was not found")
        if opportunity.status != "candidate":
            raise ReviewTaskConflict("Opportunity is no longer an eligible candidate")
        if decision == "reject":
            opportunity.status = "rejected"
            opportunity.updated_at = now
            await session.flush()
            return {"opportunity_status": "rejected"}
        readiness = await OpportunityActivationReadinessService(self._sessions).assess_in_session(
            session, opportunity
        )
        hard_checks = (
            "supporting_evidence",
            "scope_clear",
            "commercial_definition",
            "duplicate_risk",
        )
        if any(readiness.checks[name].status == "fail" for name in hard_checks):
            raise ReviewTaskConflict("Activation readiness hard conditions are no longer satisfied")
        opportunity.status = "active"
        opportunity.updated_at = now
        await session.flush()
        return {
            "opportunity_status": "active",
            "readiness_revalidated": True,
            "recommendation": readiness.recommendation,
        }

    async def _match_or_create(self, session, task, decision, now):
        signal = await session.get(Signal, task.target_id)
        if signal is None:
            raise ReviewTargetNotFound("Signal was not found")
        context = task.context if isinstance(task.context, dict) else {}
        opportunity = None
        if decision == "approve" and task.review_type == "opportunity_match":
            opportunity_id = self._uuid(context.get("proposed_opportunity_id"))
            raw_candidates = context.get("candidate_ids")
            if not isinstance(raw_candidates, list):
                raw_candidates = []
            if opportunity_id is None or opportunity_id not in {
                self._uuid(value) for value in raw_candidates
            }:
                raise ReviewTargetNotFound("Persisted match target is invalid")
            opportunity = await session.get(Opportunity, opportunity_id)
            if opportunity is None or opportunity.status not in {"candidate", "active", "review"}:
                raise ReviewTargetNotFound("Persisted match target is not eligible")
        else:
            opportunity = await self._create_from_context(session, signal, context, now)
        await OpportunityRepository(session).link_signal(
            opportunity_id=opportunity.id,
            signal_id=signal.id,
            relationship_type="supporting",
            confidence=task.priority,
            created_at=now,
        )
        signal.status = "active"
        if (signal.observed_at or now) > opportunity.last_activity_at:
            opportunity.last_activity_at = signal.observed_at or now
            opportunity.updated_at = now
        await session.flush()
        return {"signal_status": "active", "opportunity_id": str(opportunity.id)}

    async def _create_from_context(self, session, signal, context, now):
        extraction_id = self._uuid(context.get("extraction_id"))
        extraction = await session.get(AIExtraction, extraction_id) if extraction_id else None
        parsed = (
            extraction.parsed_output
            if extraction and isinstance(extraction.parsed_output, dict)
            else {}
        )
        name = parsed.get("canonical_name")
        if not isinstance(name, str) or not name.strip():
            raise ReviewTargetNotFound("Persisted review context has no canonical creation name")
        slug = self._slugify(name)
        if await OpportunityRepository(session).get_by_slug(slug):
            raise ReviewTaskConflict("Persisted canonical slug already exists")
        return await OpportunityRepository(session).create_opportunity(
            slug=slug,
            name=name.strip(),
            one_line_thesis=signal.statement,
            industry=signal.industry,
            sub_industry=signal.sub_industry,
            customer_type=signal.customer_type,
            problem=signal.problem,
            solution=signal.solution,
            business_model=signal.business_model,
            primary_technology=(signal.technology or [None])[0],
            typical_price_min=signal.price_min,
            typical_price_max=signal.price_max,
            typical_price_currency=signal.price_currency,
            typical_price_period=signal.price_period,
            market_stage="unknown",
            competition_level=None,
            build_difficulty=None,
            sales_difficulty=None,
            status="candidate",
            first_detected_at=signal.observed_at or now,
            last_activity_at=signal.observed_at or now,
            created_at=now,
            updated_at=now,
        )

    async def _merge(self, session, source_id, canonical_id, admin_id, reason, now):
        if canonical_id is None or source_id == canonical_id:
            raise InvalidMergeTarget("Source and canonical opportunities must differ")
        locked = list(
            await session.scalars(
                select(Opportunity)
                .where(Opportunity.id.in_((source_id, canonical_id)))
                .order_by(Opportunity.id)
                .with_for_update()
            )
        )
        by_id = {item.id: item for item in locked}
        source, canonical = by_id.get(source_id), by_id.get(canonical_id)
        if source is None or canonical is None:
            raise ReviewTargetNotFound("Merge opportunity was not found")
        if source.status == "merged":
            raise InvalidMergeTarget("Source opportunity is already merged")
        if canonical.status in {"merged", "rejected", "archived"}:
            raise InvalidMergeTarget("Canonical opportunity is not eligible")
        if await self._creates_cycle(session, source_id, canonical_id):
            raise OpportunityMergeCycleError("Opportunity merge would create a cycle")

        history = OpportunityMergeHistory(
            source_opportunity_id=source_id,
            canonical_opportunity_id=canonical_id,
            merged_at=now,
            merged_by=admin_id,
            reason=reason,
            created_at=now,
        )
        session.add(history)
        source_links = list(
            await session.scalars(
                select(OpportunitySignalLink).where(
                    OpportunitySignalLink.opportunity_id == source_id
                )
            )
        )
        for link in source_links:
            await session.execute(
                insert(OpportunitySignalLink)
                .values(
                    opportunity_id=canonical_id,
                    signal_id=link.signal_id,
                    relationship_type=link.relationship_type,
                    confidence=link.confidence,
                    created_at=link.created_at,
                )
                .on_conflict_do_nothing(index_elements=["opportunity_id", "signal_id"])
            )
        await session.execute(
            delete(OpportunitySignalLink).where(OpportunitySignalLink.opportunity_id == source_id)
        )
        await session.execute(
            update(OpportunityEvidence)
            .where(OpportunityEvidence.opportunity_id == source_id)
            .values(opportunity_id=canonical_id)
        )
        await self._merge_watchlists(session, source_id, canonical_id)
        source.status = "merged"
        source.updated_at = now
        if source.last_activity_at > canonical.last_activity_at:
            canonical.last_activity_at = source.last_activity_at
        canonical.updated_at = now
        await session.flush()
        return {
            "source_opportunity_status": "merged",
            "opportunity_id": str(canonical_id),
            "merge_history_id": str(history.id),
        }

    async def _merge_watchlists(self, session, source_id, canonical_id):
        source_items = list(
            await session.scalars(
                select(WatchlistItem).where(WatchlistItem.opportunity_id == source_id)
            )
        )
        for source_item in source_items:
            canonical_item = await session.scalar(
                select(WatchlistItem)
                .where(
                    WatchlistItem.watchlist_id == source_item.watchlist_id,
                    WatchlistItem.opportunity_id == canonical_id,
                )
                .with_for_update()
            )
            if canonical_item:
                canonical_item.added_at = min(canonical_item.added_at, source_item.added_at)
                await session.delete(source_item)
            else:
                source_item.opportunity_id = canonical_id

    async def _creates_cycle(self, session, source_id, canonical_id):
        current, seen = canonical_id, set()
        while current not in seen:
            if current == source_id:
                return True
            seen.add(current)
            current = await session.scalar(
                select(OpportunityMergeHistory.canonical_opportunity_id)
                .where(OpportunityMergeHistory.source_opportunity_id == current)
                .order_by(OpportunityMergeHistory.merged_at.desc())
                .limit(1)
            )
            if current is None:
                return False
        return True

    @staticmethod
    def _uuid(value):
        try:
            return UUID(str(value)) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _slugify(value):
        normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "opportunity"

    @staticmethod
    def _task_result(task):
        return ReviewTaskResult.model_validate(task, from_attributes=True)

    @staticmethod
    def _workflow_result(task, previous, effects):
        return ReviewWorkflowResult(
            review_task_id=task.id,
            review_type=task.review_type,
            previous_status=previous,
            status=task.status,
            decision=task.decision,
            target_type=task.target_type,
            target_id=task.target_id,
            assigned_to=task.assigned_to,
            resolved_by=task.resolved_by,
            resolved_at=task.resolved_at,
            side_effects=effects,
        )
