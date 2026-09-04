"""INTELLIGENCE persistence mappings."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(Text)
    one_line_thesis: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None]
    sub_industry: Mapped[str | None]
    customer_type: Mapped[str | None]
    problem: Mapped[str | None] = mapped_column(Text)
    solution: Mapped[str | None] = mapped_column(Text)
    business_model: Mapped[str | None]
    primary_technology: Mapped[str | None]
    typical_price_min: Mapped[Decimal | None] = mapped_column(Numeric)
    typical_price_max: Mapped[Decimal | None] = mapped_column(Numeric)
    typical_price_currency: Mapped[str | None]
    typical_price_period: Mapped[str | None]
    market_stage: Mapped[str]
    competition_level: Mapped[str | None]
    build_difficulty: Mapped[str | None]
    sales_difficulty: Mapped[str | None]
    status: Mapped[str]
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OpportunitySignalLink(Base):
    __tablename__ = "opportunity_signal_links"
    __table_args__ = (UniqueConstraint("opportunity_id", "signal_id"),)
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"))
    signal_id: Mapped[UUID] = mapped_column(ForeignKey("signals.id"))
    relationship_type: Mapped[str]
    confidence: Mapped[Decimal | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OpportunityEvidence(Base):
    __tablename__ = "opportunity_evidence"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"))
    source_type: Mapped[str]
    source_external_id: Mapped[str | None]
    signal_id: Mapped[UUID | None] = mapped_column(ForeignKey("signals.id"))
    video_id: Mapped[UUID | None] = mapped_column(ForeignKey("videos.id"))
    comment_id: Mapped[UUID | None] = mapped_column(ForeignKey("comments.id"))
    evidence_type: Mapped[str]
    summary: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    strength: Mapped[Decimal | None] = mapped_column(Numeric)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_id",
            "window_type",
            "period_start",
            "period_end",
            "aggregation_version",
        ),
    )
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"))
    window_type: Mapped[str]
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    aggregation_version: Mapped[str]
    video_count: Mapped[int] = mapped_column(Integer)
    new_video_count: Mapped[int] = mapped_column(Integer)
    unique_channel_count: Mapped[int] = mapped_column(Integer)
    total_views: Mapped[int] = mapped_column(BigInteger)
    comment_count: Mapped[int] = mapped_column(Integer)
    pain_signal_count: Mapped[int] = mapped_column(Integer)
    demand_signal_count: Mapped[int] = mapped_column(Integer)
    purchase_intent_signal_count: Mapped[int] = mapped_column(Integer)
    revenue_signal_count: Mapped[int] = mapped_column(Integer)
    competitor_signal_count: Mapped[int] = mapped_column(Integer)
    momentum_score: Mapped[Decimal | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OpportunityScore(Base):
    __tablename__ = "opportunity_scores"
    __table_args__ = (UniqueConstraint("opportunity_id", "scoring_version", "calculated_at"),)
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scoring_version: Mapped[str]
    input_hash: Mapped[str]
    trend_velocity_score: Mapped[Decimal] = mapped_column(Numeric)
    demand_evidence_score: Mapped[Decimal] = mapped_column(Numeric)
    revenue_evidence_score: Mapped[Decimal] = mapped_column(Numeric)
    pain_severity_score: Mapped[Decimal] = mapped_column(Numeric)
    competition_white_space_score: Mapped[Decimal] = mapped_column(Numeric)
    build_feasibility_score: Mapped[Decimal] = mapped_column(Numeric)
    distribution_ease_score: Mapped[Decimal] = mapped_column(Numeric)
    opportunity_score: Mapped[Decimal] = mapped_column(Numeric)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric)
    hype_risk_score: Mapped[Decimal | None] = mapped_column(Numeric)
    inputs_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewTask(Base):
    __tablename__ = "review_tasks"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    review_type: Mapped[str]
    target_type: Mapped[str]
    target_id: Mapped[UUID] = mapped_column(Uuid)
    status: Mapped[str]
    priority: Mapped[Decimal] = mapped_column(Numeric)
    assigned_to: Mapped[UUID | None] = mapped_column(ForeignKey("user_profiles.id"))
    decision: Mapped[str | None]
    decision_notes: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OpportunityMergeHistory(Base):
    __tablename__ = "opportunity_merge_history"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"))
    canonical_opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"))
    merged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    merged_by: Mapped[UUID | None] = mapped_column(ForeignKey("user_profiles.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Watchlist(Base):
    __tablename__ = "watchlists"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_profile_id: Mapped[UUID] = mapped_column(ForeignKey("user_profiles.id"))
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "opportunity_id"),)
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    watchlist_id: Mapped[UUID] = mapped_column(ForeignKey("watchlists.id"))
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
