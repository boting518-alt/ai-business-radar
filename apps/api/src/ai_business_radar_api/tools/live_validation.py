"""Safe, bounded orchestration of existing services for local live validation."""

import argparse
import asyncio
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from ai_business_radar_schemas import RelevanceFilterOutput
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Settings
from ..infrastructure.ai import OpenAIClient, load_prompt
from ..infrastructure.database import create_database_engine, create_session_factory
from ..infrastructure.database.models import (
    AIExtraction,
    Comment,
    Opportunity,
    OpportunitySignalLink,
    SearchQuery,
    Signal,
    Video,
    VideoSnapshot,
    YouTubeDiscoveryItem,
)
from ..infrastructure.external.youtube import YouTubeClient
from ..services.comment_pain_mining import CommentPainMiningService
from ..services.opportunity_normalization import OpportunityNormalizationService
from ..services.opportunity_scoring import OpportunityScoringService
from ..services.relevance_filter import VideoRelevanceService
from ..services.signal_extraction import BusinessSignalExtractionService
from ..services.trend_aggregation import (
    OpportunityTrendAggregationService,
    TrendAggregationRequest,
)
from ..services.youtube_comments import CommentCollectionRequest, YouTubeCommentCollectionService
from ..services.youtube_discovery import DiscoveryRequest, YouTubeDiscoveryService
from ..services.youtube_metadata import MetadataCollectionRequest, YouTubeMetadataCollectionService

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
REPORT_ROOT = REPOSITORY_ROOT / "artifacts" / "live-validation"
EXPECTED_TABLES = {
    "ai_extractions",
    "channels",
    "collection_runs",
    "comments",
    "opportunities",
    "opportunity_scores",
    "search_queries",
    "signals",
    "trend_snapshots",
    "videos",
    "youtube_discovery_items",
}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
SAFE_DATABASE_NAME = "ai_business_radar_live_test"
STAGES = (
    "discovery",
    "metadata",
    "comments",
    "relevance",
    "signals",
    "comment-pain",
    "normalization",
    "trend",
    "scoring",
)
QUALITY_CHECKLIST = (
    "Relevance Precision",
    "Signal Precision",
    "Atomic Signal Quality",
    "Creator Claim Accuracy",
    "Comment No-Signal Accuracy",
    "Comment Pain Precision",
    "Purchase Intent Precision",
    "Opportunity Match Accuracy",
    "Opportunity Duplicate Rate",
    "Top-10 Usefulness",
)


class LiveValidationError(RuntimeError):
    """A safe user-facing validation failure."""


@dataclass(frozen=True)
class ValidationLimits:
    max_videos: int = 10
    max_comments_per_video: int = 20
    max_pages: int = 1
    max_ai_videos: int = 5
    max_ai_comments: int = 20
    max_normalization_signals: int = 20

    def validate(self) -> None:
        bounds = {
            "max_videos": (self.max_videos, 1, 25),
            "max_comments_per_video": (self.max_comments_per_video, 1, 50),
            "max_pages": (self.max_pages, 1, 2),
            "max_ai_videos": (self.max_ai_videos, 1, 10),
            "max_ai_comments": (self.max_ai_comments, 1, 50),
            "max_normalization_signals": (self.max_normalization_signals, 1, 20),
        }
        for name, (value, minimum, maximum) in bounds.items():
            if not minimum <= value <= maximum:
                raise LiveValidationError(f"{name} must be between {minimum} and {maximum}")


@dataclass
class ServiceBundle:
    discovery: YouTubeDiscoveryService
    metadata: YouTubeMetadataCollectionService
    comments: YouTubeCommentCollectionService
    relevance: VideoRelevanceService | None = None
    signals: BusinessSignalExtractionService | None = None
    comment_pain: CommentPainMiningService | None = None
    normalization: OpportunityNormalizationService | None = None
    trends: OpportunityTrendAggregationService | None = None
    scoring: OpportunityScoringService | None = None


@dataclass
class ValidationReport:
    run_id: str
    command: str
    query: str | None
    limits: dict[str, int]
    database: dict[str, str]
    started_at: str
    dry_run: bool = False
    force_ai: bool = False
    stages_completed: list[str] = field(default_factory=list)
    youtube: dict[str, Any] = field(default_factory=dict)
    relevance: list[dict[str, Any]] = field(default_factory=list)
    relevance_summary: dict[str, Any] = field(default_factory=dict)
    signals: list[dict[str, Any]] = field(default_factory=list)
    signal_summary: dict[str, Any] = field(default_factory=dict)
    comment_pain: list[dict[str, Any]] = field(default_factory=list)
    comment_pain_summary: dict[str, Any] = field(default_factory=dict)
    normalization: dict[str, Any] = field(default_factory=dict)
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    scores: list[dict[str, Any]] = field(default_factory=list)
    token_usage: dict[str, int] = field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    )
    failures: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    quality_checklist: dict[str, str] = field(
        default_factory=lambda: {name: "" for name in QUALITY_CHECKLIST}
    )
    finished_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def database_identity(database_url: str) -> tuple[URL, dict[str, str]]:
    try:
        parsed = make_url(database_url)
    except Exception as error:
        raise LiveValidationError("Live validation database URL is invalid") from error
    host = (parsed.host or "").lower()
    database = (parsed.database or "").lstrip("/")
    if host not in LOCAL_HOSTS:
        raise LiveValidationError("Live validation refuses non-local database hosts")
    if database != SAFE_DATABASE_NAME:
        raise LiveValidationError(
            f"Live validation requires the dedicated database {SAFE_DATABASE_NAME}"
        )
    return parsed, {"host": host, "database": database}


