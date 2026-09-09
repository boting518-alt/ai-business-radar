"""Admin-only candidate curation. Reads never enqueue or generate intelligence."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select

from ..infrastructure.database.models import (
    ActivationReviewEvent,
    Opportunity,
    OpportunityRevision,
    OpportunitySignalLink,
    ReviewTask,
    Signal,
)
from ..infrastructure.database.repositories.radar_queries import RadarQueryRepository
from .intelligence_localization import IntelligenceLocalizationService
from .intelligence_translation import ENTITY_FIELDS
from .opportunity_activation import (
    OpportunityActivationReadiness,
    OpportunityActivationReadinessService,
)
from .radar_query import EvidenceItem, EvidencePage, EvidenceSummary, RadarQueryService
from .source_provenance import source_navigation


class CandidateNotFound(RuntimeError):
    pass


class CandidateConflict(ValueError):
    pass


class CandidateFilters(BaseModel):
    locale: Literal["en-US", "zh-CN"] = "en-US"
    q: str | None = Field(None, max_length=200)
    industry_code: str | None = None
    customer_code: str | None = None
    readiness: Literal["ready", "needs_review", "not_ready"] | None = None
    review_state: Literal["none", "pending", "in_review", "deferred"] | None = None
    has_semantic_warnings: bool | None = None
    sort: Literal["priority", "recent", "name"] = "priority"
    offset: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=100)


class CandidateEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_updated_at: datetime
    note: str | None = Field(None, max_length=2000)
    name: str | None = Field(None, max_length=300)
    one_line_thesis: str | None = Field(None, max_length=4000)
    problem: str | None = Field(None, max_length=8000)
    solution: str | None = Field(None, max_length=8000)
    business_model: str | None = Field(None, max_length=300)
    typical_price_min: Decimal | None = Field(None, ge=0, allow_inf_nan=False)
    typical_price_max: Decimal | None = Field(None, ge=0, allow_inf_nan=False)
    typical_price_currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    typical_price_period: str | None = Field(None, max_length=100)
    market_stage: (
        Literal[
            "unknown", "emerging", "accelerating", "validated", "crowded", "mature", "declining"
        ]
        | None
    ) = None
    competition_level: Literal["unknown", "low", "medium", "high"] | None = None
    build_difficulty: Literal["unknown", "low", "medium", "high"] | None = None

    @field_validator("name")
    @classmethod
    def name_required(cls, value):
        if value is None or not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def required_fields(self):
        if "market_stage" in self.model_fields_set and self.market_stage is None:
            raise ValueError("Market stage must not be null")
        if self.expected_updated_at.utcoffset() is None:
            raise ValueError("Expected update time must include timezone")
        return self


class CandidateSummary(BaseModel):
    id: UUID
    name: str
    one_line_thesis: str | None
    industry: str | None
    customer_type: str | None
    industry_taxonomy: dict | None
    customer_taxonomy: dict | None
    evidence_summary: EvidenceSummary
    semantic_warning_count: int
    readiness: OpportunityActivationReadiness
    activation_review: dict | None
    review_state: str
    last_activity_at: datetime
    score_at: datetime | None
    trend_at: datetime | None
    score_freshness: str
    trend_freshness: str


class CandidatePage(BaseModel):
    items: list[CandidateSummary]
    total: int
    offset: int
    limit: int
    has_more: bool
    counts: dict[str, int]


class CandidateDetail(BaseModel):
    summary: CandidateSummary
    opportunity: dict[str, Any]
    revisions: list[dict]
    review_history: list[dict]
    legacy_reviews: list[dict]
    translation_state: str
    history_has_more: bool


def record(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def freshness(timestamp, activity):
    if timestamp is None:
        return "pending"
    return (
        "stale"
        if timestamp < activity or timestamp < datetime.now(UTC) - timedelta(days=1)
        else "ready"
    )


class CandidateWorkspaceService:
    def __init__(self, sessions):
        self._sessions = sessions
        self.activation = OpportunityActivationReadinessService(sessions)

    async def _summaries(self, session, opportunities, locale):
        ids = [o.id for o in opportunities]
        if not ids:
            return []
        repo = RadarQueryRepository(session)
        readiness = await self.activation.assess_many(session, opportunities)
        evidence = await repo.evidence_summaries(ids)
        taxonomy = await repo.taxonomy("opportunity", ids, locale)
        scores = await repo.latest_scores(ids)
        trends = await repo.latest_trends(ids, "7d")
        warnings = dict(
            (
                await session.execute(
                    select(OpportunitySignalLink.opportunity_id, func.count())
                    .join(Signal, Signal.id == OpportunitySignalLink.signal_id)
                    .where(
                        OpportunitySignalLink.opportunity_id.in_(ids),
                        Signal.semantic_status != "current",
                    )
                    .group_by(OpportunitySignalLink.opportunity_id)
                )
            ).all()
        )
        reviews = list(
            await session.scalars(
                select(ReviewTask)
                .where(
                    ReviewTask.target_id.in_(ids),
                    ReviewTask.review_type == "opportunity_activation",
                    ReviewTask.status.in_(("pending", "in_review")),
                )
                .order_by(ReviewTask.created_at.desc(), ReviewTask.id)
            )
        )
        by_id = {r.target_id: r for r in reviews}
        result = []
        for o in opportunities:
            task = by_id.get(o.id)
            score, trend = scores.get(o.id), trends.get(o.id)
            score_at = score.calculated_at if score else None
            trend_at = trend.period_end if trend else None
            result.append(
                CandidateSummary(
                    id=o.id,
                    name=o.name,
                    one_line_thesis=o.one_line_thesis,
                    industry=o.industry,
                    customer_type=o.customer_type,
                    industry_taxonomy=taxonomy.get((o.id, "industry")),
                    customer_taxonomy=taxonomy.get((o.id, "customer")),
                    evidence_summary=EvidenceSummary(**evidence.get(o.id, {})),
                    semantic_warning_count=warnings.get(o.id, 0),
                    readiness=readiness[o.id],
                    activation_review={
                        k: getattr(task, k)
                        for k in (
                            "id",
                            "status",
                            "assigned_to",
                            "created_at",
                            "decision",
                            "decision_notes",
                        )
                    }
                    if task
                    else None,
                    review_state="deferred"
                    if task and task.status == "pending" and task.decision == "defer"
                    else task.status
                    if task
                    else "none",
                    last_activity_at=o.last_activity_at,
                    score_at=score_at,
                    trend_at=trend_at,
                    score_freshness=freshness(score_at, max(o.last_activity_at, o.updated_at)),
                    trend_freshness=freshness(trend_at, o.last_activity_at),
                )
            )
        return result

    async def list(self, filters: CandidateFilters, locale="en-US"):
        # Matches the existing library's server-side projection pagination. Query count is fixed.
        async with self._sessions() as session:
            opportunities = list(
                await session.scalars(
                    select(Opportunity)
                    .where(Opportunity.status == "candidate")
                    .order_by(Opportunity.id)
                )
            )
            items = await self._summaries(session, opportunities, locale)
        counts = {
            "total": len(items),
            "ready": sum(i.readiness.overall == "ready" for i in items),
            "needs_review": sum(i.readiness.overall == "needs_review" for i in items),
            "not_ready": sum(i.readiness.overall == "not_ready" for i in items),
            "under_review": sum(i.activation_review is not None for i in items),
            "deferred": sum(i.review_state == "deferred" for i in items),
        }
        if filters.q:
            items = [
                i
                for i in items
                if filters.q.casefold() in f"{i.name} {i.one_line_thesis or ''}".casefold()
            ]
        for kind in ("industry", "customer"):
            code = getattr(filters, f"{kind}_code")
            if code:
                items = [
                    i for i in items if (getattr(i, f"{kind}_taxonomy") or {}).get("code") == code
                ]
        if filters.readiness:
            items = [i for i in items if i.readiness.overall == filters.readiness]
        if filters.review_state:
            items = [i for i in items if i.review_state == filters.review_state]
        if filters.has_semantic_warnings is not None:
            items = [
                i for i in items if bool(i.semantic_warning_count) == filters.has_semantic_warnings
            ]
        if filters.sort == "name":
            items.sort(key=lambda i: (i.name.casefold(), str(i.id)))
        elif filters.sort == "recent":
            items.sort(key=lambda i: i.last_activity_at, reverse=True)
        else:
            rank = {"ready": 2, "needs_review": 1, "not_ready": 0}
            items.sort(
                key=lambda i: (
                    rank[i.readiness.overall],
                    i.evidence_summary.supporting_signal_count,
                    i.last_activity_at,
                ),
                reverse=True,
            )
        total = len(items)
        # List cards need only overall status and metrics. Full checks/duplicates live in detail.
        page = [
            item.model_copy(
                update={
                    "readiness": item.readiness.model_copy(
                        update={"checks": {}, "duplicate_candidates": []}
                    )
                }
            )
            for item in items[filters.offset : filters.offset + filters.limit]
        ]
        return CandidatePage(
            items=page,
            total=total,
            offset=filters.offset,
            limit=filters.limit,
            has_more=filters.offset + len(page) < total,
            counts=counts,
        )

    async def detail(self, identity, locale="en-US"):
        async with self._sessions() as session:
            o = await session.get(Opportunity, identity)
            # Retain a read-only dossier after Publish/Invalid for confirmation and audit.
            if o is None:
                raise CandidateNotFound("Opportunity not found")
            summary = (await self._summaries(session, [o], locale))[0]
            revisions = list(
                await session.scalars(
                    select(OpportunityRevision)
                    .where(OpportunityRevision.opportunity_id == identity)
                    .order_by(OpportunityRevision.changed_at.desc(), OpportunityRevision.id)
                    .limit(101)
                )
            )
            events = list(
                await session.scalars(
                    select(ActivationReviewEvent)
                    .where(ActivationReviewEvent.opportunity_id == identity)
                    .order_by(ActivationReviewEvent.created_at.desc(), ActivationReviewEvent.id)
                    .limit(101)
                )
            )
            legacy = list(
                await session.scalars(
                    select(ReviewTask)
                    .where(
                        ReviewTask.target_id == identity,
                        ReviewTask.review_type == "opportunity_activation",
                    )
                    .order_by(ReviewTask.created_at.desc())
                    .limit(100)
                )
            )
            localized = await IntelligenceLocalizationService(session).localize(
                "opportunity",
                identity,
                "zh-CN",
                {k: getattr(o, k) for k in ENTITY_FIELDS["opportunity"]},
            )
            populated = [v for v in localized.values() if v.original_text]
            return CandidateDetail(
                summary=summary,
                opportunity=record(o),
                revisions=[record(r) for r in revisions[:100]],
                review_history=[record(r) for r in events[:100]],
                legacy_reviews=[
                    {
                        k: getattr(r, k)
                        for k in (
                            "id",
                            "status",
                            "assigned_to",
                            "created_at",
                            "updated_at",
                            "resolved_at",
                            "decision",
                            "decision_notes",
                        )
                    }
                    for r in legacy
                ],
                translation_state="ready"
                if populated and all(v.localized for v in populated)
                else "pending",
                history_has_more=len(revisions) > 100 or len(events) > 100,
            )

    async def edit(self, identity, actor, body: CandidateEdit):
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            o = await session.scalar(
                select(Opportunity).where(Opportunity.id == identity).with_for_update()
            )
            if o is None:
                raise CandidateNotFound("Opportunity not found")
            if o.status != "candidate" or o.updated_at != body.expected_updated_at:
                raise CandidateConflict("Candidate changed; reload before saving")
            values = body.model_dump(exclude_unset=True, exclude={"expected_updated_at", "note"})
            values = {
                k: (v.strip() or None) if isinstance(v, str) else v for k, v in values.items()
            }
            minimum = values.get("typical_price_min", o.typical_price_min)
            maximum = values.get("typical_price_max", o.typical_price_max)
            if minimum is not None and maximum is not None and minimum > maximum:
                raise CandidateConflict("Minimum price cannot exceed maximum price")
            changed = False
            for key, value in values.items():
                old = getattr(o, key)
                if value != old:
                    session.add(
                        OpportunityRevision(
                            opportunity_id=identity,
                            changed_by=actor,
                            changed_at=now,
                            field=key,
                            old_value=str(old) if isinstance(old, Decimal) else old,
                            new_value=str(value) if isinstance(value, Decimal) else value,
                            note=body.note,
                        )
                    )
                    setattr(o, key, value)
                    changed = True
            if changed:
                o.updated_at = now
        return await self.detail(identity)

    async def evidence(self, identity, offset, limit, locale, excluded=False, signal_ids=None):
        async with self._sessions() as session:
            if await session.get(Opportunity, identity) is None:
                raise CandidateNotFound("Opportunity not found")
            rows, total = await RadarQueryRepository(session).evidence(
                identity, offset, limit, excluded_only=excluded, signal_ids=signal_ids
            )
            values = [dict(row._mapping) for row in rows]
            localized = await IntelligenceLocalizationService(session).localize_many(
                "signal",
                {
                    v["signal_id"]: {k: v[k] for k in ("statement", "evidence_text")}
                    for v in values
                    if v["signal_id"]
                },
                locale,
            )
            for v in values:
                v.update(source_navigation(v))
                RadarQueryService._localized_signal(v, localized.get(v["signal_id"], {}))
                v["summary"] = v["statement"]
            return EvidencePage(
                items=[EvidenceItem(**v) for v in values],
                total=total,
                offset=offset,
                limit=limit,
                has_more=offset + len(values) < total,
            )
