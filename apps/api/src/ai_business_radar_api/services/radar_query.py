from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.database.repositories.radar_queries import RadarQueryRepository
from .intelligence_localization import IntelligenceLocalizationService, Locale

Window = Literal["7d", "30d", "90d"]
Sort = Literal["score", "momentum", "confidence", "hype", "recent"]
LibrarySort = Literal[
    "last_activity_desc",
    "first_detected_desc",
    "score_desc",
    "confidence_desc",
    "momentum_desc",
    "name_asc",
]
Direction = Literal["asc", "desc"]


class OpportunityNotVisibleError(RuntimeError):
    pass


class TrendItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    window_type: str
    period_start: datetime
    period_end: datetime
    aggregation_version: str
    video_count: int
    new_video_count: int
    unique_channel_count: int
    total_views: int
    comment_count: int
    pain_signal_count: int
    demand_signal_count: int
    purchase_intent_signal_count: int
    revenue_signal_count: int
    competitor_signal_count: int
    momentum_score: Decimal | None


class ScoreItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    calculated_at: datetime
    scoring_version: str
    trend_velocity_score: Decimal
    demand_evidence_score: Decimal
    revenue_evidence_score: Decimal
    pain_severity_score: Decimal
    competition_white_space_score: Decimal
    build_feasibility_score: Decimal
    distribution_ease_score: Decimal
    opportunity_score: Decimal
    confidence_score: Decimal | None
    hype_risk_score: Decimal | None


class EvidenceSummary(BaseModel):
    active_signal_count: int = 0
    distinct_video_count: int = 0
    distinct_channel_count: int = 0
    pain_signal_count: int = 0
    demand_signal_count: int = 0
    purchase_intent_signal_count: int = 0
    revenue_signal_count: int = 0


class TaxonomyProjection(BaseModel):
    code: str
    label: str


class RadarOpportunityItem(BaseModel):
    id: UUID
    slug: str
    name: str
    one_line_thesis: str | None
    industry: str | None
    sub_industry: str | None
    customer_type: str | None
    industry_taxonomy: TaxonomyProjection | None = None
    customer_taxonomy: TaxonomyProjection | None = None
    business_model: str | None
    market_stage: str
    competition_level: str | None
    build_difficulty: str | None
    sales_difficulty: str | None
    opportunity_score: Decimal | None
    confidence_score: Decimal | None
    hype_risk_score: Decimal | None
    trend: TrendItem | None
    first_detected_at: datetime
    last_activity_at: datetime
    evidence_summary: EvidenceSummary
    watchlisted: bool


class RadarResponse(BaseModel):
    items: list[RadarOpportunityItem]
    total: int
    offset: int
    limit: int


class OpportunityLibraryRequest(BaseModel):
    q: str | None = Field(default=None, max_length=200)
    industry_code: str | None = None
    customer_code: str | None = None
    market_stage: str | None = None
    min_score: Decimal | None = Field(default=None, ge=0, le=100)
    max_score: Decimal | None = Field(default=None, ge=0, le=100)
    min_confidence: Decimal | None = Field(default=None, ge=0, le=100)
    max_hype_risk: Decimal | None = Field(default=None, ge=0, le=100)
    watchlisted: bool | None = None
    sort: LibrarySort = "last_activity_desc"
    page: int = Field(default=1, ge=1)
    page_size: Literal[20, 50, 100] = 20