def configured(secret: Any) -> bool:
    if secret is None:
        return False
    value = secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret)
    return bool(value.strip())


def safe_error(error: BaseException) -> str:
    """Never serialize provider exception messages, which may contain request details."""
    return type(error).__name__


def safe_integrity_diagnostic(stage: str, error: IntegrityError) -> dict[str, str]:
    """Return actionable PostgreSQL metadata without SQL, parameters, or URLs."""
    original = error.orig
    diagnostic = getattr(original, "diag", None)
    constraint = getattr(diagnostic, "constraint_name", None)
    message = getattr(diagnostic, "message_primary", None)
    if not isinstance(message, str) or not message:
        message = "Database integrity constraint violated."
    message = re.sub(r"(?i)postgres(?:ql)?://\S+", "[REDACTED_DATABASE_URL]", message)
    message = re.sub(r"(?i)password\s*[=:]\s*\S+", "password=[REDACTED]", message)
    result = {
        "stage": stage,
        "error_type": "IntegrityError",
        "message": message[:300],
    }
    if isinstance(constraint, str) and re.fullmatch(r"[A-Za-z0-9_]{1,128}", constraint):
        result["constraint"] = constraint
    return result


def failure_summary(item: dict[str, str]) -> str:
    error_type = item.get("error", item.get("error_type", "Error"))
    constraint = f" ({item['constraint']})" if item.get("constraint") else ""
    message = f": {item['message']}" if item.get("message") else ""
    return f"- {item['stage']}: {error_type}{constraint}{message}"


def safe_provider_diagnostic(error: BaseException, settings: Settings) -> dict[str, str]:
    """Expose only a bounded provider category/message with credentials redacted."""
    root = error.__cause__ or error
    body = getattr(root, "body", None)
    provider_error = body.get("error", {}) if isinstance(body, dict) else {}
    message = provider_error.get("message") if isinstance(provider_error, dict) else None
    if not isinstance(message, str):
        message = str(getattr(root, "message", "Provider request failed"))
    secrets = (
        settings.youtube_api_key,
        settings.openai_api_key,
        settings.supabase_service_role_key,
        settings.supabase_jwt_secret,
    )
    for secret in secrets:
        if configured(secret):
            message = message.replace(secret.get_secret_value(), "[REDACTED]")
    message = re.sub(r"(?i)bearer\s+[a-z0-9._-]+", "Bearer [REDACTED]", message)
    message = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}\b", "[REDACTED]", message)
    message = re.sub(r"\bAIza[0-9A-Za-z_-]{20,}\b", "[REDACTED]", message)
    return {
        "status": "failed",
        "error_type": type(root).__name__,
        "message": message[:500],
    }


def configuration_status(settings: Settings) -> dict[str, str]:
    return {
        "YOUTUBE_API_KEY": "configured" if configured(settings.youtube_api_key) else "missing",
        "OPENAI_API_KEY": "configured" if configured(settings.openai_api_key) else "missing",
        "AI_PROVIDER": settings.ai_provider or "missing",
        "AI_MODEL_RELEVANCE": settings.ai_model_relevance or "missing",
        "AI_MODEL_SIGNAL_EXTRACTION": settings.ai_model_signal_extraction or "missing",
        "AI_MODEL_COMMENT_PAIN_MINING": settings.ai_model_comment_pain_mining or "missing",
        "AI_MODEL_OPPORTUNITY_NORMALIZATION": (
            settings.ai_model_opportunity_normalization or "missing"
        ),
    }


