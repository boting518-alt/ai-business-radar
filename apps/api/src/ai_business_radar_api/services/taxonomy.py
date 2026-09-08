import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.database.models import (
    CustomerTaxonomyNode,
    IndustryTaxonomyNode,
    Opportunity,
    OpportunityTaxonomyMapping,
    Signal,
    SignalTaxonomyMapping,
    TaxonomyAlias,
    TaxonomyLocalization,
)

TaxonomyType = Literal["industry", "customer"]
EntityType = Literal["signal", "opportunity"]


class TaxonomyNotFoundError(RuntimeError):
    pass


class TaxonomyLabel(BaseModel):
    code: str
    parent_code: str | None
    canonical_name: str
    label: str
    taxonomy_version: str


class TaxonomyMappingResult(BaseModel):
    entity_type: EntityType
    entity_id: UUID
    taxonomy_type: TaxonomyType
    original_text: str | None
    normalized_text: str | None
    taxonomy_code: str | None
    status: Literal["mapped", "unmapped", "review_required"]
    source: str
    confidence: Decimal | None
    reason: str


class ManualTaxonomyRequest(BaseModel):
    taxonomy_type: TaxonomyType
    taxonomy_code: str | None = None
    action: Literal["set", "clear"] = "set"


def normalize_alias(value: str) -> str:
    return re.sub(r"[^\w\s-]", " ", value.strip().lower()).replace("_", " ").strip()


class TaxonomyMappingService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def nodes(self, taxonomy_type: TaxonomyType, locale: str) -> list[TaxonomyLabel]:
        model = IndustryTaxonomyNode if taxonomy_type == "industry" else CustomerTaxonomyNode
        async with self._sessions() as session:
            nodes = list(
                await session.scalars(
                    select(model).where(model.is_active.is_(True)).order_by(model.code)
                )
            )
            labels = list(
                await session.scalars(
                    select(TaxonomyLocalization).where(
                        TaxonomyLocalization.taxonomy_type == taxonomy_type,
                        TaxonomyLocalization.locale.in_([locale, "en-US"]),
                    )
                )
            )
        by_key = {(row.taxonomy_code, row.locale): row.label for row in labels}
        return [
            TaxonomyLabel(
                code=node.code,
                parent_code=node.parent_code,
                canonical_name=node.canonical_name,
                label=by_key.get((node.code, locale))
                or by_key.get((node.code, "en-US"))
                or node.canonical_name,
                taxonomy_version=node.taxonomy_version,
            )
            for node in nodes
        ]

    async def map_text(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        taxonomy_type: TaxonomyType,
        text: str | None,
    ) -> TaxonomyMappingResult:
        normalized = normalize_alias(text) if text else None
        async with self._sessions() as session:
            alias = (
                await session.scalar(
                    select(TaxonomyAlias).where(
                        TaxonomyAlias.taxonomy_type == taxonomy_type,
                        TaxonomyAlias.alias_text_normalized == normalized,
                    )
                )
                if normalized
                else None
            )
        return TaxonomyMappingResult(
            entity_type=entity_type,
            entity_id=entity_id,
            taxonomy_type=taxonomy_type,
            original_text=text,
            normalized_text=normalized,
            taxonomy_code=alias.taxonomy_code if alias else None,
            status="mapped" if alias else "unmapped",
            source="rule",
            confidence=Decimal("1") if alias else None,
            reason="normalized_exact_alias" if alias else "no_explicit_alias",
        )

    async def apply_rule(
        self, entity_type: EntityType, entity_id: UUID, taxonomy_type: TaxonomyType
    ) -> TaxonomyMappingResult:
        entity_model, mapping_model, id_field = self._models(entity_type)
        async with self._sessions() as session:
            entity = await session.get(entity_model, entity_id)
        if entity is None:
            raise TaxonomyNotFoundError("Entity was not found")
        original = entity.industry if taxonomy_type == "industry" else entity.customer_type
        result = await self.map_text(entity_type, entity_id, taxonomy_type, original)
        if result.taxonomy_code:
            await self.set_mapping(
                entity_type, entity_id, taxonomy_type, result.taxonomy_code, "rule"
            )
        return result

    async def set_mapping(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        taxonomy_type: TaxonomyType,
        code: str,
        source: str = "manual",
    ) -> None:
        entity_model, mapping_model, id_field = self._models(entity_type)
        node_model = IndustryTaxonomyNode if taxonomy_type == "industry" else CustomerTaxonomyNode
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            if (
                await session.get(entity_model, entity_id) is None
                or await session.get(node_model, code) is None
            ):
                raise TaxonomyNotFoundError("Entity or taxonomy code was not found")
            existing = await session.scalar(
                select(mapping_model).where(
                    getattr(mapping_model, id_field) == entity_id,
                    mapping_model.taxonomy_type == taxonomy_type,
                    mapping_model.mapping_status == "active",
                )
            )
            if existing and existing.taxonomy_code == code:
                return
            if existing:
                await session.execute(
                    update(mapping_model)
                    .where(mapping_model.id == existing.id)
                    .values(mapping_status="rejected", updated_at=now)
                )
            session.add(
                mapping_model(
                    **{id_field: entity_id},
                    taxonomy_type=taxonomy_type,
                    taxonomy_code=code,
                    mapping_source=source,
                    mapping_confidence=Decimal("1") if source == "rule" else None,
                    mapping_status="active",
                    created_at=now,
                    updated_at=now,
                )
            )

    async def clear_mapping(
        self, entity_type: EntityType, entity_id: UUID, taxonomy_type: TaxonomyType
    ) -> None:
        _, mapping_model, id_field = self._models(entity_type)
        async with self._sessions() as session, session.begin():
            await session.execute(
                update(mapping_model)
                .where(
                    getattr(mapping_model, id_field) == entity_id,
                    mapping_model.taxonomy_type == taxonomy_type,
                    mapping_model.mapping_status == "active",
                )
                .values(mapping_status="rejected", updated_at=datetime.now(UTC))
            )

    @staticmethod
    def _models(entity_type: EntityType):
        return (
            (Signal, SignalTaxonomyMapping, "signal_id")
            if entity_type == "signal"
            else (Opportunity, OpportunityTaxonomyMapping, "opportunity_id")
        )
