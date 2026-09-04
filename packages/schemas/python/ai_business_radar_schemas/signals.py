"""Atomic signal domain contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import model_validator

from .common import NonNegativeDecimal, NonNegativeInt, NormalizedConfidence, SchemaModel
from .enums import ClaimStatus, SignalSourceType, SignalStatus, SignalType


class SignalExtractionCandidate(SchemaModel):
    """One commercial observation extracted before persistence."""

    signal_type: SignalType
    statement: str
    normalized_statement: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    customer_type: str | None = None
    problem: str | None = None
    solution: str | None = None
    business_model: str | None = None
    price_min: NonNegativeDecimal | None = None
    price_max: NonNegativeDecimal | None = None
    price_currency: str | None = None
    price_period: str | None = None
    revenue_claim_amount: NonNegativeDecimal | None = None
    revenue_claim_currency: str | None = None
    revenue_claim_period: str | None = None
    customer_count_claim: NonNegativeInt | None = None
    technology: list[str] | None = None
    distribution_channels: list[str] | None = None
    geography: list[str] | None = None
    claim_status: ClaimStatus
    confidence: NormalizedConfidence
    evidence_strength: NormalizedConfidence | None = None
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_commercial_ranges(self) -> "SignalExtractionCandidate":
        if self.price_min is not None and self.price_max is not None:
            if self.price_min > self.price_max:
                raise ValueError("price_min must be less than or equal to price_max")
        if (self.price_min is not None or self.price_max is not None) and not self.price_currency:
            raise ValueError("price_currency is required when a price amount is present")
        if self.revenue_claim_amount is not None and not self.revenue_claim_currency:
            raise ValueError("revenue_claim_currency is required for a revenue claim amount")
        if not self.statement.strip():
            raise ValueError("statement must not be blank")
        return self


class SignalCreate(SignalExtractionCandidate):
    source_type: SignalSourceType
    source_id: UUID
    video_id: UUID | None = None
    comment_id: UUID | None = None
    ai_extraction_id: UUID | None = None
    status: SignalStatus = SignalStatus.REVIEW

    @model_validator(mode="after")
    def validate_source_reference(self) -> "SignalCreate":
        if self.source_type == SignalSourceType.VIDEO:
            valid = self.video_id == self.source_id and self.comment_id is None
        else:
            valid = self.comment_id == self.source_id and self.video_id is None
        if not valid:
            raise ValueError("source_type, source_id, and explicit source FK must agree")
        return self


class SignalRead(SignalCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
