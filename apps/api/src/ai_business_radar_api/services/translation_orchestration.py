"""Best-effort lifecycle triggers and bounded translation coverage reconciliation."""

import logging
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.ai import default_prompt_version
from ..infrastructure.database.models import (
    IntelligenceLocalization,
    Opportunity,
    ReviewTask,
    Signal,
)
from .intelligence_localization import source_text_hash
from .intelligence_translation import ENTITY_FIELDS, PROMPT_FAMILY, TARGET_LOCALE

logger = logging.getLogger(__name__)

EntityType = Literal["signal", "opportunity"]
CoverageState = Literal["complete", "partial", "missing", "stale", "failed"]


class TranslationEnqueuer(Protocol):
    def enqueue(self, *, queue: str, actor: str, payload: dict) -> str: ...


def current_translation_version() -> str:
    """Resolve the runtime version from the authoritative prompt registry."""
    return f"translation-zh-CN-{default_prompt_version(PROMPT_FAMILY)}"


class TranslationCoverage(BaseModel):
    entity_type: EntityType
    entity_id: UUID
    locale: Literal["zh-CN"] = TARGET_LOCALE
    required_fields: list[str]
    translated_fields: list[str]
    missing_fields: list[str]
    stale_fields: list[str]
    failed_fields: list[str]
    status: CoverageState
    eligible: bool
    translation_version: str


class TranslationReconciliationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    target_locale: Literal["zh-CN"] = Field(default="zh-CN", alias="locale")
    limit: int = Field(default=100, ge=1, le=500)
    dry_run: bool = False


class TranslationReconciliationResult(BaseModel):
    eligible: int
    missing: int
    stale: int
    current: int
    failed: int
    would_enqueue: int
    enqueued: int
    enqueue_failed: int
    coverages: list[TranslationCoverage]
    dry_run: bool


