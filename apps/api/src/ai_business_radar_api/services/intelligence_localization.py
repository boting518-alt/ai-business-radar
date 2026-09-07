"""Deterministic reads of stored intelligence localization projections."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..infrastructure.database.models import IntelligenceLocalization

EntityType = Literal["signal", "opportunity"]
Locale = Literal["zh-CN", "en-US"]


@dataclass(frozen=True)
class LocalizedText:
    text: str | None
    original_text: str | None
    localized: bool = False
    stale: bool = False


def source_text_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


class IntelligenceLocalizationService:
    """Resolve projections without generating translations or blocking reads."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def localize(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        locale: Locale,
        canonical_fields: dict[str, str | None],
    ) -> dict[str, LocalizedText]:
        result = {
            field: LocalizedText(text=value, original_text=value)
            for field, value in canonical_fields.items()
        }
        populated = {field: value for field, value in canonical_fields.items() if value}
        if locale == "en-US" or not populated:
            return result

        rows = list(
            await self._session.scalars(
                select(IntelligenceLocalization)
                .where(
                    IntelligenceLocalization.entity_type == entity_type,
                    IntelligenceLocalization.entity_id == entity_id,
                    IntelligenceLocalization.locale == locale,
                    IntelligenceLocalization.field_name.in_(populated),
                )
                .order_by(
                    IntelligenceLocalization.updated_at.desc(),
                    IntelligenceLocalization.id.desc(),
                )
            )
        )
        for field, canonical in populated.items():
            candidates = [row for row in rows if row.field_name == field]
            current = next(
                (
                    row
                    for row in candidates
                    if row.status == "current"
                    and row.source_text_hash == source_text_hash(canonical)
                ),
                None,
            )
            if current is not None:
                result[field] = LocalizedText(
                    text=current.translated_text,
                    original_text=canonical,
                    localized=True,
                )
            elif candidates:
                result[field] = LocalizedText(
                    text=canonical,
                    original_text=canonical,
                    stale=True,
                )
        return result