class OpportunityLibraryResponse(BaseModel):
    items: list[RadarOpportunityItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class RadarRequest(BaseModel):
    window_type: Window = "7d"
    sort: Sort = "score"
    direction: Direction = "desc"
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    q: str | None = Field(default=None, max_length=200)
    industry: list[str] = Field(default_factory=list)
    sub_industry: list[str] = Field(default_factory=list)
    business_model: list[str] = Field(default_factory=list)
    customer_type: list[str] = Field(default_factory=list)
    market_stage: list[str] = Field(default_factory=list)
    competition_level: list[str] = Field(default_factory=list)
    build_difficulty: list[str] = Field(default_factory=list)
    sales_difficulty: list[str] = Field(default_factory=list)
    score_min: Decimal | None = Field(default=None, ge=0, le=100)
    score_max: Decimal | None = Field(default=None, ge=0, le=100)
    confidence_min: Decimal | None = Field(default=None, ge=0, le=100)
    confidence_max: Decimal | None = Field(default=None, ge=0, le=100)
    hype_max: Decimal | None = Field(default=None, ge=0, le=100)
    detected_after: datetime | None = None
    industry_code: str | None = None
    customer_code: str | None = None


class OpportunityDetailData(BaseModel):
    id: UUID
    slug: str
    name: str
    one_line_thesis: str | None
    industry: str | None
    sub_industry: str | None
    customer_type: str | None
    industry_taxonomy: TaxonomyProjection | None = None
    customer_taxonomy: TaxonomyProjection | None = None
    problem: str | None
    solution: str | None
    business_model: str | None
    primary_technology: str | None
    typical_price_min: Decimal | None
    typical_price_max: Decimal | None
    typical_price_currency: str | None
    typical_price_period: str | None
    competition_level: str | None
    build_difficulty: str | None
    sales_difficulty: str | None
    market_stage: str
    first_detected_at: datetime
    last_activity_at: datetime


class OpportunityDetail(BaseModel):
    opportunity: OpportunityDetailData
    current_intelligence: ScoreItem | None
    trend_summary: dict[str, TrendItem | None]
    evidence_summary: EvidenceSummary
    watchlisted: bool


class EvidenceItem(BaseModel):
    evidence_id: UUID
    evidence_type: str
    summary: str
    source_type: str
    observed_at: datetime | None
    strength: Decimal | None
    confidence: Decimal | None
    youtube_video_id: str | None
    video_title: str | None


class SignalFeedItem(BaseModel):
    id: UUID
    signal_type: str
    statement: str
    evidence_text: str | None
    industry: str | None
    customer_type: str | None
    industry_taxonomy: TaxonomyProjection | None = None
    customer_taxonomy: TaxonomyProjection | None = None
    claim_status: str
    confidence: Decimal
    evidence_strength: Decimal | None
    observed_at: datetime | None
    source_type: str
    video_title: str | None
    channel_name: str | None
    opportunity_ids: list[UUID]
    opportunities: list["LinkedOpportunity"]
    original_statement: str
    original_evidence_text: str | None
    statement_localized: bool = False
    evidence_localized: bool = False
    localization_stale: bool = False


class LinkedOpportunity(BaseModel):
    id: UUID
    slug: str
    name: str


class RadarQueryService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def radar(
        self, user_id: UUID, request: RadarRequest, locale: Locale = "en-US"
    ) -> RadarResponse:
        async with self._sessions() as session:
            repo = RadarQueryRepository(session)
            opportunities = await repo.list_active_opportunities(
                request.industry_code, request.customer_code
            )
            ids = [item.id for item in opportunities]
            scores = await repo.latest_scores(ids)
            trends = await repo.latest_trends(ids, request.window_type)
            summaries = await repo.evidence_summaries(ids)
            watched = await repo.watchlisted_ids(user_id, ids)
            localization = IntelligenceLocalizationService(session)
            taxonomy = await repo.taxonomy("opportunity", ids, locale)
            items = []
            for item in opportunities:
                fields = await localization.localize(
                    "opportunity",
                    item.id,
                    locale,
                    {
                        "name": item.name,
                        "one_line_thesis": item.one_line_thesis,
                        "industry": item.industry,
                        "customer_type": item.customer_type,
                    },
                )
                items.append(
                    self._item(
                        item,
                        scores.get(item.id),
                        trends.get(item.id),
                        summaries.get(item.id),
                        watched,
                        fields,
                        taxonomy,
                    )
                )
        items = self._filter(items, request)
        items = self._sort(items, request.sort, request.direction)
        total = len(items)
        if request.sort == "score":
            items = [item for item in items if item.opportunity_score is not None]
            total = len(items)
        return RadarResponse(
            items=items[request.offset : request.offset + request.limit],
            total=total,
            offset=request.offset,
            limit=request.limit,
        )

    async def opportunities(
        self, user_id: UUID, request: OpportunityLibraryRequest, locale: Locale = "en-US"
    ) -> OpportunityLibraryResponse:
        async with self._sessions() as session:
            repo = RadarQueryRepository(session)
            opportunities = await repo.list_active_opportunities(
                request.industry_code, request.customer_code
            )
            ids = [item.id for item in opportunities]
            scores = await repo.latest_scores(ids)
            trends = await repo.latest_trends(ids, "7d")
            summaries = await repo.evidence_summaries(ids)
            watched = await repo.watchlisted_ids(user_id, ids)
            taxonomy = await repo.taxonomy("opportunity", ids, locale)
            canonical = {
                item.id: {
                    "name": item.name,
                    "one_line_thesis": item.one_line_thesis,
                    "problem": item.problem,
                    "solution": item.solution,
                    "industry": item.industry,
                    "customer_type": item.customer_type,
                }
                for item in opportunities
            }
            localized = await IntelligenceLocalizationService(session).localize_many(
                "opportunity", canonical, locale
            )
            items = [
                self._item(
                    item,
                    scores.get(item.id),
                    trends.get(item.id),
                    summaries.get(item.id),
                    watched,
                    localized[item.id],
                    taxonomy,
                )
                for item in opportunities
            ]
        needle = request.q.casefold().strip() if request.q else None
        if needle:
            items = [
                item
                for item in items
                if needle
                in " ".join(
                    str(localized[item.id].get(field).text or "")
                    for field in ("name", "one_line_thesis", "problem", "solution")
                ).casefold()
            ]
        if request.market_stage:
            items = [item for item in items if item.market_stage == request.market_stage]
        if request.min_score is not None:
            items = [
                item
                for item in items
                if item.opportunity_score is not None
                and item.opportunity_score >= request.min_score
            ]
        if request.max_score is not None:
            items = [
                item
                for item in items
                if item.opportunity_score is not None
                and item.opportunity_score <= request.max_score
            ]
        if request.min_confidence is not None:
            items = [
                item
                for item in items
                if item.confidence_score is not None
                and item.confidence_score >= request.min_confidence
            ]
        if request.max_hype_risk is not None:
            items = [
                item
                for item in items
                if item.hype_risk_score is not None
                and item.hype_risk_score <= request.max_hype_risk
            ]
        if request.watchlisted is not None:
            items = [item for item in items if item.watchlisted is request.watchlisted]
        key = {
            "last_activity_desc": lambda x: x.last_activity_at,
            "first_detected_desc": lambda x: x.first_detected_at,
            "score_desc": lambda x: x.opportunity_score or Decimal("-1"),
            "confidence_desc": lambda x: x.confidence_score or Decimal("-1"),
            "momentum_desc": lambda x: (
                x.trend.momentum_score
                if x.trend and x.trend.momentum_score is not None
                else Decimal("-1")
            ),
            "name_asc": lambda x: x.name.casefold(),
        }[request.sort]
        items.sort(key=key, reverse=request.sort != "name_asc")
        total = len(items)
        start = (request.page - 1) * request.page_size
        return OpportunityLibraryResponse(
            items=items[start : start + request.page_size],
            total=total,
            page=request.page,
            page_size=request.page_size,
            total_pages=(total + request.page_size - 1) // request.page_size,
        )

    async def detail(
        self, user_id: UUID, identifier: str, locale: Locale = "en-US"
    ) -> OpportunityDetail:
        async with self._sessions() as session:
            repo = RadarQueryRepository(session)
            opportunity = await repo.get_visible_opportunity(identifier)
            if opportunity is None:
                raise OpportunityNotVisibleError("Opportunity was not found")
            scores = await repo.latest_scores([opportunity.id])
            trends = {
                window: (await repo.latest_trends([opportunity.id], window)).get(opportunity.id)
                for window in ("7d", "30d", "90d")
            }
            summaries = await repo.evidence_summaries([opportunity.id])
            watched = await repo.watchlisted_ids(user_id, [opportunity.id])
            localized = await IntelligenceLocalizationService(session).localize(
                "opportunity",
                opportunity.id,
                locale,
                {
                    "name": opportunity.name,
                    "one_line_thesis": opportunity.one_line_thesis,
                    "industry": opportunity.industry,
                    "customer_type": opportunity.customer_type,
                    "problem": opportunity.problem,
                    "solution": opportunity.solution,
                },
            )
            taxonomy = await repo.taxonomy("opportunity", [opportunity.id], locale)
        identity = {
            key: getattr(opportunity, key)
            for key in (
                "id",
                "slug",
                "name",
                "one_line_thesis",
                "industry",
                "sub_industry",
                "customer_type",
                "problem",
                "solution",
                "business_model",
                "primary_technology",
                "typical_price_min",
                "typical_price_max",
                "typical_price_currency",
                "typical_price_period",
                "competition_level",
                "build_difficulty",
                "sales_difficulty",
                "market_stage",
                "first_detected_at",
                "last_activity_at",
            )
        }
        for key, value in localized.items():
            identity[key] = value.text
        identity["industry_taxonomy"] = taxonomy.get((opportunity.id, "industry"))
        identity["customer_taxonomy"] = taxonomy.get((opportunity.id, "customer"))
        return OpportunityDetail(
            opportunity=OpportunityDetailData(**identity),
            current_intelligence=self._score(scores.get(opportunity.id)),
            trend_summary={key: self._trend(value) for key, value in trends.items()},
            evidence_summary=EvidenceSummary(**summaries.get(opportunity.id, {})),
            watchlisted=opportunity.id in watched,
        )

    async def trends(self, identifier: str, window: Window | None, limit: int) -> list[TrendItem]:
        async with self._sessions() as session:
            repo = RadarQueryRepository(session)
            opportunity = await repo.get_visible_opportunity(identifier)
            if opportunity is None:
                raise OpportunityNotVisibleError("Opportunity was not found")
            rows = await repo.trend_history(opportunity.id, window, limit)
        return [TrendItem.model_validate(row) for row in rows]

    async def scores(self, identifier: str, limit: int) -> list[ScoreItem]:
        async with self._sessions() as session:
            repo = RadarQueryRepository(session)
            opportunity = await repo.get_visible_opportunity(identifier)
            if opportunity is None:
                raise OpportunityNotVisibleError("Opportunity was not found")
            rows = await repo.score_history(opportunity.id, limit)
        return [ScoreItem.model_validate(row) for row in rows]

    async def evidence(self, identifier: str, offset: int, limit: int) -> list[EvidenceItem]:
        async with self._sessions() as session:
            repo = RadarQueryRepository(session)
            opportunity = await repo.get_visible_opportunity(identifier)
            if opportunity is None:
                raise OpportunityNotVisibleError("Opportunity was not found")
            rows = await repo.evidence(opportunity.id, offset, limit)
        return [EvidenceItem(**dict(row._mapping)) for row in rows]

    async def signals(self, locale: Locale = "en-US", **filters: Any) -> list[SignalFeedItem]:
        async with self._sessions() as session:
            rows = await RadarQueryRepository(session).active_signals(**filters)
            localization = IntelligenceLocalizationService(session)
            taxonomy = await RadarQueryRepository(session).taxonomy(
                "signal", [row._mapping["id"] for row in rows], locale
            )
            items = []
            for row in rows:
                values = dict(row._mapping)
                localized = await localization.localize(
                    "signal",
                    values["id"],
                    locale,
                    {
                        "statement": values["statement"],
                        "evidence_text": values["evidence_text"],
                        "industry": values["industry"],
                        "customer_type": values["customer_type"],
                    },
                )
                values["original_statement"] = values["statement"]
                values["original_evidence_text"] = values["evidence_text"]
                for key, value in localized.items():
                    values[key] = value.text
                values["statement_localized"] = localized["statement"].localized
                values["evidence_localized"] = localized["evidence_text"].localized
                values["localization_stale"] = any(value.stale for value in localized.values())
                values["opportunity_ids"] = values["opportunity_ids"] or []
                values["opportunities"] = values["opportunities"] or []
                values["industry_taxonomy"] = taxonomy.get((values["id"], "industry"))
                values["customer_taxonomy"] = taxonomy.get((values["id"], "customer"))
                for opportunity in values["opportunities"]:
                    name = await localization.localize(
                        "opportunity",
                        UUID(str(opportunity["id"])),
                        locale,
                        {"name": opportunity["name"]},
                    )
                    opportunity["name"] = name["name"].text
                items.append(SignalFeedItem(**values))
        return items

    @staticmethod
    def _item(opportunity, score, trend, summary, watched, localized=None, taxonomy=None):
        localized = localized or {}

        def value(field):
            return localized[field].text if field in localized else getattr(opportunity, field)

        return RadarOpportunityItem(
            id=opportunity.id,
            slug=opportunity.slug,
            name=value("name"),
            one_line_thesis=value("one_line_thesis"),
            industry=value("industry"),
            sub_industry=opportunity.sub_industry,
            customer_type=value("customer_type"),
            industry_taxonomy=(taxonomy or {}).get((opportunity.id, "industry")),
            customer_taxonomy=(taxonomy or {}).get((opportunity.id, "customer")),
            business_model=opportunity.business_model,
            market_stage=opportunity.market_stage,
            competition_level=opportunity.competition_level,
            build_difficulty=opportunity.build_difficulty,
            sales_difficulty=opportunity.sales_difficulty,
            opportunity_score=score.opportunity_score if score else None,
            confidence_score=score.confidence_score if score else None,
            hype_risk_score=score.hype_risk_score if score else None,
            trend=RadarQueryService._trend(trend),
            first_detected_at=opportunity.first_detected_at,
            last_activity_at=opportunity.last_activity_at,
            evidence_summary=EvidenceSummary(**(summary or {})),
            watchlisted=opportunity.id in watched,
        )

    @staticmethod
    def _filter(items, request):
        fields = (
            "industry",
            "sub_industry",
            "business_model",
            "customer_type",
            "market_stage",
            "competition_level",
            "build_difficulty",
            "sales_difficulty",
        )
        for field in fields:
            values = {value.lower() for value in getattr(request, field)}
            if values:
                items = [item for item in items if (getattr(item, field) or "").lower() in values]
        if request.q:
            query = request.q.lower()
            items = [
                item
                for item in items
                if query
                in " ".join(
                    str(getattr(item, field) or "").lower()
                    for field in (
                        "name",
                        "one_line_thesis",
                        "industry",
                        "sub_industry",
                        "customer_type",
                    )
                )
            ]
        ranges = (
            ("opportunity_score", request.score_min, request.score_max),
            ("confidence_score", request.confidence_min, request.confidence_max),
        )
        for field, minimum, maximum in ranges:
            if minimum is not None:
                items = [
                    item
                    for item in items
                    if getattr(item, field) is not None and getattr(item, field) >= minimum
                ]
            if maximum is not None:
                items = [
                    item
                    for item in items
                    if getattr(item, field) is not None and getattr(item, field) <= maximum
                ]
        if request.hype_max is not None:
            items = [
                item
                for item in items
                if item.hype_risk_score is not None and item.hype_risk_score <= request.hype_max
            ]
        if request.detected_after is not None:
            items = [item for item in items if item.first_detected_at >= request.detected_after]
        return items

    @staticmethod
    def _sort(items, sort, direction):
        def value(item):
            if sort == "momentum":
                return item.trend.momentum_score if item.trend else None
            if sort == "confidence":
                return item.confidence_score
            if sort == "hype":
                return item.hype_risk_score
            if sort == "recent":
                return item.last_activity_at
            return item.opportunity_score

        present = [item for item in items if value(item) is not None]
        missing = [item for item in items if value(item) is None]
        present.sort(key=lambda item: str(item.id))
        if sort == "momentum":
            present.sort(key=lambda item: item.opportunity_score or Decimal("-1"), reverse=True)
        else:
            present.sort(key=lambda item: item.last_activity_at, reverse=True)
        present.sort(key=value, reverse=direction == "desc")
        missing.sort(key=lambda item: (-item.last_activity_at.timestamp(), str(item.id)))
        return present + missing

    @staticmethod
    def _trend(row):
        return TrendItem.model_validate(row) if row else None

    @staticmethod
    def _score(row):
        return ScoreItem.model_validate(row) if row else None