class ReportWriter:
    def __init__(self, root: Path = REPORT_ROOT) -> None:
        self.root = root

    def write(self, report: ValidationReport) -> Path:
        timestamp = report.started_at.replace(":", "").replace("-", "").split(".")[0]
        directory = self.root / f"{timestamp}-{report.run_id[:8]}"
        directory.mkdir(parents=True, exist_ok=False)
        payload = report.as_dict()
        self._write_json(directory / "summary.json", payload)
        (directory / "summary.md").write_text(self._markdown(report), encoding="utf-8")
        self._write_csv(directory / "relevance_review.csv", report.relevance)
        self._write_csv(directory / "signal_review.csv", report.signals)
        self._write_csv(directory / "comment_pain_review.csv", report.comment_pain)
        self._write_csv(directory / "opportunities.csv", report.opportunities)
        self._write_csv(directory / "scores.csv", report.scores)
        return directory

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        content = json.dumps(value, ensure_ascii=False, indent=2, default=str)
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        columns = sorted({key for row in rows for key in row}) or ["status"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _csv_value(value) for key, value in row.items()})

    @staticmethod
    def _markdown(report: ValidationReport) -> str:
        failures = "\n".join(failure_summary(item) for item in report.failures) or "- None"
        warnings = "\n".join(f"- {item}" for item in report.warnings) or "- None"
        checklist = "\n".join(f"- [ ] {name}:" for name in QUALITY_CHECKLIST)
        scores = "\n".join(
            f"| {row.get('opportunity', '')} | {row.get('score', '')} | "
            f"{row.get('confidence', '')} | {row.get('hype_risk', '')} | "
            f"{row.get('momentum_7d', '')} |"
            for row in report.scores
        ) or "| _No scored opportunities_ | | | | |"
        return f"""# Local Live Validation — {report.run_id}

**LOCAL LIVE VALIDATION DATA — NOT PRODUCTION INTELLIGENCE**

## Run metadata

- Command: {report.command}
- Query: {report.query or 'N/A'}
- Started: {report.started_at}
- Finished: {report.finished_at or 'partial'}
- Database: {report.database['host']} / {report.database['database']}
- Dry run: {report.dry_run}
- Force AI: {report.force_ai}
- Completed stages: {', '.join(report.stages_completed) or 'none'}

## Limits

```json
{json.dumps(report.limits, indent=2)}
```

## YouTube request and RAW summary

```json
{json.dumps(report.youtube, indent=2, default=str)}
```

## OpenAI request and token summary

```json
{json.dumps(report.token_usage, indent=2)}
```

Relevance rows: {len(report.relevance)}
Signal review rows: {len(report.signals)}
Comment pain rows: {len(report.comment_pain)}
Normalization: `{json.dumps(report.normalization, default=str)}`

Relevance summary: `{json.dumps(report.relevance_summary, default=str)}`
Signal summary: `{json.dumps(report.signal_summary, default=str)}`
Comment pain summary: `{json.dumps(report.comment_pain_summary, default=str)}`

## Final ranking

| Opportunity | Score | Confidence | Hype Risk | 7d Momentum |
| --- | ---: | ---: | ---: | ---: |
{scores}

## Failures

{failures}

## Warnings

{warnings}

## Manual quality review

{checklist}

## Next action

Review the generated CSV files, complete the checklist, and use the normal Admin Review workflow
before expecting candidate intelligence to appear on Radar. Radar may be empty until that workflow
activates the relevant records.
"""


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


