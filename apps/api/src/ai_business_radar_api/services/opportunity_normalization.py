import re
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from ai_business_radar_schemas import OpportunityNormalizerOutput
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.ai import AIClient, AIStructuredOutputError, load_prompt
from ..infrastructure.ai.errors import AIProviderError
from ..infrastructure.database.models import AIExtraction, Comment, Opportunity, Signal, Video
from ..infrastructure.database.repositories import (
    AIExtractionRepository,
    OpportunityRepository,
    ReviewTaskRepository,
    SignalRepository,
)
from .relevance_filter import canonical_input_hash

TASK_TYPE = "opportunity_normalizer"
PROMPT_TASK = "opportunity-normalizer"
PROMPT_VERSION = "v001"
CANDIDATE_LIMIT = 10
LEXICAL_POOL_LIMIT = 100


class SignalNotFoundError(RuntimeError):
    pass


class SignalNotEligibleError(RuntimeError):
    pass


class InvalidOpportunityNormalizationOutput(RuntimeError):
    pass


class OpportunityNormalizationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force: bool = False


class OpportunityNormalizationBatchRequest(OpportunityNormalizationRunRequest):
    limit: int = Field(default=50, ge=1, le=200)


class OpportunityNormalizationItemResult(BaseModel):
    signal_id: UUID
    extraction_id: UUID | None
    status: str
    action: str | None = None
    opportunity_id: UUID | None = None
    review_task_id: UUID | None = None
    reused: bool = False


class OpportunityNormalizationBatchResult(BaseModel):
    requested: int
    processed: int
    reused: int
    matched: int
    created: int
    review: int
    failed: int
    items: list[OpportunityNormalizationItemResult]


class OpportunityNormalizationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ai_client: AIClient,
        *,
        provider: str,
        model: str,
        match_threshold: float = 0.70,
        create_threshold: float = 0.75,
    ) -> None:
        self._sessions = session_factory
        self._ai = ai_client
        self._provider = provider
        self._model = model
        self._match_threshold = Decimal(str(match_threshold))
        self._create_threshold = Decimal(str(create_threshold))

    async def normalize(
        self, signal_id: UUID, *, force: bool = False
    ) -> OpportunityNormalizationItemResult:
        signal, source_context, candidates = await self._load_context(signal_id, force=force)
        if not force:
            existing = await self._find_existing_outcome(signal_id)
            if existing is not None:
                return existing
        input_data = self._build_input(signal, source_context, candidates)
        prompt = load_prompt(PROMPT_TASK, PROMPT_VERSION)
        input_hash = canonical_input_hash(
            input_data, prompt_version=PROMPT_VERSION, task_type=TASK_TYPE
        )
        if not force:
            reused = await self._find_completed(signal_id, input_hash)
            if reused is not None:
                return await self._reused_result(signal_id, reused.id)

        extraction_id = await self._start(signal_id, input_hash)
        try:
            response = await self._ai.structured_generate(
                task_type=TASK_TYPE,
                model=self._model,
                system_prompt=prompt,
                input_data=input_data,
                output_model=OpportunityNormalizerOutput,
            )
        except AIStructuredOutputError as error:
            await self._fail(extraction_id, invalid=True, raw=error.raw_output)
            return self._result(signal_id, extraction_id, "invalid_output")
        except AIProviderError:
            await self._fail(extraction_id, invalid=False)
            return self._result(signal_id, extraction_id, "failed")

        try:
            parsed = OpportunityNormalizerOutput.model_validate(response.parsed)
            self._validate_match(parsed, candidates)
        except (ValidationError, InvalidOpportunityNormalizationOutput):
            await self._fail(extraction_id, invalid=True, raw=response.raw_output)
            return self._result(signal_id, extraction_id, "invalid_output")

        try:
            return await self._complete(signal, candidates, extraction_id, parsed, response)
        except SQLAlchemyError:
            await self._fail(extraction_id, invalid=False, error="normalization_persistence_failed")
            return self._result(signal_id, extraction_id, "failed")

    async def normalize_batch(
        self, request: OpportunityNormalizationBatchRequest
    ) -> OpportunityNormalizationBatchResult:
        async with self._sessions() as session:
            signals = await SignalRepository(session).list_for_normalization(limit=request.limit)
        items = [await self.normalize(signal.id, force=request.force) for signal in signals]
        return OpportunityNormalizationBatchResult(
            requested=len(items),
            processed=sum(item.status == "completed" for item in items),
            reused=sum(item.reused for item in items),
            matched=sum(item.action == "MATCH" for item in items),
            created=sum(item.action == "CREATE" for item in items),
            review=sum(item.action == "REVIEW" for item in items),
            failed=sum(item.status in {"failed", "invalid_output"} for item in items),
            items=items,
        )

    async def _load_context(self, signal_id: UUID, *, force: bool):
        async with self._sessions() as session:
            signal = await SignalRepository(session).get_by_id(signal_id)
            if signal is None:
                raise SignalNotFoundError("Signal was not found")
            if signal.status in {"ignored", "rejected"} and not force:
                raise SignalNotEligibleError("Signal is not eligible for normalization")
            source_context: dict = {}
            if signal.video_id:
                video = await session.get(Video, signal.video_id)
                if video:
                    source_context = {
                        "source_type": "video",
                        "youtube_video_id": video.youtube_video_id,
                        "title": video.title,
                        "published_at": video.published_at.isoformat(),
                    }
            elif signal.comment_id:
                comment = await session.get(Comment, signal.comment_id)
                if comment:
                    video = await session.get(Video, comment.video_id)
                    source_context = {
                        "source_type": "comment",
                        "text": comment.text,
                        "published_at": comment.published_at.isoformat(),
                        "parent_video_title": video.title if video else None,
                    }
            terms = self._lexical_terms(signal)
            pool = await OpportunityRepository(session).list_lexical_candidates(
                terms=terms, limit=LEXICAL_POOL_LIMIT
            )
            candidates = sorted(
                pool,
                key=lambda item: (
                    -self._lexical_score(item, terms),
                    item.name.lower(),
                    str(item.id),
                ),
            )[:CANDIDATE_LIMIT]
            return signal, source_context, candidates

    @staticmethod
    def _lexical_terms(signal: Signal) -> list[str]:
        text = " ".join(
            value
            for value in (
                signal.statement,
                signal.industry,
                signal.customer_type,
                signal.problem,
                signal.solution,
            )
            if value
        ).lower()
        return sorted({word for word in re.findall(r"[\w-]{3,}", text) if not word.isdigit()})[:20]

    @staticmethod
    def _lexical_score(opportunity: Opportunity, terms: list[str]) -> int:
        haystack = " ".join(
            value.lower()
            for value in (
                opportunity.name,
                opportunity.one_line_thesis,
                opportunity.industry,
                opportunity.customer_type,
                opportunity.problem,
                opportunity.solution,
            )
            if value
        )
        return sum(term in haystack for term in terms)

    @staticmethod
    def _build_input(signal: Signal, source_context: dict, candidates: list[Opportunity]) -> dict:
        return {
            "signal": {
                "signal_id": str(signal.id),
                "signal_type": signal.signal_type,
                "statement": signal.statement,
                "evidence_text": signal.evidence_text,
                "industry": signal.industry,
                "sub_industry": signal.sub_industry,
                "customer_type": signal.customer_type,
                "problem": signal.problem,
                "solution": signal.solution,
                "business_model": signal.business_model,
                "technology": signal.technology,
                "claim_status": signal.claim_status,
                "observed_at": signal.observed_at.isoformat() if signal.observed_at else None,
            },
            "source_context": source_context,
            "candidates": [
                {
                    "opportunity_id": str(item.id),
                    "name": item.name,
                    "one_line_thesis": item.one_line_thesis,
                    "industry": item.industry,
                    "customer_type": item.customer_type,
                    "problem": item.problem,
                    "solution": item.solution,
                    "status": item.status,
                }
                for item in candidates
            ],
        }

    @staticmethod
    def _validate_match(parsed, candidates) -> None:
        if parsed.action.value != "MATCH":
            return
        eligible = {
            item.id for item in candidates if item.status in {"candidate", "active", "review"}
        }
        if parsed.opportunity_id not in eligible:
            raise InvalidOpportunityNormalizationOutput("MATCH id was not an eligible candidate")

    async def _find_completed(self, signal_id, input_hash):
        async with self._sessions() as session:
            return await AIExtractionRepository(session).find_completed_identity(
                source_type="signal",
                source_id=signal_id,
                task_type=TASK_TYPE,
                prompt_version=PROMPT_VERSION,
                model=self._model,
                input_hash=input_hash,
            )

    async def _find_existing_outcome(self, signal_id):
        async with self._sessions() as session:
            link = await OpportunityRepository(session).get_link_for_signal(signal_id)
            review = await ReviewTaskRepository(session).find_open_for_target(
                target_type="signal", target_id=signal_id
            )
            if link is None and review is None:
                return None
            extraction = await AIExtractionRepository(session).find_latest_completed_source(
                source_type="signal",
                source_id=signal_id,
                task_type=TASK_TYPE,
                prompt_version=PROMPT_VERSION,
                model=self._model,
            )
            if extraction is None:
                return None
            return self._outcome_result(signal_id, extraction, link, review)

    async def _start(self, signal_id, input_hash):
        now = datetime.now(UTC)
        async with self._sessions() as session, session.begin():
            extraction = await AIExtractionRepository(session).create_pending(
                source_type="signal",
                source_id=signal_id,
                signal_id=signal_id,
                task_type=TASK_TYPE,
                provider=self._provider,
                model=self._model,
                prompt_version=PROMPT_VERSION,
                input_hash=input_hash,
            )
            await AIExtractionRepository(session).mark_running(extraction.id, now)
            return extraction.id

    async def _complete(self, signal, candidates, extraction_id, parsed, response):
        now = datetime.now(UTC)
        action = parsed.action.value
        confidence = Decimal(str(parsed.confidence))
        review_reason = None
        if action == "MATCH" and confidence < self._match_threshold:
            action, review_reason = "REVIEW", "match_confidence_below_threshold"
        elif action == "CREATE" and confidence < self._create_threshold:
            action, review_reason = "REVIEW", "create_confidence_below_threshold"

        async with self._sessions() as session, session.begin():
            opportunities = OpportunityRepository(session)
            opportunity_id = None
            review_task_id = None
            if action == "MATCH":
                opportunity_id = parsed.opportunity_id
                await opportunities.link_signal(
                    opportunity_id=opportunity_id,
                    signal_id=signal.id,
                    relationship_type="supporting",
                    confidence=confidence,
                    created_at=now,
                )
                await opportunities.update_last_activity(opportunity_id, signal.observed_at or now)
                await SignalRepository(session).update_status(signal.id, "active")
            elif action == "CREATE":
                slug = self._slugify(parsed.canonical_name)
                if await opportunities.get_by_slug(slug):
                    action, review_reason = "REVIEW", "canonical_slug_collision"
                else:
                    opportunity = await opportunities.create_opportunity(
                        slug=slug,
                        name=parsed.canonical_name,
                        one_line_thesis=signal.statement,
                        industry=signal.industry,
                        sub_industry=signal.sub_industry,
                        customer_type=signal.customer_type,
                        problem=signal.problem,
                        solution=signal.solution,
                        business_model=signal.business_model,
                        primary_technology=(signal.technology or [None])[0],
                        typical_price_min=signal.price_min,
                        typical_price_max=signal.price_max,
                        typical_price_currency=signal.price_currency,
                        typical_price_period=signal.price_period,
                        market_stage="unknown",
                        competition_level=None,
                        build_difficulty=None,
                        sales_difficulty=None,
                        status="candidate",
                        first_detected_at=signal.observed_at or now,
                        last_activity_at=signal.observed_at or now,
                        created_at=now,
                        updated_at=now,
                    )
                    opportunity_id = opportunity.id
                    await opportunities.link_signal(
                        opportunity_id=opportunity.id,
                        signal_id=signal.id,
                        relationship_type="supporting",
                        confidence=confidence,
                        created_at=now,
                    )
                    await SignalRepository(session).update_status(signal.id, "active")
            if action == "REVIEW":
                review = await ReviewTaskRepository(session).find_open_for_target(
                    target_type="signal", target_id=signal.id
                )
                if review is None:
                    requested_action = parsed.action.value
                    review = await ReviewTaskRepository(session).create_review_task(
                        review_type=(
                            "opportunity_match"
                            if requested_action == "MATCH"
                            else "opportunity_creation"
                        ),
                        target_type="signal",
                        target_id=signal.id,
                        status="pending",
                        priority=confidence,
                        assigned_to=None,
                        decision=None,
                        decision_notes=None,
                        context={
                            "reason": review_reason or parsed.reason,
                            "model_action": requested_action,
                            "proposed_opportunity_id": (
                                str(parsed.opportunity_id) if parsed.opportunity_id else None
                            ),
                            "candidate_ids": [str(item.id) for item in candidates],
                            "extraction_id": str(extraction_id),
                        },
                        created_at=now,
                        updated_at=now,
                        resolved_at=None,
                    )
                review_task_id = review.id
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
            return OpportunityNormalizationItemResult(
                signal_id=signal.id,
                extraction_id=extraction_id,
                status="completed",
                action=action,
                opportunity_id=opportunity_id,
                review_task_id=review_task_id,
            )

    async def _reused_result(self, signal_id, extraction_id):
        async with self._sessions() as session:
            extraction = await session.get(AIExtraction, extraction_id)
            link = await OpportunityRepository(session).get_link_for_signal(signal_id)
            review = await ReviewTaskRepository(session).find_open_for_target(
                target_type="signal", target_id=signal_id
            )
        return self._outcome_result(signal_id, extraction, link, review)

    @staticmethod
    def _outcome_result(signal_id, extraction, link, review):
        return OpportunityNormalizationItemResult(
            signal_id=signal_id,
            extraction_id=extraction.id,
            status="completed",
            action=(
                "REVIEW"
                if review
                else extraction.parsed_output.get("action")
                if link and extraction and extraction.parsed_output
                else None
            ),
            opportunity_id=link.opportunity_id if link else None,
            review_task_id=review.id if review else None,
            reused=True,
        )

    async def _fail(self, extraction_id, *, invalid, raw=None, error=None):
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
    def _slugify(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "opportunity"

    @staticmethod
    def _result(signal_id, extraction_id, status):
        return OpportunityNormalizationItemResult(
            signal_id=signal_id, extraction_id=extraction_id, status=status
        )
