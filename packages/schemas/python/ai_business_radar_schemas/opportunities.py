"""Normalized opportunity domain contracts without embedded score columns."""

from datetime import datetime
from uuid import UUID

from pydantic import model_validator

from .common import NonNegativeDecimal, SchemaModel
from .enums import MarketStage, OpportunityStatus


class OpportunityCreate(SchemaModel):
    slug: str
    name: str
    one_line_thesis: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    customer_type: str | None = None
    problem: str | None = None
    solution: str | None = None
    business_model: str | None = None
    primary_technology: str | None = None
    typical_price_min: NonNegativeDecimal | None = None
    typical_price_max: NonNegativeDecimal | None = None
    typical_price_currency: str | None = None
    typical_price_period: str | None = None
    market_stage: MarketStage
    competition_level: str | None = None
    build_difficulty: str | None = None
    sales_difficulty: str | None = None
    status: OpportunityStatus = OpportunityStatus.CANDIDATE
    first_detected_at: datetime
    last_activity_at: datetime

    @model_validator(mode="after")
    def validate_opportunity(self) -> "OpportunityCreate":
        if not self.slug.strip() or not self.name.strip():
            raise ValueError("slug and name must not be blank")
        if self.typical_price_min is not None and self.typical_price_max is not None:
            if self.typical_price_min > self.typical_price_max:
                raise ValueError("typical_price_min must be less than or equal to typical_price_max")
        if (
            self.typical_price_min is not None or self.typical_price_max is not None
        ) and not self.typical_price_currency:
            raise ValueError("typical_price_currency is required when a price is present")
        if self.first_detected_at > self.last_activity_at:
            raise ValueError("first_detected_at must not be after last_activity_at")
        return self


class OpportunityRead(OpportunityCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime


class OpportunitySummary(SchemaModel):
    id: UUID
    slug: str
    name: str
    one_line_thesis: str | None = None
    industry: str | None = None
    customer_type: str | None = None
    market_stage: MarketStage
    status: OpportunityStatus
    last_activity_at: datetime