class LiveValidationRunner:
    def __init__(
        self,
        settings: Settings,
        sessions: async_sessionmaker[AsyncSession],
        services: ServiceBundle,
        *,
        writer: ReportWriter | None = None,
    ) -> None:
        self.settings = settings
        self.sessions = sessions
        self.services = services
        self.writer = writer or ReportWriter()

    async def run(
        self,
        *,
        command: str,
        query: str | None,
        limits: ValidationLimits,
        stop_after: str | None,
        force_ai: bool,
        dry_run: bool,
        show_sample: bool,
        identity: dict[str, str],
    ) -> tuple[ValidationReport, Path]:
        limits.validate()
        report = ValidationReport(
            run_id=str(uuid4()),
            command=command,
            query=query,
            limits=dict(limits.__dict__),
            database=identity,
            started_at=datetime.now(UTC).isoformat(),
            dry_run=dry_run,
            force_ai=force_ai,
        )
        self._active_report = report
        if force_ai:
            report.warnings.append(
                "Force AI creates new extraction history and consumes provider tokens."
            )
        if dry_run:
            report.warnings.append(
                "Dry run made no YouTube or OpenAI requests and changed no data."
            )
            report.finished_at = datetime.now(UTC).isoformat()
            return report, self.writer.write(report)

        video_ids: list[UUID] = []
        signal_ids: list[UUID] = []
        opportunity_ids: list[UUID] = []
        try:
            if command in {"youtube", "full"}:
                if not query:
                    raise LiveValidationError("A query is required for YouTube validation")
                query_id = await self._get_or_create_query(query)
                discovery = await self.services.discovery.discover(
                    DiscoveryRequest(
                        search_query_id=query_id,
                        max_pages=limits.max_pages,
                        max_results=limits.max_videos,
                    )
                )
                report.youtube["discovery"] = discovery.model_dump(mode="json")
                report.stages_completed.append("discovery")
                if self._stopped(report, stop_after):
                    return self._finish(report)

                metadata = await self.services.metadata.collect(
                    MetadataCollectionRequest(
                        collection_run_id=discovery.collection_run_id,
                        limit=limits.max_videos,
                        include_snapshots=True,
                    )
                )
                report.youtube["metadata"] = metadata.model_dump(mode="json")
                video_ids = await self._run_video_ids(discovery.collection_run_id)
                report.stages_completed.append("metadata")
                if self._stopped(report, stop_after):
                    return self._finish(report)

                if video_ids:
                    comments = await self.services.comments.collect(
                        CommentCollectionRequest(
                            video_ids=video_ids,
                            limit_videos=limits.max_videos,
                            max_pages_per_video=limits.max_pages,
                            max_comments_per_video=limits.max_comments_per_video,
                        )
                    )
                    report.youtube["comments"] = comments.model_dump(mode="json")
                else:
                    report.youtube["comments"] = {"status": "skipped", "reason": "no_videos"}
                    report.warnings.append(
                        "Comment collection skipped because metadata returned no videos."
                    )
                report.youtube["raw_counts"] = await self._raw_counts(video_ids)
                if show_sample:
                    report.youtube["sample"] = await self._raw_sample(video_ids)
                report.stages_completed.append("comments")
                if command == "youtube" or self._stopped(report, stop_after):
                    return self._finish(report)

            if command == "ai":
                video_ids = await self._select_ai_videos(limits.max_ai_videos)

            relevance_ids: list[UUID] = []
            assert self.services.relevance is not None
            for video_id in video_ids[: limits.max_ai_videos]:
                item = await self.services.relevance.analyze(video_id, force=force_ai)
                if not getattr(item, "reused", False):
                    await self._track_extraction(item.extraction_id)
                report.relevance.append(await self._relevance_row(video_id, item))
                if item.relevant is True:
                    relevance_ids.append(video_id)
            report.relevance_summary = {
                "processed": len(report.relevance),
                "relevant": len(relevance_ids),
                "irrelevant": len(report.relevance) - len(relevance_ids),
            }
            report.stages_completed.append("relevance")
            if self._stopped(report, stop_after):
                return self._finish(report)

            extraction_ids: list[UUID] = []
            assert self.services.signals is not None
            for video_id in relevance_ids:
                item = await self.services.signals.extract(video_id, force=force_ai)
                if item.extraction_id:
                    extraction_ids.append(item.extraction_id)
                    if not getattr(item, "reused", False):
                        await self._track_extraction(item.extraction_id)
            signal_ids.extend(await self._signals_for_extractions(extraction_ids))
            report.signals = await self._signal_rows(signal_ids, limit=20)
            report.signal_summary = {
                "signals": len(signal_ids),
                "sampled": len(report.signals),
                "types": dict(Counter(row["signal_type"] for row in report.signals)),
                "claim_statuses": dict(
                    Counter(row.get("claim_status", "") for row in report.signals)
                ),
            }
            report.stages_completed.append("signals")
            if self._stopped(report, stop_after):
                return self._finish(report)

            comment_ids = await self._select_comments(video_ids, limits.max_ai_comments)
            pain_extraction_ids: list[UUID] = []
            assert self.services.comment_pain is not None
            for comment_id in comment_ids:
                item = await self.services.comment_pain.mine(comment_id, force=force_ai)
                if item.extraction_id:
                    pain_extraction_ids.append(item.extraction_id)
                    if not getattr(item, "reused", False):
                        await self._track_extraction(item.extraction_id)
                report.comment_pain.append(await self._comment_pain_row(comment_id, item))
            pain_signal_ids = await self._signals_for_extractions(pain_extraction_ids)
            signal_ids.extend(pain_signal_ids)
            report.comment_pain_summary = {
                "processed": len(report.comment_pain),
                "with_signals": sum(bool(row["signal"]) for row in report.comment_pain),
                "no_signal": sum(not bool(row["signal"]) for row in report.comment_pain),
                "signals_created": len(pain_signal_ids),
                "failed": sum(row.get("status") != "completed" for row in report.comment_pain),
            }
            report.stages_completed.append("comment-pain")
            if self._stopped(report, stop_after):
                return self._finish(report)

            actions = Counter()
            assert self.services.normalization is not None
            for signal_id in list(dict.fromkeys(signal_ids))[: limits.max_normalization_signals]:
                item = await self.services.normalization.normalize(signal_id, force=force_ai)
                if not getattr(item, "reused", False):
                    await self._track_extraction(item.extraction_id)
                actions[item.action or item.status] += 1
                if item.opportunity_id:
                    opportunity_ids.append(item.opportunity_id)
            opportunity_ids = list(dict.fromkeys(opportunity_ids))
            report.normalization = dict(actions)
            report.opportunities = await self._opportunity_rows(opportunity_ids)
            report.stages_completed.append("normalization")
            if self._stopped(report, stop_after):
                return self._finish(report)

            assert self.services.trends is not None
            for opportunity_id in opportunity_ids:
                for window in ("7d", "30d", "90d"):
                    await self.services.trends.aggregate(
                        TrendAggregationRequest(
                            opportunity_id=opportunity_id,
                            window_type=window,
                            force=False,
                        )
                    )
            report.stages_completed.append("trend")
            if self._stopped(report, stop_after):
                return self._finish(report)

            assert self.services.scoring is not None
            for opportunity_id in opportunity_ids:
                result = await self.services.scoring.score(opportunity_id, force=False)
                report.scores.append(await self._score_row(opportunity_id, result))
            report.scores.sort(key=lambda row: float(row["score"]), reverse=True)
            report.stages_completed.append("scoring")
        except Exception as error:
            stage = next((item for item in STAGES if item not in report.stages_completed), "setup")
            failure = (
                safe_integrity_diagnostic(stage, error)
                if isinstance(error, IntegrityError)
                else {"stage": stage, "error": safe_error(error)}
            )
            report.failures.append(failure)
        return self._finish(report)

    def _finish(self, report: ValidationReport) -> tuple[ValidationReport, Path]:
        report.finished_at = datetime.now(UTC).isoformat()
        return report, self.writer.write(report)

    @staticmethod
    def _stopped(report: ValidationReport, stop_after: str | None) -> bool:
        return bool(stop_after and report.stages_completed[-1] == stop_after)

    async def _get_or_create_query(self, query: str) -> UUID:
        async with self.sessions() as session, session.begin():
            existing = await session.scalar(
                select(SearchQuery).where(
                    SearchQuery.query == query,
                    SearchQuery.query_group == "discovery",
                    SearchQuery.discovery_mode == "discovery",
                )
            )
            if existing:
                return existing.id
            now = datetime.now(UTC)
            entity = SearchQuery(
                query=query,
                query_group="discovery",
                language="en",
                region=None,
                enabled=True,
                priority=0,
                discovery_mode="discovery",
                last_run_at=None,
                created_at=now,
                updated_at=now,
            )
            session.add(entity)
            await session.flush()
            return entity.id

    async def _run_video_ids(self, run_id: UUID) -> list[UUID]:
        async with self.sessions() as session:
            return list(
                await session.scalars(
                    select(YouTubeDiscoveryItem.canonical_video_id)
                    .where(
                        YouTubeDiscoveryItem.collection_run_id == run_id,
                        YouTubeDiscoveryItem.canonical_video_id.is_not(None),
                    )
                    .order_by(YouTubeDiscoveryItem.id)
                )
            )

    async def _select_ai_videos(self, limit: int) -> list[UUID]:
        async with self.sessions() as session:
            return list(
                await session.scalars(
                    select(Video.id)
                    .where(Video.processing_status.in_(("new", "queued")))
                    .order_by(Video.first_seen_at.desc(), Video.id)
                    .limit(limit)
                )
            )

    async def _select_comments(self, video_ids: list[UUID], limit: int) -> list[UUID]:
        if not video_ids:
            return []
        async with self.sessions() as session:
            return list(
                await session.scalars(
                    select(Comment.id)
                    .where(Comment.video_id.in_(video_ids), Comment.text != "")
                    .order_by(Comment.first_seen_at, Comment.id)
                    .limit(limit)
                )
            )

    async def _signals_for_extractions(self, extraction_ids: list[UUID]) -> list[UUID]:
        if not extraction_ids:
            return []
        async with self.sessions() as session:
            return list(
                await session.scalars(
                    select(Signal.id)
                    .where(Signal.ai_extraction_id.in_(extraction_ids))
                    .order_by(Signal.created_at, Signal.id)
                )
            )

    async def _raw_counts(self, video_ids: list[UUID]) -> dict[str, int]:
        if not video_ids:
            return {"videos": 0, "channels": 0, "snapshots": 0, "comments": 0}
        async with self.sessions() as session:
            videos = (
                await session.scalar(
                    select(func.count(Video.id)).where(Video.id.in_(video_ids))
                )
            ) or 0
            channels = (
                await session.scalar(
                    select(func.count(func.distinct(Video.channel_id))).where(Video.id.in_(video_ids))
                )
            ) or 0
            snapshots = (
                await session.scalar(
                    select(func.count(VideoSnapshot.id)).where(VideoSnapshot.video_id.in_(video_ids))
                )
            ) or 0
            comments = (
                await session.scalar(
                    select(func.count(Comment.id)).where(Comment.video_id.in_(video_ids))
                )
            ) or 0
        return {
            "videos": videos,
            "channels": channels,
            "snapshots": snapshots,
            "comments": comments,
        }

    async def _raw_sample(self, video_ids: list[UUID]) -> dict[str, list[str]]:
        if not video_ids:
            return {"video_titles": [], "comment_excerpts": []}
        async with self.sessions() as session:
            titles = list(
                await session.scalars(select(Video.title).where(Video.id.in_(video_ids)).limit(5))
            )
            comments = list(
                await session.scalars(
                    select(Comment.text).where(Comment.video_id.in_(video_ids)).limit(5)
                )
            )
        return {
            "video_titles": [item[:160] for item in titles],
            "comment_excerpts": [item[:240] for item in comments],
        }

    async def _extraction(self, extraction_id: UUID | None) -> AIExtraction | None:
        if extraction_id is None:
            return None
        async with self.sessions() as session:
            return await session.get(AIExtraction, extraction_id)

    async def _track_extraction(self, extraction_id: UUID | None) -> None:
        self._accumulate_tokens(await self._extraction(extraction_id))

    async def _relevance_row(self, video_id: UUID, item: Any) -> dict[str, Any]:
        async with self.sessions() as session:
            video = await session.get(Video, video_id)
            extraction = (
                await session.get(AIExtraction, item.extraction_id)
                if item.extraction_id
                else None
            )
        parsed = extraction.parsed_output if extraction and extraction.parsed_output else {}
        return {
            "video_id": str(video_id),
            "video_title": video.title if video else "",
            "ai_relevant": item.relevant,
            "relevance_score": item.relevance_score,
            "reason": str(parsed.get("reason", ""))[:300],
            "processing_state": video.processing_status if video else "",
            "model": extraction.model if extraction else "",
            "prompt_version": extraction.prompt_version if extraction else "",
            "input_tokens": extraction.input_tokens if extraction else None,
            "output_tokens": extraction.output_tokens if extraction else None,
            "total_tokens": extraction.total_tokens if extraction else None,
            "reused": item.reused,
            "status": item.status,
            "human_relevant": "",
            "human_notes": "",
        }

    def _accumulate_tokens(self, extraction: AIExtraction | None) -> None:
        if not extraction:
            return
        report = getattr(self, "_active_report", None)
        if report is None:
            return
        report.token_usage["input_tokens"] += extraction.input_tokens or 0
        report.token_usage["output_tokens"] += extraction.output_tokens or 0
        report.token_usage["total_tokens"] += extraction.total_tokens or 0

    async def _signal_rows(self, signal_ids: list[UUID], *, limit: int) -> list[dict[str, Any]]:
        if not signal_ids:
            return []
        async with self.sessions() as session:
            rows = list(
                await session.scalars(
                    select(Signal).where(Signal.id.in_(signal_ids)).order_by(Signal.created_at).limit(limit)
                )
            )
        return [
            {
                "signal_id": str(row.id),
                "signal_type": row.signal_type,
                "statement": row.statement[:500],
                "evidence_text": (row.evidence_text or "")[:500],
                "claim_status": row.claim_status,
                "confidence": row.confidence,
                "human_accurate": "",
                "human_notes": "",
            }
            for row in rows
        ]

    async def _comment_pain_row(self, comment_id: UUID, item: Any) -> dict[str, Any]:
        async with self.sessions() as session:
            comment = await session.get(Comment, comment_id)
            types = list(
                await session.scalars(
                    select(Signal.signal_type).where(Signal.ai_extraction_id == item.extraction_id)
                )
            ) if item.extraction_id else []
        return {
            "comment_id": str(comment_id),
            "comment_excerpt": (comment.text if comment else "")[:240],
            "signal": bool(item.signals_created),
            "signal_types": types,
            "status": item.status,
            "reused": item.reused,
            "human_correct": "",
            "human_notes": "",
        }

    async def _opportunity_rows(self, opportunity_ids: list[UUID]) -> list[dict[str, Any]]:
        if not opportunity_ids:
            return []
        async with self.sessions() as session:
            opportunities = list(
                await session.scalars(
                    select(Opportunity).where(Opportunity.id.in_(opportunity_ids))
                )
            )
            counts = dict(
                (
                    await session.execute(
                        select(
                            OpportunitySignalLink.opportunity_id,
                            func.count(OpportunitySignalLink.id),
                        )
                        .where(OpportunitySignalLink.opportunity_id.in_(opportunity_ids))
                        .group_by(OpportunitySignalLink.opportunity_id)
                    )
                ).all()
            )
        return [
            {
                "opportunity_id": str(item.id),
                "name": item.name,
                "slug": item.slug,
                "customer": item.customer_type,
                "problem": item.problem,
                "solution": item.solution,
                "linked_signal_count": counts.get(item.id, 0),
                "status": item.status,
                "duplicate_notes": "",
            }
            for item in opportunities
        ]

    async def _score_row(self, opportunity_id: UUID, result: Any) -> dict[str, Any]:
        async with self.sessions() as session:
            opportunity = await session.get(Opportunity, opportunity_id)
        trend = result.inputs_snapshot.get("trend", {})
        return {
            "opportunity_id": str(opportunity_id),
            "opportunity": opportunity.name if opportunity else "",
            "score": result.opportunity_score,
            "confidence": result.confidence_score,
            "hype_risk": result.hype_risk_score,
            "momentum_7d": trend.get("momentum_score"),
            "signal_count": len(result.inputs_snapshot.get("signals", [])),
            "video_count": result.inputs_snapshot.get("video_count", 0),
            **result.components.model_dump(mode="json"),
        }


