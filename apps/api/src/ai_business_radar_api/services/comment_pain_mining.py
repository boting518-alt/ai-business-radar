from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from ai_business_radar_schemas import CommentPainMinerOutput, SignalCreate
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.ai import (
    AIClient,
    AIStructuredOutputError,
    default_prompt_version,
    load_prompt,
)
from ..infrastructure.ai.errors import AIProviderError
from ..infrastructure.database.models import Channel, Comment, Video
from ..infrastructure.database.repositories import (
    AIExtractionRepository,
    CommentRepository,
    SignalRepository,
)
from .relevance_filter import canonical_input_hash
from .translation_orchestration import TranslationCoverageReconciliationService

TASK_TYPE = "comment_pain_miner"
PROMPT_TASK = "comment-pain-miner"
PROMPT_VERSION = default_prompt_version(PROMPT_TASK)
EVIDENCE_LIMIT = 2000

CATEGORY_TO_SIGNAL_TYPE = {
    "existing pain": "pain",
    "current workaround": "workflow",
    "purchase intent": "purchase_intent",
    "willingness to pay": "purchase_intent",
    "existing spending": "pricing",
    "feature request": "feature_request",
    "adoption blocker": "complaint",
    "competitor usage": "competition",
    "workflow inefficiency": "workflow",
    "unmet need": "demand",
}


class CommentNotFoundError(RuntimeError):
    pass


class InvalidCommentPainOutput(RuntimeError):
    pass


class CommentPainRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force: bool = False


class CommentPainBatchRequest(CommentPainRunRequest):
    limit: int = Field(default=50, ge=1, le=200)
    comment_ids: list[UUID] | None = None


class CommentPainItemResult(BaseModel):
    comment_id: UUID
    extraction_id: UUID | None
    status: str
    mined: bool = False
    signals_created: int = 0
    reused: bool = False


class CommentPainBatchResult(BaseModel):
    requested: int
    processed: int
    reused: int
    signals_created: int
    empty_results: int
    failed: int
    items: list[CommentPainItemResult]


