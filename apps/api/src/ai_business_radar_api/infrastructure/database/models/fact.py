"""FACT persistence mappings."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AIExtraction(Base):
    __tablename__ = "ai_extractions"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_type: Mapped[str]
    source_id: Mapped[UUID] = mapped_column(Uuid)
    video_id: Mapped[UUID | None] = mapped_column(ForeignKey("videos.id"))
    comment_id: Mapped[UUID | None] = mapped_column(ForeignKey("comments.id"))
    signal_id: Mapped[UUID | None] = mapped_column(ForeignKey("signals.id"))
    opportunity_id: Mapped[UUID | None] = mapped_column(ForeignKey("opportunities.id"))
    task_type: Mapped[str]
    provider: Mapped[str]
    model: Mapped[str]
    prompt_version: Mapped[str]
    prompt_hash: Mapped[str | None]
    input_hash: Mapped[str]
    attempt_number: Mapped[int] = mapped_column(Integer)
    supersedes_extraction_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai_extractions.id"))
    status: Mapped[str]
    raw_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    parsed_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    provider_request_id: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_type: Mapped[str]
    source_id: Mapped[UUID] = mapped_column(Uuid)
    video_id: Mapped[UUID | None] = mapped_column(ForeignKey("videos.id"))
    comment_id: Mapped[UUID | None] = mapped_column(ForeignKey("comments.id"))
    ai_extraction_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai_extractions.id"))
    signal_type: Mapped[str]
    statement: Mapped[str] = mapped_column(Text)
    evidence_text: Mapped[str | None] = mapped_column(Text)
    normalized_statement: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None]
    sub_industry: Mapped[str | None]
    customer_type: Mapped[str | None]
    problem: Mapped[str | None] = mapped_column(Text)
    solution: Mapped[str | None] = mapped_column(Text)
    business_model: Mapped[str | None]
    price_min: Mapped[Decimal | None] = mapped_column(Numeric)
    price_max: Mapped[Decimal | None] = mapped_column(Numeric)
    price_currency: Mapped[str | None]
    price_period: Mapped[str | None]
    revenue_claim_amount: Mapped[Decimal | None] = mapped_column(Numeric)
    revenue_claim_currency: Mapped[str | None]
    revenue_claim_period: Mapped[str | None]
    customer_count_claim: Mapped[int | None] = mapped_column(Integer)
    technology: Mapped[list[str] | None] = mapped_column(JSONB)
    distribution_channels: Mapped[list[str] | None] = mapped_column(JSONB)
    geography: Mapped[list[str] | None] = mapped_column(JSONB)
    claim_status: Mapped[str]
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    evidence_strength: Mapped[Decimal | None] = mapped_column(Numeric)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
