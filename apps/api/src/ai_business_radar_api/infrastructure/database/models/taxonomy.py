from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class IndustryTaxonomyNode(Base):
    __tablename__ = "industry_taxonomy_nodes"
    code: Mapped[str] = mapped_column(Text, primary_key=True)
    parent_code: Mapped[str | None] = mapped_column(ForeignKey("industry_taxonomy_nodes.code"))
    canonical_name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean)
    taxonomy_version: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CustomerTaxonomyNode(Base):
    __tablename__ = "customer_taxonomy_nodes"
    code: Mapped[str] = mapped_column(Text, primary_key=True)
    parent_code: Mapped[str | None] = mapped_column(ForeignKey("customer_taxonomy_nodes.code"))
    canonical_name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean)
    taxonomy_version: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TaxonomyLocalization(Base):
    __tablename__ = "taxonomy_localizations"
    taxonomy_type: Mapped[str] = mapped_column(primary_key=True)
    taxonomy_code: Mapped[str] = mapped_column(primary_key=True)
    locale: Mapped[str] = mapped_column(primary_key=True)
    label: Mapped[str]
    short_label: Mapped[str | None]
    description: Mapped[str | None] = mapped_column(Text)


class TaxonomyAlias(Base):
    __tablename__ = "taxonomy_aliases"
    taxonomy_type: Mapped[str] = mapped_column(primary_key=True)
    alias_text_normalized: Mapped[str] = mapped_column(primary_key=True)
    taxonomy_code: Mapped[str] = mapped_column(primary_key=True)
    locale: Mapped[str | None]
    match_type: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SignalTaxonomyMapping(Base):
    __tablename__ = "signal_taxonomy_mappings"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    signal_id: Mapped[UUID] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"))
    taxonomy_type: Mapped[str]
    taxonomy_code: Mapped[str]
    mapping_source: Mapped[str]
    mapping_confidence: Mapped[Decimal | None] = mapped_column(Numeric)
    mapping_status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OpportunityTaxonomyMapping(Base):
    __tablename__ = "opportunity_taxonomy_mappings"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"))
    taxonomy_type: Mapped[str]
    taxonomy_code: Mapped[str]
    mapping_source: Mapped[str]
    mapping_confidence: Mapped[Decimal | None] = mapped_column(Numeric)
    mapping_status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