class CommentPainMiningService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ai_client: AIClient,
        *,
        provider: str,
        model: str,
        translation_orchestrator: TranslationCoverageReconciliationService | None = None,
    ) -> None:
        self._sessions = session_factory
        self._ai = ai_client
        self._provider = provider
        self._model = model
        self._translation = translation_orchestrator

    async def mine(self, comment_id: UUID, *, force: bool = False) -> CommentPainItemResult:
        comment, video, channel = await self._load_context(comment_id)
        input_data = self._build_input(comment, video, channel)
        prompt = load_prompt(PROMPT_TASK, PROMPT_VERSION)
        input_hash = canonical_input_hash(
            input_data, prompt_version=PROMPT_VERSION, task_type=TASK_TYPE
        )
        if not force:
            reused = await self._find_completed(comment_id, input_hash)
            if reused is not None:
                async with self._sessions() as session:
                    count = await SignalRepository(session).count_for_extraction(reused.id)
                return CommentPainItemResult(
                    comment_id=comment_id,
                    extraction_id=reused.id,
                    status="completed",
                    mined=True,
                    signals_created=count,
                    reused=True,
                )

        extraction_id = await self._start(comment_id, input_hash)
        try:
            response = await self._ai.structured_generate(
                task_type=TASK_TYPE,
                model=self._model,
                system_prompt=prompt,
                input_data=input_data,
                output_model=CommentPainMinerOutput,
            )
        except AIStructuredOutputError as error:
            await self._fail(extraction_id, invalid=True, raw=error.raw_output)
            return self._invalid_result(comment_id, extraction_id)
        except AIProviderError:
            await self._fail(extraction_id, invalid=False)
            return CommentPainItemResult(
                comment_id=comment_id, extraction_id=extraction_id, status="failed"
            )

        try:
            parsed = CommentPainMinerOutput.model_validate(response.parsed)
            self._validate_output_source(parsed, comment_id)
            rows = self._signal_values(comment, extraction_id, parsed)
        except (ValidationError, InvalidCommentPainOutput):
            await self._fail(extraction_id, invalid=True, raw=response.raw_output)
            return self._invalid_result(comment_id, extraction_id)

        try:
            count, signal_ids = await self._complete(extraction_id, parsed, response, rows)
        except SQLAlchemyError:
            await self._fail(extraction_id, invalid=False, error="signal_persistence_failed")
            return CommentPainItemResult(
                comment_id=comment_id, extraction_id=extraction_id, status="failed"
            )
        if self._translation is not None:
            for signal_id in signal_ids:
                await self._translation.best_effort_enqueue(
                    "signal", signal_id, reason="signal_review"
                )
        return CommentPainItemResult(
            comment_id=comment_id,
            extraction_id=extraction_id,
            status="completed",
            mined=True,
            signals_created=count,
        )

    async def mine_batch(self, request: CommentPainBatchRequest) -> CommentPainBatchResult:
        async with self._sessions() as session:
            if request.comment_ids is None:
                comments = await CommentRepository(session).list_for_pain_mining(
                    limit=request.limit
                )
            else:
                comments = [
                    comment
                    for comment_id in request.comment_ids[: request.limit]
                    if (comment := await session.get(Comment, comment_id)) is not None
                ]
        items = [await self.mine(comment.id, force=request.force) for comment in comments]
        return CommentPainBatchResult(
            requested=len(items),
            processed=sum(item.status == "completed" for item in items),
            reused=sum(item.reused for item in items),
            signals_created=sum(item.signals_created for item in items if not item.reused),
            empty_results=sum(
                item.mined and item.signals_created == 0 and not item.reused for item in items
            ),
            failed=sum(item.status in {"failed", "invalid_output"} for item in items),
            items=items,
        )

    async def _load_context(self, comment_id: UUID) -> tuple[Comment, Video, Channel]:
        async with self._sessions() as session:
            comment = await session.get(Comment, comment_id)
            if comment is None or not comment.text.strip():
                raise CommentNotFoundError("Canonical comment was not found")
            video = await session.get(Video, comment.video_id)
            if video is None:
                raise CommentNotFoundError("Parent video was not found")
            channel = await session.get(Channel, video.channel_id)
            if channel is None:
                raise CommentNotFoundError("Parent channel was not found")
            return comment, video, channel

    @staticmethod
    def _build_input(comment: Comment, video: Video, channel: Channel) -> dict:
        return {
            "comment": {
                "comment_id": str(comment.id),
                "youtube_comment_id": comment.youtube_comment_id,
                "text": comment.text,
                "published_at": comment.published_at.isoformat(),
                "source_updated_at": (
                    comment.source_updated_at.isoformat() if comment.source_updated_at else None
                ),
                "like_count": comment.like_count,
                "reply_count": comment.reply_count,
                "language": comment.language,
            },
            "parent_video": {
                "youtube_video_id": video.youtube_video_id,
                "title": video.title,
            },
            "parent_channel": {"name": channel.name, "channel_type": channel.channel_type},
        }

    async def _find_completed(self, comment_id: UUID, input_hash: str):
        async with self._sessions() as session:
            return await AIExtractionRepository(session).find_completed_identity(
                source_type="comment",
                source_id=comment_id,
                task_type=TASK_TYPE,
                prompt_version=PROMPT_VERSION,
                model=self._model,
                input_hash=input_hash,
            )

    async def _start(self, comment_id: UUID, input_hash: str) -> UUID:
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            extraction = await AIExtractionRepository(session).create_pending(
                source_type="comment",
                source_id=comment_id,
                comment_id=comment_id,
                task_type=TASK_TYPE,
                provider=self._provider,
                model=self._model,
                prompt_version=PROMPT_VERSION,
                input_hash=input_hash,
            )
            await AIExtractionRepository(session).mark_running(extraction.id, now)
            return extraction.id

    @staticmethod
    def _validate_output_source(parsed: CommentPainMinerOutput, comment_id: UUID) -> None:
        if any(item.comment_id != comment_id for item in parsed.signals):
            raise InvalidCommentPainOutput("Output comment_id does not match source")

    @staticmethod
    def _normalize_category(category: str) -> str:
        return " ".join(category.strip().lower().replace("_", " ").replace("-", " ").split())

    def _signal_values(self, comment, extraction_id, parsed) -> list[dict]:
        now = datetime.now(UTC)
        rows = []
        for item in parsed.signals:
            category = self._normalize_category(item.category)
            signal_type = CATEGORY_TO_SIGNAL_TYPE.get(category)
            if signal_type is None:
                raise InvalidCommentPainOutput("Unsupported comment pain category")
            rows.append(self._build_signal_values(comment, extraction_id, item, signal_type, now))
            if item.purchase_intent and signal_type != "purchase_intent":
                rows.append(
                    self._build_signal_values(comment, extraction_id, item, "purchase_intent", now)
                )
        return rows

    @staticmethod
    def _build_signal_values(comment, extraction_id, item, signal_type, now) -> dict:
        candidate = SignalCreate(
            source_type="comment",
            source_id=comment.id,
            comment_id=comment.id,
            ai_extraction_id=extraction_id,
            signal_type=signal_type,
            statement=item.pain,
            problem=item.pain,
            solution=item.requested_solution or item.current_solution,
            claim_status="unknown",
            confidence=Decimal(str(item.evidence_strength)),
            evidence_strength=Decimal(str(item.evidence_strength)),
            observed_at=comment.published_at,
            status="review",
        )
        values = candidate.model_dump(mode="python")
        values.update(evidence_text=comment.text[:EVIDENCE_LIMIT], created_at=now, updated_at=now)
        return values

    async def _complete(self, extraction_id, parsed, response, rows) -> tuple[int, list[UUID]]:
        now = datetime.now(UTC)
        strengths = [Decimal(str(item.evidence_strength)) for item in parsed.signals]
        confidence = sum(strengths, Decimal(0)) / len(strengths) if parsed.signals else None
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
        return len(created), [item.id for item in created]

    async def _fail(
        self, extraction_id, *, invalid: bool, raw=None, error: str | None = None
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

    @staticmethod
    def _invalid_result(comment_id: UUID, extraction_id: UUID) -> CommentPainItemResult:
        return CommentPainItemResult(
            comment_id=comment_id, extraction_id=extraction_id, status="invalid_output"
        )
