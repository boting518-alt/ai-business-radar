import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from ai_business_radar_schemas import RelevanceFilterOutput
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.ai import (
    AIClient,
    AIStructuredOutputError,
    default_prompt_version,
    load_prompt,
)
from ..infrastructure.ai.errors import AIProviderError
from ..infrastructure.database.models import Channel, Video
from ..infrastructure.database.repositories import AIExtractionRepository, VideoRepository

TASK_TYPE = "relevance_filter"
PROMPT_TASK = "relevance-filter"
PROMPT_VERSION = default_prompt_version(PROMPT_TASK)


class VideoNotFoundError(RuntimeError):
    pass


class RelevanceRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force: bool = False


class RelevanceBatchRequest(RelevanceRunRequest):
    limit: int = Field(default=20, ge=1, le=100)


class RelevanceItemResult(BaseModel):
    video_id: UUID
    extraction_id: UUID | None
    status: str
    relevant: bool | None = None
    relevance_score: float | None = None
    reused: bool = False


class RelevanceBatchResult(BaseModel):
    requested: int
    processed: int
    relevant: int
    irrelevant: int
    failed: int
    reused: int
    items: list[RelevanceItemResult]


def canonical_input_hash(input_data: dict[str, Any], *, prompt_version: str, task_type: str) -> str:
    payload = {"input": input_data, "prompt_version": prompt_version, "task_type": task_type}
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class VideoRelevanceService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ai_client: AIClient,
        *,
        provider: str,
        model: str,
    ) -> None:
        self._sessions = session_factory
        self._ai = ai_client
        self._provider = provider
        self._model = model

    async def analyze(self, video_id: UUID, *, force: bool = False) -> RelevanceItemResult:
        video, channel = await self._load_video(video_id)
        input_data = self._build_input(video, channel)
        prompt = load_prompt(PROMPT_TASK, PROMPT_VERSION)
        input_hash = canonical_input_hash(
            input_data, prompt_version=PROMPT_VERSION, task_type=TASK_TYPE
        )
        if not force:
            reused = await self._find_completed(video_id, input_hash)
            if reused is not None:
                parsed = RelevanceFilterOutput.model_validate(reused.parsed_output)
                await self._set_video_status(video_id, "queued" if parsed.relevant else "ignored")
                return self._item(video_id, reused.id, parsed, reused=True)
        extraction_id = await self._start(video_id, input_hash)
        try:
            response = await self._ai.structured_generate(
                task_type=TASK_TYPE,
                model=self._model,
                system_prompt=prompt,
                input_data=input_data,
                output_model=RelevanceFilterOutput,
            )
            parsed = RelevanceFilterOutput.model_validate(response.parsed)
        except (AIStructuredOutputError, ValidationError) as error:
            raw = error.raw_output if isinstance(error, AIStructuredOutputError) else None
            await self._fail(extraction_id, video_id, invalid=True, raw=raw)
            return RelevanceItemResult(
                video_id=video_id, extraction_id=extraction_id, status="invalid_output"
            )
        except AIProviderError:
            await self._fail(extraction_id, video_id, invalid=False)
            return RelevanceItemResult(
                video_id=video_id, extraction_id=extraction_id, status="failed"
            )
        await self._complete(extraction_id, video_id, parsed, response)
        return self._item(video_id, extraction_id, parsed)

    async def analyze_batch(self, request: RelevanceBatchRequest) -> RelevanceBatchResult:
        async with self._sessions() as session:
            videos = await VideoRepository(session).list_new_for_relevance(limit=request.limit)
        items = [await self.analyze(video.id, force=request.force) for video in videos]
        return RelevanceBatchResult(
            requested=len(videos),
            processed=sum(item.status == "completed" for item in items),
            relevant=sum(item.relevant is True for item in items),
            irrelevant=sum(item.relevant is False for item in items),
            failed=sum(item.status in {"failed", "invalid_output"} for item in items),
            reused=sum(item.reused for item in items),
            items=items,
        )

    async def _load_video(self, video_id: UUID) -> tuple[Video, Channel]:
        async with self._sessions() as session:
            video = await session.get(Video, video_id)
            if video is None:
                raise VideoNotFoundError("Canonical video was not found")
            channel = await session.get(Channel, video.channel_id)
            return video, channel

    @staticmethod
    def _build_input(video: Video, channel: Channel) -> dict[str, Any]:
        return {
            "video": {
                "youtube_video_id": video.youtube_video_id,
                "title": video.title,
                "description": video.description,
                "published_at": video.published_at.isoformat(),
                "duration_seconds": video.duration_seconds,
                "language": video.language,
                "view_count": video.current_view_count,
                "like_count": video.current_like_count,
                "comment_count": video.current_comment_count,
            },
            "channel": {"name": channel.name, "channel_type": channel.channel_type},
        }

    async def _find_completed(self, video_id: UUID, input_hash: str):
        async with self._sessions() as session:
            return await AIExtractionRepository(session).find_completed_identity(
                source_id=video_id,
                task_type=TASK_TYPE,
                prompt_version=PROMPT_VERSION,
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
                prompt_version=PROMPT_VERSION,
                input_hash=input_hash,
            )
            await AIExtractionRepository(session).mark_running(extraction.id, now)
            await VideoRepository(session).update_processing_status(video_id, "processing")
            return extraction.id

    async def _complete(self, extraction_id, video_id, parsed, response) -> None:
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            await AIExtractionRepository(session).mark_completed(
                extraction_id,
                completed_at=now,
                raw_output=response.raw_output,
                parsed_output=parsed.model_dump(mode="json"),
                confidence=Decimal(str(parsed.relevance_score)),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.total_tokens,
                provider_request_id=response.provider_request_id,
            )
            await VideoRepository(session).update_processing_status(
                video_id, "queued" if parsed.relevant else "ignored"
            )

    async def _fail(self, extraction_id, video_id, *, invalid, raw=None) -> None:
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
                    extraction_id, completed_at=now, error="ai_provider_request_failed"
                )
            await VideoRepository(session).update_processing_status(
                video_id, "review" if invalid else "failed"
            )

    async def _set_video_status(self, video_id: UUID, status: str) -> None:
        async with self._sessions() as session, session.begin():
            await VideoRepository(session).update_processing_status(video_id, status)

    @staticmethod
    def _item(video_id, extraction_id, parsed, *, reused=False):
        return RelevanceItemResult(
            video_id=video_id,
            extraction_id=extraction_id,
            status="completed",
            relevant=parsed.relevant,
            relevance_score=float(parsed.relevance_score),
            reused=reused,
        )