async def preflight(settings: Settings, database_url: str, *, live: bool = False) -> dict[str, Any]:
    _, identity = database_identity(database_url)
    checks: dict[str, Any] = {
        "database": identity,
        "live_requests": live,
        **configuration_status(settings),
    }
    engine = create_database_engine(database_url)
    try:
        async with engine.connect() as connection:
            existing = {
                row
                for row in (
                    await connection.execute(
                        text(
                            "SELECT tablename FROM pg_tables "
                            "WHERE schemaname = 'public' AND tablename = ANY(:names)"
                        ),
                        {"names": sorted(EXPECTED_TABLES)},
                    )
                ).scalars()
            }
        missing = sorted(EXPECTED_TABLES - existing)
        checks["migrations"] = "ready" if not missing else f"missing {len(missing)} tables"
    except Exception:
        checks["migrations"] = "unreachable"
    finally:
        await engine.dispose()

    if not configured(settings.redis_url):
        checks["redis"] = "missing"
    else:
        redis = Redis.from_url(settings.redis_url.get_secret_value())
        try:
            checks["redis"] = "reachable" if await redis.ping() else "unreachable"
        except Exception:
            checks["redis"] = "unreachable"
        finally:
            await redis.aclose()

    if live:
        checks["youtube_live"] = await _youtube_live_preflight(settings)
        checks["openai_live"] = await _openai_live_preflight(settings)
    return checks


