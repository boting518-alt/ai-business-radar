"""Asynchronous, versioned generation of stored intelligence translations."""

import logging
from hashlib import sha256
from typing import Literal
from uuid import UUID

from ai_business_radar_schemas import IntelligenceTranslationOutput
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.ai import AIClient, default_prompt_version, resolve_prompt
from ..infrastructure.ai.client import AIResponse
from ..infrastructure.ai.errors import (
    AIAuthenticationError,
    AIProviderError,
    AIRateLimitError,
    AIStructuredOutputError,
    AITransientError,
)
from ..infrastructure.database.models import IntelligenceLocalization, Opportunity, Signal
from .intelligence_localization import source_text_hash

logger = logging.getLogger(__name__)

TARGET_LOCALE = "zh-CN"
PROMPT_FAMILY = "intelligence-translation/zh-CN"
PROMPT_VERSION = default_prompt_version(PROMPT_FAMILY)
TRANSLATION_VERSION = f"translation-zh-CN-{PROMPT_VERSION}"
PROMPT_PATH = resolve_prompt(PROMPT_FAMILY, PROMPT_VERSION).path
ENTITY_FIELDS = {
    "signal": ("statement", "evidence_text"),
    "opportunity": ("name", "one_line_thesis", "problem", "solution"),
}

EntityType = Literal["signal", "opportunity"]
BatchEntityType = Literal["signals", "opportunities", "all"]


class TranslationEntityNotFoundError(RuntimeError):
    pass


class UnsupportedTranslationFieldError(ValueError):
    pass


class InvalidTranslationOutputError(RuntimeError):
    pass


class PermanentTranslationError(RuntimeError):
    pass


class TranslationRequest(BaseModel):
    entity_type: EntityType
    entity_id: UUID
    target_locale: Literal["zh-CN"] = Field(default="zh-CN", alias="locale")
    force: bool = False
    fields: list[str] | None = None
    dry_run: bool = False

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_fields(self) -> "TranslationRequest":
        if self.fields is not None:
            requested = set(self.fields)
            allowed = set(ENTITY_FIELDS[self.entity_type])
            if not requested or len(requested) != len(self.fields) or not requested <= allowed:
                raise ValueError("fields must be unique supported fields for the entity type")
        return self


class TranslationBatchRequest(BaseModel):
    entity_type: BatchEntityType = "all"
    target_locale: Literal["zh-CN"] = Field(default="zh-CN", alias="locale")
    limit: int = Field(default=20, ge=1, le=50)
    force: bool = False
    only_missing: bool = True
    only_stale: bool = False
    dry_run: bool = False

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def compatible_selection(self) -> "TranslationBatchRequest":
        if self.only_missing and self.only_stale:
            raise ValueError("only_missing and only_stale cannot both be true")
        return self


class TranslationFieldPlan(BaseModel):
    field_name: str
    state: Literal["current", "missing", "stale"]
    source_text_hash: str
    would_translate: bool
    reason: str


class TranslationResult(BaseModel):
    entity_type: EntityType
    entity_id: UUID
    target_locale: Literal["zh-CN"]
    translated_fields: list[str] = Field(default_factory=list)
    reused_fields: list[str] = Field(default_factory=list)
    skipped_fields: list[str] = Field(default_factory=list)
    failed_fields: list[str] = Field(default_factory=list)
    translation_version: str = TRANSLATION_VERSION
    provider: str
    model: str
    prompt_hash: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    dry_run: bool = False
    plan: list[TranslationFieldPlan] = Field(default_factory=list)


class TranslationBatchResult(BaseModel):
    requested: int
    processed: int
    translated: int
    reused: int
    results: list[TranslationResult]