class TranslationCoverageReconciliationService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        enqueuer: TranslationEnqueuer | None,
    ) -> None:
        self._sessions = sessions
        self._enqueuer = enqueuer

    @property
    def queue_configured(self) -> bool:
        return self._enqueuer is not None

    async def coverage(self, entity_type: EntityType, entity_id: UUID) -> TranslationCoverage:
        model = Signal if entity_type == "signal" else Opportunity
        async with self._sessions() as session:
            entity = await session.get(model, entity_id)
            if entity is None:
                raise LookupError(f"{entity_type} was not found")
            eligible = await self._eligible(session, entity_type, entity)
            required = [field for field in ENTITY_FIELDS[entity_type] if getattr(entity, field)]
            rows = list(
                await session.scalars(
                    select(IntelligenceLocalization)
                    .where(
                        IntelligenceLocalization.entity_type == entity_type,
                        IntelligenceLocalization.entity_id == entity_id,
                        IntelligenceLocalization.locale == TARGET_LOCALE,
                        IntelligenceLocalization.field_name.in_(required),
                    )
                    .order_by(IntelligenceLocalization.updated_at.desc())
                )
            )
        version = current_translation_version()
        translated, missing, stale, failed = [], [], [], []
        for field in required:
            digest = source_text_hash(getattr(entity, field))
            related = [row for row in rows if row.field_name == field]
            current = next(
                (
                    row
                    for row in related
                    if row.status == "current"
                    and row.source_text_hash == digest
                    and row.translation_version == version
                ),
                None,
            )
            if current:
                translated.append(field)
            elif any(row.status == "failed" for row in related):
                failed.append(field)
            elif related:
                stale.append(field)
            else:
                missing.append(field)
        if failed:
            status: CoverageState = "failed"
        elif stale:
            status = "stale"
        elif not translated and missing:
            status = "missing"
        elif missing:
            status = "partial"
        else:
            status = "complete"
        return TranslationCoverage(
            entity_type=entity_type,
            entity_id=entity_id,
            required_fields=required,
            translated_fields=translated,
            missing_fields=missing,
            stale_fields=stale,
            failed_fields=failed,
            status=status,
            eligible=eligible,
            translation_version=version,
        )

    async def enqueue_if_required(
        self, entity_type: EntityType, entity_id: UUID, *, reason: str
    ) -> bool:
        coverage = await self.coverage(entity_type, entity_id)
        if not coverage.eligible or coverage.status == "complete":
            logger.info(
                "translation_reconciliation_skip entity_type=%s entity_id=%s locale=%s "
                "translation_version=%s reason=%s",
                entity_type,
                entity_id,
                TARGET_LOCALE,
                coverage.translation_version,
                reason,
            )
            return False
        if self._enqueuer is None:
            return False
        event = {
            "signal_review": "translation_triggered_signal_review",
            "signal_active": "translation_triggered_signal_active",
            "activation_review": "translation_triggered_activation_review",
            "opportunity_active": "translation_triggered_opportunity_active",
        }.get(reason, "translation_reconciliation_enqueue")
        try:
            payload = {
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "locale": TARGET_LOCALE,
            }
            unique = getattr(self._enqueuer, "enqueue_unique", None)
            job_id = (
                unique(
                    queue="intelligence_translation",
                    actor=f"translate_{entity_type}",
                    payload=payload,
                    deduplication_key=(
                        f"translation:{entity_type}:{entity_id}:{TARGET_LOCALE}:"
                        f"{coverage.translation_version}"
                    ),
                )
                if unique
                else self._enqueuer.enqueue(
                    queue="intelligence_translation",
                    actor=f"translate_{entity_type}",
                    payload=payload,
                )
            )
            if job_id is None:
                logger.info(
                    "translation_reconciliation_skip entity_type=%s entity_id=%s locale=%s "
                    "translation_version=%s reason=active_job",
                    entity_type,
                    entity_id,
                    TARGET_LOCALE,
                    coverage.translation_version,
                )
                return False
        except Exception:
            logger.exception(
                "translation_enqueue_failed entity_type=%s entity_id=%s locale=%s "
                "translation_version=%s reason=%s",
                entity_type,
                entity_id,
                TARGET_LOCALE,
                coverage.translation_version,
                reason,
            )
            return False
        logger.info(
            "%s entity_type=%s entity_id=%s locale=%s translation_version=%s reason=%s",
            event,
            entity_type,
            entity_id,
            TARGET_LOCALE,
            coverage.translation_version,
            reason,
        )
        return True

    async def best_effort_enqueue(
        self, entity_type: EntityType, entity_id: UUID, *, reason: str
    ) -> bool:
        """Never let coverage or queue failure escape into a domain lifecycle."""
        try:
            return await self.enqueue_if_required(entity_type, entity_id, reason=reason)
        except Exception:
            logger.exception(
                "translation_enqueue_failed entity_type=%s entity_id=%s locale=%s "
                "translation_version=%s reason=%s",
                entity_type,
                entity_id,
                TARGET_LOCALE,
                current_translation_version(),
                reason,
            )
            return False

    async def reconcile(
        self, request: TranslationReconciliationRequest
    ) -> TranslationReconciliationResult:
        targets = await self._eligible_targets(request.limit)
        coverages = [await self.coverage(kind, entity_id) for kind, entity_id in targets]
        candidates = [item for item in coverages if item.status != "complete"]
        enqueued = 0
        failures = 0
        if not request.dry_run:
            for item in candidates:
                if await self.enqueue_if_required(
                    item.entity_type, item.entity_id, reason="reconciliation"
                ):
                    enqueued += 1
                else:
                    failures += 1
        logger.info(
            "translation_reconciliation_scan locale=%s translation_version=%s eligible=%s "
            "would_enqueue=%s enqueued=%s dry_run=%s",
            TARGET_LOCALE,
            current_translation_version(),
            len(coverages),
            len(candidates),
            enqueued,
            request.dry_run,
        )
        return TranslationReconciliationResult(
            eligible=len(coverages),
            missing=sum(item.status in {"missing", "partial"} for item in coverages),
            stale=sum(item.status == "stale" for item in coverages),
            current=sum(item.status == "complete" for item in coverages),
            failed=sum(item.status == "failed" for item in coverages),
            would_enqueue=len(candidates),
            enqueued=enqueued,
            enqueue_failed=failures,
            coverages=coverages,
            dry_run=request.dry_run,
        )

    async def _eligible_targets(self, limit: int) -> list[tuple[EntityType, UUID]]:
        async with self._sessions() as session:
            signal_ids = list(
                await session.scalars(
                    select(Signal.id)
                    .where(Signal.status.in_(("review", "active")))
                    .order_by(Signal.updated_at.desc(), Signal.id)
                    .limit(limit)
                )
            )
            open_activation = exists().where(
                ReviewTask.target_type == "opportunity",
                ReviewTask.target_id == Opportunity.id,
                ReviewTask.review_type == "opportunity_activation",
                ReviewTask.status.in_(("pending", "in_review")),
            )
            opportunity_ids = list(
                await session.scalars(
                    select(Opportunity.id)
                    .where(
                        (Opportunity.status == "active")
                        | ((Opportunity.status == "candidate") & open_activation)
                    )
                    .order_by(Opportunity.updated_at.desc(), Opportunity.id)
                    .limit(limit)
                )
            )
        targets: list[tuple[EntityType, UUID]] = []
        for index in range(max(len(signal_ids), len(opportunity_ids))):
            if index < len(signal_ids):
                targets.append(("signal", signal_ids[index]))
            if index < len(opportunity_ids):
                targets.append(("opportunity", opportunity_ids[index]))
            if len(targets) >= limit:
                break
        return targets[:limit]

    @staticmethod
    async def _eligible(session: AsyncSession, entity_type: EntityType, entity) -> bool:
        if entity_type == "signal":
            return entity.status in {"review", "active"}
        if entity.status == "active":
            return True
        if entity.status != "candidate":
            return False
        return bool(
            await session.scalar(
                select(
                    exists().where(
                        ReviewTask.target_type == "opportunity",
                        ReviewTask.target_id == entity.id,
                        ReviewTask.review_type == "opportunity_activation",
                        ReviewTask.status.in_(("pending", "in_review")),
                    )
                )
            )
        )