def preflight_ready(checks: dict[str, Any]) -> bool:
    required = (
        "YOUTUBE_API_KEY",
        "OPENAI_API_KEY",
        "AI_PROVIDER",
        "AI_MODEL_RELEVANCE",
        "AI_MODEL_SIGNAL_EXTRACTION",
        "AI_MODEL_COMMENT_PAIN_MINING",
        "AI_MODEL_OPPORTUNITY_NORMALIZATION",
    )
    configuration_is_ready = (
        checks.get("migrations") == "ready"
        and checks.get("redis") == "reachable"
        and checks.get("AI_PROVIDER") == "openai"
        and all(checks.get(name) not in {None, "", "missing"} for name in required)
    )
    if not configuration_is_ready:
        return False
    if checks.get("live_requests"):
        return checks.get("youtube_live") == "passed" and checks.get("openai_live") == "passed"
    return True


async def _youtube_live_preflight(settings: Settings) -> str | dict[str, str]:
    if not configured(settings.youtube_api_key):
        return "skipped_missing_key"
    client = YouTubeClient(
        settings.youtube_api_key.get_secret_value(),
        base_url=settings.youtube_api_base_url,
        timeout_seconds=settings.youtube_http_timeout_seconds,
        max_retries=settings.youtube_max_retries,
    )
    try:
        async with client:
            await client.search_videos("AI business", max_results=1)
        return "passed"
    except Exception as error:
        return safe_provider_diagnostic(error, settings)


