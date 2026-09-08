from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from ai_business_radar_schemas import (
    BusinessSignalExtractorOutput,
    SignalCreate,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.ai import (
    AIClient,
    AIStructuredOutputError,
    default_prompt_version,
    resolve_prompt,
)
from ..infrastructure.ai.errors import AIProviderError
from ..infrastructure.database.models import Channel, Video
from ..infrastructure.database.repositories import (
    AIExtractionRepository,
    SignalRepository,
    VideoRepository,
)
from .relevance_filter import canonical_input_hash
from .translation_orchestration import TranslationCoverageReconciliationService

TASK_TYPE = "signal_extractor"
PROMPT_TASK = "signal-extractor"
PROMPT_VERSION = default_prompt_version(PROMPT_TASK)


class SignalVideoNotFoundError(RuntimeError):
    pass


class SignalVideoNotEligibleError(RuntimeError):
    pass


class SignalRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force: bool = False


class SignalBatchRequest(SignalRunRequest):
    limit: int = Field(default=20, ge=1, le=100)


class SignalItemResult(BaseModel):
    video_id: UUID
    extraction_id: UUID | None
    status: str
    signals_created: int = 0
    reused: bool = False


class SignalBatchResult(BaseModel):
    requested: int
    processed: int
    reused: int
    signals_created: int
    failed: int
    items: list[SignalItemResult]


class BusinessSignalExtractionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ai_client: AIClient,
        *,
        provider: str,
        model: str,
        prompt_version: str = PROMPT_VERSION,
        translation_orchestrator: TranslationCoverageReconciliationService | None = None,
    ) -> None:
        self._sessions = session_factory
        self._ai = ai_client
        self._provider = provider
        self._model = model
        self._prompt = resolve_prompt(PROMPT_TASK, prompt_version)
        self._translation = translation_orchestrator

    async def extract(self, video_id: UUID, *, force: bool = False) -> SignalItemResult:
        video, channel = await self._load_video(video_id, force=force)
        input_data = self._build_input(video, channel)
        prompt = self._prompt.content
        input_hash = canonical_input_hash(
            input_data, prompt_version=self._prompt.version, task_type=TASK_TYPE
        )
        if not force:
            reused = await self._find_completed(video_id, input_hash)
            if reused is not None:
                async with self._sessions() as session:
                    count = await SignalRepository(session).count_for_extraction(reused.id)
                return SignalItemResult(
                    video_id=video_id,
                    extraction_id=reused.id,
                    status="completed",
                    signals_created=count,
                    reused=True,
                )

        extraction_id = await self._start(video_id, input_hash)
        try:
            response = await self._ai.structured_generate(
                task_type=TASK_TYPE,
                model=self._model,
                system_prompt=prompt,
                input_data=input_data,
                output_model=BusinessSignalExtractorOutput,
            )
        except AIStructuredOutputError as error:
            await self._fail(extraction_id, video_id, invalid=True, raw=error.raw_output)
            return SignalItemResult(
                video_id=video_id, extraction_id=extraction_id, status="invalid_output"
            )
        except AIProviderError:
            await self._fail(extraction_id, video_id, invalid=False)
            return SignalItemResult(video_id=video_id, extraction_id=extraction_id, status="failed")

        try:
            parsed = BusinessSignalExtractorOutput.model_validate(response.parsed)
        except ValidationError:
            await self._fail(extraction_id, video_id, invalid=True, raw=response.raw_output)
            return SignalItemResult(
                video_id=video_id, extraction_id=extraction_id, status="invalid_output"
            )

        try:
            count, signal_ids = await self._complete(extraction_id, video, parsed, response)
        except SQLAlchemyError:
            await self._fail(
                extraction_id,
                video_id,
                invalid=False,
                error="signal_persistence_failed",
            )
            return SignalItemResult(video_id=video_id, extraction_id=extraction_id, status="failed")
        if self._translation is not None:
            for signal_id in signal_ids:
                await self._translation.best_effort_enqueue(
                    "signal", signal_id, reason="signal_review"
                )
        return SignalItemResult(
            video_id=video_id,
            extraction_id=extraction_id,
            status="completed",
            signals_created=count,
        )

    async def extract_batch(self, request: SignalBatchRequest) -> SignalBatchResult:
        async with self._sessions() as session:
            videos = await VideoRepository(session).list_queued_for_signal_extraction(
                limit=request.limit
            )
        items = [await self.extract(video.id, force=request.force) for video in videos]
        return SignalBatchResult(
            requested=len(items),
            processed=sum(item.status == "completed" for item in items),
            reused=sum(item.reused for item in items),
            signals_created=sum(item.signals_created for item in items if not item.reused),
            failed=sum(item.status in {"failed", "invalid_output"} for item in items),
            items=items,
        )

    async def _load_video(self, video_id: UUID, *, force: bool) -> tuple[Video, Channel]:
        async with self._sessions() as session:
            video = await session.get(Video, video_id)
            if video is None:
                raise SignalVideoNotFoundError("Canonical video was not found")
            if video.processing_status != "queued" and not force:
                raise SignalVideoNotEligibleError("Video is not queued for signal extraction")
            channel = await session.get(Channel, video.channel_id)
            if channel is None:
                raise SignalVideoNotFoundError("Canonical channel was not found")
            return video, channel

    @staticmethod
    def _build_input(video: Video, channel: Channel) -> dict:
        return {
            "video": {
                "youtube_video_id": video.youtube_video_id,
                "title": video.title,
                "description": video.description,
                "published_at": video.published_at.isoformat(),
                "duration_seconds": video.duration_seconds,
                "language": video.language,
                "statistics": {
                    "view_count": video.current_view_count,
                    "like_count": video.current_like_count,
                    "comment_count": video.current_comment_count,
                },
            },
            "channel": {"name": channel.name, "channel_type": channel.channel_type},
        }

    async def _find_completed(self, video_id: UUID, input_hash: str):
        async with self._sessions() as session:
            return await AIExtractionRepository(session).find_completed_identity(
                source_id=video_id,
                task_type=TASK_TYPE,
                prompt_version=self._prompt.version,
                model=self._model,
                input_hash=input_hash,
            )

    async def _start(self, video_id: UUID, input_hash: str) -> UUID:
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            extraction = await AIExtractionRepository(session).create_pending(
                source_type="video",
                source_id=video_id,
                video_id=video_id,
                task_type=TASK_TYPE,
                provider=self._provider,
                model=self._model,
                prompt_version=self._prompt.version,
                prompt_hash=self._prompt.sha256,
                input_hash=input_hash,
            )
            await AIExtractionRepository(session).mark_running(extraction.id, now)
            await VideoRepository(session).update_processing_status(video_id, "processing")
            return extraction.id

    async def _complete(self, extraction_id, video, parsed, response) -> tuple[int, list[UUID]]:
        now = datetime.now(UTC)
        confidences = [Decimal(str(item.confidence)) for item in parsed.signals]
        confidence = sum(confidences, Decimal(0)) / len(confidences) if parsed.signals else None
        rows = [
            self._signal_values(video, extraction_id, parsed, item, now) for item in parsed.signals
        ]
        async with self._sessions() as session, session.begin():
            created = await SignalRepository(session).create_many(rows)
            await AIExtractionRepository(session).mark_completed(
                extraction_id,
                completed_at=now,
                raw_output=response.raw_output,
                parsed_output=parsed.model_dump(mode="json"),
                confidence=confidence,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.total_tokens,
                provider_request_id=response.provider_request_id,
            )
            await VideoRepository(session).update_processing_status(video.id, "queued")
        return len(created), [item.id for item in created]

    @staticmethod
    def _signal_values(video, extraction_id, parsed, item, now) -> dict:
        pricing = parsed.pricing if item.type.value == "pricing" else None
        candidate = SignalCreate(
            source_type="video",
            source_id=video.id,
            video_id=video.id,
            ai_extraction_id=extraction_id,
            signal_type=item.type,
            statement=item.statement,
            industry=parsed.industry,
            customer_type=parsed.customer,
            problem=parsed.problem,
            solution=parsed.solution,
            business_model=parsed.business_model,
            price_min=Decimal(str(pricing.min)) if pricing and pricing.min is not None else None,
            price_max=Decimal(str(pricing.max)) if pricing and pricing.max is not None else None,
            price_currency=pricing.currency if pricing else None,
            price_period=pricing.period if pricing else None,
            technology=parsed.technology or None,
            distribution_channels=parsed.distribution or None,
            claim_status=item.claim_status,
            confidence=Decimal(str(item.confidence)),
            observed_at=video.published_at,
            status="review",
        )
        values = candidate.model_dump(mode="python")
        values.update(evidence_text=item.evidence, created_at=now, updated_at=now)
        return values

    async def _fail(
        self, extraction_id, video_id, *, invalid: bool, raw=None, error: str | None = None
    ) -> None:
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            repository = AIExtractionRepository(session)
            if invalid:
                await repository.mark_invalid(
                    extraction_id,
                    completed_at=now,
                    error="structured_output_invalid",
                    raw_output=raw,
                )
            else:
                await repository.mark_failed(
                    extraction_id,
                    completed_at=now,
                    error=error or "ai_provider_request_failed",
                )
            await VideoRepository(session).update_processing_status(
                video_id, "review" if invalid else "failed"
            )