class IntelligenceTranslationService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        ai_client: AIClient,
        *,
        provider: str,
        model: str,
    ) -> None:
        self._sessions = sessions
        self._ai = ai_client
        self._provider = provider
        self._model = model

    async def translate_entity(self, request: TranslationRequest) -> TranslationResult:
        canonical = await self._load_canonical(request.entity_type, request.entity_id)
        fields = request.fields or list(ENTITY_FIELDS[request.entity_type])
        canonical = {field: canonical[field] for field in fields if canonical.get(field)}
        existing = await self._existing(request.entity_type, request.entity_id, fields)
        plan = self._plan(canonical, existing, request.force)
        pending = [item.field_name for item in plan if item.would_translate]
        reused = [
            item.field_name for item in plan if item.state == "current" and not item.would_translate
        ]
        skipped = [field for field in fields if field not in canonical]
        logger.info(
            "translation_requested entity_type=%s entity_id=%s locale=%s field_count=%s "
            "translation_version=%s",
            request.entity_type,
            request.entity_id,
            request.target_locale,
            len(pending),
            TRANSLATION_VERSION,
        )
        base = dict(
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            target_locale=request.target_locale,
            reused_fields=reused,
            skipped_fields=skipped,
            translation_version=TRANSLATION_VERSION,
            provider=self._provider,
            model=self._model,
            dry_run=request.dry_run,
            plan=plan,
        )
        if request.dry_run or not pending:
            event = "translation_reused" if not pending else "translation_dry_run"
            logger.info(
                "%s entity_type=%s entity_id=%s", event, request.entity_type, request.entity_id
            )
            return TranslationResult(translated_fields=[], **base)

        prompt = PROMPT_PATH.read_text(encoding="utf-8")
        prompt_hash = sha256(prompt.encode()).hexdigest()
        try:
            response = await self._ai.structured_generate(
                task_type="intelligence_translation",
                model=self._model,
                system_prompt=prompt,
                input_data={
                    "canonical_locale": "en-US",
                    "target_locale": request.target_locale,
                    "entity_type": request.entity_type,
                    "fields": [
                        {"field_name": field, "source_text": canonical[field]} for field in pending
                    ],
                },
                output_model=IntelligenceTranslationOutput,
            )
            output = IntelligenceTranslationOutput.model_validate(response.parsed)
            translations = {item.field_name: item.translated_text for item in output.translations}
            if set(translations) != set(pending):
                raise InvalidTranslationOutputError(
                    "translation output fields must exactly match requested fields"
                )
            await self._persist(request, canonical, translations, response, prompt_hash)
        except (AITransientError, AIRateLimitError):
            logger.exception(
                "translation_failed entity_type=%s entity_id=%s locale=%s field_count=%s "
                "translation_version=%s",
                request.entity_type,
                request.entity_id,
                request.target_locale,
                len(pending),
                TRANSLATION_VERSION,
            )
            raise
        except (
            AIAuthenticationError,
            AIStructuredOutputError,
            AIProviderError,
            InvalidTranslationOutputError,
        ) as error:
            logger.exception(
                "translation_failed entity_type=%s entity_id=%s locale=%s field_count=%s "
                "translation_version=%s",
                request.entity_type,
                request.entity_id,
                request.target_locale,
                len(pending),
                TRANSLATION_VERSION,
            )
            raise PermanentTranslationError("translation failed permanently") from error
        logger.info(
            "translation_generated entity_type=%s entity_id=%s locale=%s field_count=%s "
            "translation_version=%s",
            request.entity_type,
            request.entity_id,
            request.target_locale,
            len(pending),
            TRANSLATION_VERSION,
        )
        return TranslationResult(
            translated_fields=pending,
            prompt_hash=prompt_hash,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            **base,
        )

    async def translate_batch(self, request: TranslationBatchRequest) -> TranslationBatchResult:
        targets = await self._batch_targets(request)
        results = [
            await self.translate_entity(
                TranslationRequest(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    locale=request.target_locale,
                    force=request.force,
                    dry_run=request.dry_run,
                )
            )
            for entity_type, entity_id in targets
        ]
        return TranslationBatchResult(
            requested=request.limit,
            processed=len(results),
            translated=sum(bool(item.translated_fields) for item in results),
            reused=sum(
                not item.translated_fields and not any(plan.would_translate for plan in item.plan)
                for item in results
            ),
            results=results,
        )

    async def _load_canonical(
        self, entity_type: EntityType, entity_id: UUID
    ) -> dict[str, str | None]:
        model = Signal if entity_type == "signal" else Opportunity
        async with self._sessions() as session:
            entity = await session.get(model, entity_id)
        if entity is None:
            raise TranslationEntityNotFoundError(f"{entity_type} was not found")
        return {field: getattr(entity, field) for field in ENTITY_FIELDS[entity_type]}

    async def _existing(self, entity_type: EntityType, entity_id: UUID, fields: list[str]):
        async with self._sessions() as session:
            return list(
                await session.scalars(
                    select(IntelligenceLocalization)
                    .where(
                        IntelligenceLocalization.entity_type == entity_type,
                        IntelligenceLocalization.entity_id == entity_id,
                        IntelligenceLocalization.locale == TARGET_LOCALE,
                        IntelligenceLocalization.field_name.in_(fields),
                    )
                    .order_by(IntelligenceLocalization.updated_at.desc())
                )
            )

    @staticmethod
    def _plan(canonical, existing, force: bool) -> list[TranslationFieldPlan]:
        plan = []
        for field, value in canonical.items():
            if not value:
                continue
            digest = source_text_hash(value)
            current = next(
                (
                    row
                    for row in existing
                    if row.field_name == field
                    and row.source_text_hash == digest
                    and row.translation_version == TRANSLATION_VERSION
                    and row.status == "current"
                ),
                None,
            )
            related = any(row.field_name == field for row in existing)
            state = "current" if current else "stale" if related else "missing"
            would_translate = force or current is None
            reason = "forced" if force else "reusable" if current else state
            plan.append(
                TranslationFieldPlan(
                    field_name=field,
                    state=state,
                    source_text_hash=digest,
                    would_translate=would_translate,
                    reason=reason,
                )
            )
        return plan

    async def _persist(
        self, request, canonical, translations, response: AIResponse, prompt_hash: str
    ) -> None:
        async with self._sessions() as session, session.begin():
            for field, translated_text in translations.items():
                digest = source_text_hash(canonical[field])
                await session.execute(
                    update(IntelligenceLocalization)
                    .where(
                        IntelligenceLocalization.entity_type == request.entity_type,
                        IntelligenceLocalization.entity_id == request.entity_id,
                        IntelligenceLocalization.field_name == field,
                        IntelligenceLocalization.locale == request.target_locale,
                        IntelligenceLocalization.status == "current",
                        ~(
                            (IntelligenceLocalization.source_text_hash == digest)
                            & (IntelligenceLocalization.translation_version == TRANSLATION_VERSION)
                        ),
                    )
                    .values(status="stale")
                )
                statement = insert(IntelligenceLocalization).values(
                    entity_type=request.entity_type,
                    entity_id=request.entity_id,
                    field_name=field,
                    locale=request.target_locale,
                    translated_text=translated_text,
                    source_text_hash=digest,
                    translation_version=TRANSLATION_VERSION,
                    translation_provider=response.provider,
                    translation_model=response.model,
                    prompt_hash=prompt_hash,
                    provider_request_id=response.provider_request_id,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    status="current",
                )
                await session.execute(
                    statement.on_conflict_do_update(
                        constraint="uq_intelligence_localizations_projection",
                        set_={
                            "translated_text": statement.excluded.translated_text,
                            "translation_provider": statement.excluded.translation_provider,
                            "translation_model": statement.excluded.translation_model,
                            "prompt_hash": statement.excluded.prompt_hash,
                            "provider_request_id": statement.excluded.provider_request_id,
                            "input_tokens": statement.excluded.input_tokens,
                            "output_tokens": statement.excluded.output_tokens,
                            "status": "current",
                            "updated_at": statement.excluded.updated_at,
                        },
                    )
                )

    async def _batch_targets(self, request: TranslationBatchRequest):
        targets: list[tuple[EntityType, UUID]] = []
        needs_projection_filter = not request.force and (request.only_missing or request.only_stale)
        async with self._sessions() as session:
            if request.entity_type in ("signals", "all"):
                query = (
                    select(Signal.id)
                    .where(Signal.status == "active")
                    .order_by(Signal.observed_at.desc().nulls_last(), Signal.id)
                )
                if not needs_projection_filter:
                    query = query.limit(request.limit)
                ids = list(await session.scalars(query))
                targets.extend(("signal", item) for item in ids)
            remaining = request.limit if needs_projection_filter else request.limit - len(targets)
            if remaining and request.entity_type in ("opportunities", "all"):
                query = (
                    select(Opportunity.id)
                    .where(Opportunity.status == "active")
                    .order_by(Opportunity.last_activity_at.desc(), Opportunity.id)
                )
                if not needs_projection_filter:
                    query = query.limit(remaining)
                ids = list(await session.scalars(query))
                targets.extend(("opportunity", item) for item in ids)
        if needs_projection_filter:
            selected = []
            for target in targets:
                canonical = await self._load_canonical(*target)
                fields = [field for field, value in canonical.items() if value]
                plan = self._plan(canonical, await self._existing(*target, fields), request.force)
                if request.only_missing and any(item.state == "missing" for item in plan):
                    selected.append(target)
                elif request.only_stale and any(item.state == "stale" for item in plan):
                    selected.append(target)
                if len(selected) == request.limit:
                    break
            targets = selected
        return targets[: request.limit]