async def _openai_live_preflight(settings: Settings) -> str | dict[str, str]:
    if not configured(settings.openai_api_key) or not settings.ai_model_relevance:
        return "skipped_missing_configuration"
    client = OpenAIClient(settings.openai_api_key.get_secret_value(), max_retries=0)
    try:
        await client.structured_generate(
            task_type="relevance_filter",
            model=settings.ai_model_relevance,
            system_prompt=load_prompt("relevance-filter", "v001"),
            input_data={
                "video": {
                    "youtube_video_id": "preflight",
                    "title": "AI business workflow",
                    "description": "Minimal provider contract validation.",
                    "published_at": datetime.now(UTC).isoformat(),
                    "duration_seconds": 60,
                    "language": "en",
                    "view_count": 0,
                    "like_count": 0,
                    "comment_count": 0,
                },
                "channel": {"name": "Local validation", "channel_type": None},
            },
            output_model=RelevanceFilterOutput,
        )
        return "passed"
    except Exception as error:
        return safe_provider_diagnostic(error, settings)


def build_services(
    settings: Settings,
    sessions: async_sessionmaker[AsyncSession],
    youtube: YouTubeClient,
    *,
    require_ai: bool,
) -> ServiceBundle:
    base = ServiceBundle(
        discovery=YouTubeDiscoveryService(
            sessions,
            youtube,
            max_quota_units_per_run=settings.youtube_discovery_max_quota_units_per_run,
        ),
        metadata=YouTubeMetadataCollectionService(sessions, youtube),
        comments=YouTubeCommentCollectionService(
            sessions,
            youtube,
            max_quota_units_per_run=settings.youtube_comment_max_quota_units_per_run,
        ),
    )
    if not require_ai:
        return base
    if settings.ai_provider != "openai" or not configured(settings.openai_api_key):
        raise LiveValidationError("AI_PROVIDER=openai and OPENAI_API_KEY are required")
    models = (
        settings.ai_model_relevance,
        settings.ai_model_signal_extraction,
        settings.ai_model_comment_pain_mining,
        settings.ai_model_opportunity_normalization,
    )
    if not all(models):
        raise LiveValidationError("All four AI_MODEL_* settings are required")
    ai = OpenAIClient(
        settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
    )
    return ServiceBundle(
        discovery=base.discovery,
        metadata=base.metadata,
        comments=base.comments,
        relevance=VideoRelevanceService(
            sessions, ai, provider="openai", model=settings.ai_model_relevance
        ),
        signals=BusinessSignalExtractionService(
            sessions,
            ai,
            provider="openai",
            model=settings.ai_model_signal_extraction,
            prompt_version=settings.signal_extractor_prompt_version,
        ),
        comment_pain=CommentPainMiningService(
            sessions, ai, provider="openai", model=settings.ai_model_comment_pain_mining
        ),
        normalization=OpportunityNormalizationService(
            sessions,
            ai,
            provider="openai",
            model=settings.ai_model_opportunity_normalization,
            match_threshold=settings.ai_opportunity_match_threshold,
            create_threshold=settings.ai_opportunity_create_threshold,
        ),
        trends=OpportunityTrendAggregationService(sessions),
        scoring=OpportunityScoringService(sessions),
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Bounded local live API and intelligence validation")
    subcommands = root.add_subparsers(dest="command", required=True)
    preflight_parser = subcommands.add_parser("preflight")
    preflight_parser.add_argument("--live", action="store_true")
    for name in ("youtube", "ai", "full"):
        command = subcommands.add_parser(name)
        if name != "ai":
            command.add_argument("--query", default="AI dental receptionist")
        command.add_argument("--max-videos", type=int, default=10)
        command.add_argument("--max-comments-per-video", type=int, default=20)
        command.add_argument("--max-pages", type=int, default=1)
        command.add_argument("--max-ai-videos", type=int, default=5)
        command.add_argument("--max-ai-comments", type=int, default=20)
        command.add_argument("--max-normalization-signals", type=int, default=20)
        command.add_argument("--stop-after", choices=STAGES)
        command.add_argument("--force-ai", action="store_true")
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--show-sample", action="store_true")
    return root


async def async_main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    settings = Settings()
    database_secret = settings.live_validation_database_url or settings.database_url
    if not configured(database_secret):
        print("ERROR: LIVE_VALIDATION_DATABASE_URL is missing", file=sys.stderr)
        return 2
    database_url = database_secret.get_secret_value()
    try:
        _, identity = database_identity(database_url)
        if arguments.command == "preflight":
            checks = await preflight(settings, database_url, live=arguments.live)
            print(json.dumps(checks, indent=2))
            return 0 if preflight_ready(checks) else 1

        limits = ValidationLimits(
            max_videos=arguments.max_videos,
            max_comments_per_video=arguments.max_comments_per_video,
            max_pages=arguments.max_pages,
            max_ai_videos=arguments.max_ai_videos,
            max_ai_comments=arguments.max_ai_comments,
            max_normalization_signals=arguments.max_normalization_signals,
        )
        limits.validate()
        if arguments.dry_run:
            engine = create_database_engine(database_url)
            sessions = create_session_factory(engine)
            # Dry-run uses no live clients or service calls.
            runner = LiveValidationRunner(settings, sessions, services=None)  # type: ignore[arg-type]
            report, directory = await runner.run(
                command=arguments.command,
                query=getattr(arguments, "query", None),
                limits=limits,
                stop_after=arguments.stop_after,
                force_ai=arguments.force_ai,
                dry_run=True,
                show_sample=arguments.show_sample,
                identity=identity,
            )
            await engine.dispose()
        else:
            if arguments.command in {"youtube", "full"} and not configured(
                settings.youtube_api_key
            ):
                raise LiveValidationError("YOUTUBE_API_KEY is required")
            checks = await preflight(settings, database_url, live=False)
            if checks["migrations"] != "ready":
                raise LiveValidationError("Database migrations are not ready")
            if checks["redis"] != "reachable":
                raise LiveValidationError("REDIS_URL is missing or unreachable")
            engine = create_database_engine(database_url)
            sessions = create_session_factory(engine)
            youtube_key = (
                settings.youtube_api_key.get_secret_value()
                if configured(settings.youtube_api_key)
                else "unused-local-ai-validation"
            )
            youtube = YouTubeClient(
                youtube_key,
                base_url=settings.youtube_api_base_url,
                timeout_seconds=settings.youtube_http_timeout_seconds,
                max_retries=settings.youtube_max_retries,
            )
            try:
                services = build_services(
                    settings,
                    sessions,
                    youtube,
                    require_ai=arguments.command in {"ai", "full"},
                )
                runner = LiveValidationRunner(settings, sessions, services)
                async with youtube:
                    report, directory = await runner.run(
                        command=arguments.command,
                        query=getattr(arguments, "query", None),
                        limits=limits,
                        stop_after=arguments.stop_after,
                        force_ai=arguments.force_ai,
                        dry_run=False,
                        show_sample=arguments.show_sample,
                        identity=identity,
                    )
            finally:
                await engine.dispose()
        print(f"Database: {identity['host']} / {identity['database']}")
        print(f"Completed stages: {', '.join(report.stages_completed) or 'none'}")
        print(f"Report: {directory}")
        print("Radar may be empty until the normal review/activation workflow is completed.")
        return 1 if report.failures else 0
    except LiveValidationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(argv))
