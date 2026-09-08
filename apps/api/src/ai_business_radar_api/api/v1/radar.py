# ruff: noqa: B008

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ...infrastructure.auth import RequiredUser
from ...services.radar_query import (
    EvidenceItem,
    OpportunityDetail,
    OpportunityNotVisibleError,
    RadarQueryService,
    RadarRequest,
    RadarResponse,
    ScoreItem,
    SignalFeedItem,
    TrendItem,
)

router = APIRouter(tags=["Radar", "Opportunities", "Signals"])


def get_radar_service(request: Request) -> RadarQueryService:
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    return RadarQueryService(sessions)


def _values(value: list[str] | None) -> list[str]:
    return [part.strip() for item in value or [] for part in item.split(",") if part.strip()]


def _request(
    window_type="7d",
    sort="score",
    direction="desc",
    limit=25,
    offset=0,
    q=None,
    industry=None,
    sub_industry=None,
    business_model=None,
    customer_type=None,
    market_stage=None,
    competition_level=None,
    build_difficulty=None,
    sales_difficulty=None,
    score_min=None,
    score_max=None,
    confidence_min=None,
    confidence_max=None,
    hype_max=None,
    detected_after=None,
    industry_code=None,
    customer_code=None,
    **_ignored,
) -> RadarRequest:
    if score_min is not None and score_max is not None and score_min > score_max:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid score range")
    if (
        confidence_min is not None
        and confidence_max is not None
        and confidence_min > confidence_max
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid confidence range")
    return RadarRequest(
        window_type=window_type,
        sort=sort,
        direction=direction,
        limit=limit,
        offset=offset,
        q=q,
        industry=_values(industry),
        sub_industry=_values(sub_industry),
        business_model=_values(business_model),
        customer_type=_values(customer_type),
        market_stage=_values(market_stage),
        competition_level=_values(competition_level),
        build_difficulty=_values(build_difficulty),
        sales_difficulty=_values(sales_difficulty),
        score_min=score_min,
        score_max=score_max,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        hype_max=hype_max,
        detected_after=detected_after,
        industry_code=industry_code,
        customer_code=customer_code,
    )


@router.get("/radar", response_model=RadarResponse)
async def radar(
    user: RequiredUser,
    service: Annotated[RadarQueryService, Depends(get_radar_service)],
    window_type: Literal["7d", "30d", "90d"] = "7d",
    sort: Literal["score", "momentum", "confidence", "hype", "recent"] = "score",
    direction: Literal["asc", "desc"] = "desc",
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=200),
    industry: list[str] | None = Query(None),
    sub_industry: list[str] | None = Query(None),
    business_model: list[str] | None = Query(None),
    customer_type: list[str] | None = Query(None),
    market_stage: list[str] | None = Query(None),
    competition_level: list[str] | None = Query(None),
    build_difficulty: list[str] | None = Query(None),
    sales_difficulty: list[str] | None = Query(None),
    score_min: Decimal | None = Query(None, ge=0, le=100),
    score_max: Decimal | None = Query(None, ge=0, le=100),
    confidence_min: Decimal | None = Query(None, ge=0, le=100),
    confidence_max: Decimal | None = Query(None, ge=0, le=100),
    hype_max: Decimal | None = Query(None, ge=0, le=100),
    detected_after: datetime | None = None,
    industry_code: str | None = None,
    customer_code: str | None = None,
    locale: Literal["zh-CN", "en-US"] = "en-US",
) -> RadarResponse:
    return await service.radar(user.user_profile_id, _request(**locals()), locale)


@router.get("/opportunities", response_model=RadarResponse)
async def opportunities(
    user: RequiredUser,
    service: Annotated[RadarQueryService, Depends(get_radar_service)],
    window_type: Literal["7d", "30d", "90d"] = "7d",
    sort: Literal["score", "momentum", "confidence", "hype", "recent"] = "recent",
    direction: Literal["asc", "desc"] = "desc",
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=200),
    industry: list[str] | None = Query(None),
    sub_industry: list[str] | None = Query(None),
    business_model: list[str] | None = Query(None),
    customer_type: list[str] | None = Query(None),
    market_stage: list[str] | None = Query(None),
    competition_level: list[str] | None = Query(None),
    build_difficulty: list[str] | None = Query(None),
    sales_difficulty: list[str] | None = Query(None),
    score_min: Decimal | None = Query(None, ge=0, le=100),
    score_max: Decimal | None = Query(None, ge=0, le=100),
    confidence_min: Decimal | None = Query(None, ge=0, le=100),
    confidence_max: Decimal | None = Query(None, ge=0, le=100),
    hype_max: Decimal | None = Query(None, ge=0, le=100),
    detected_after: datetime | None = None,
    industry_code: str | None = None,
    customer_code: str | None = None,
    locale: Literal["zh-CN", "en-US"] = "en-US",
) -> RadarResponse:
    return await service.opportunities(user.user_profile_id, _request(**locals()), locale)


def _not_found(error: OpportunityNotVisibleError) -> None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity was not found") from error


@router.get("/opportunities/{identifier}", response_model=OpportunityDetail)
async def detail(
    identifier: str,
    user: RequiredUser,
    service: Annotated[RadarQueryService, Depends(get_radar_service)],
    locale: Literal["zh-CN", "en-US"] = "en-US",
) -> OpportunityDetail:
    try:
        return await service.detail(user.user_profile_id, identifier, locale)
    except OpportunityNotVisibleError as error:
        _not_found(error)


@router.get("/opportunities/{identifier}/trends", response_model=list[TrendItem])
async def trends(
    identifier: str,
    _: RequiredUser,
    service: Annotated[RadarQueryService, Depends(get_radar_service)],
    window_type: Literal["7d", "30d", "90d"] | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> list[TrendItem]:
    try:
        return await service.trends(identifier, window_type, limit)
    except OpportunityNotVisibleError as error:
        _not_found(error)


@router.get("/opportunities/{identifier}/scores", response_model=list[ScoreItem])
async def scores(
    identifier: str,
    _: RequiredUser,
    service: Annotated[RadarQueryService, Depends(get_radar_service)],
    limit: int = Query(50, ge=1, le=200),
) -> list[ScoreItem]:
    try:
        return await service.scores(identifier, limit)
    except OpportunityNotVisibleError as error:
        _not_found(error)


@router.get("/opportunities/{identifier}/evidence", response_model=list[EvidenceItem])
async def evidence(
    identifier: str,
    _: RequiredUser,
    service: Annotated[RadarQueryService, Depends(get_radar_service)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[EvidenceItem]:
    try:
        return await service.evidence(identifier, offset, limit)
    except OpportunityNotVisibleError as error:
        _not_found(error)


@router.get("/signals", response_model=list[SignalFeedItem])
async def signals(
    _: RequiredUser,
    service: Annotated[RadarQueryService, Depends(get_radar_service)],
    signal_type: str | None = None,
    industry: str | None = None,
    customer_type: str | None = None,
    industry_code: str | None = None,
    customer_code: str | None = None,
    opportunity_id: UUID | None = None,
    observed_after: datetime | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    locale: Literal["zh-CN", "en-US"] = "en-US",
) -> list[SignalFeedItem]:
    return await service.signals(
        locale=locale,
        signal_type=signal_type,
        industry=industry,
        customer_type=customer_type,
        industry_code=industry_code,
        customer_code=customer_code,
        opportunity_id=opportunity_id,
        observed_after=observed_after,
        offset=offset,
        limit=limit,
    )
