"""Admin discovery topic configuration and asynchronous run orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.database.models import (
    CollectionRun,
    DiscoveryTopic,
    DiscoveryTopicRun,
    SearchQuery,
)

Schedule = Literal["manual", "6h", "12h", "daily", "weekly"]


class DiscoveryQueryInput(BaseModel):
    query_text: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    max_videos: int | None = Field(None, ge=1, le=100)
    max_pages: int | None = Field(None, ge=1, le=5)
    max_comments_per_video: int | None = Field(None, ge=0, le=100)
    schedule_override: Schedule | None = None

    @field_validator("query_text")
    @classmethod
    def clean_query(cls, value: str) -> str:
        return value.strip()


class DiscoveryQueryCreate(DiscoveryQueryInput):
    topic_id: UUID


class DiscoveryQueryPatch(BaseModel):
    query_text: str | None = Field(None, min_length=1, max_length=200)
    enabled: bool | None = None
    max_videos: int | None = Field(None, ge=1, le=100)
    max_pages: int | None = Field(None, ge=1, le=5)
    max_comments_per_video: int | None = Field(None, ge=0, le=100)
    schedule_override: Schedule | None = None


class DiscoveryTopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(None, max_length=2000)
    status: Literal["active", "paused"] = "paused"
    default_schedule: Schedule = "manual"
    default_max_videos: int = Field(25, ge=1, le=100)
    default_max_pages: int = Field(1, ge=1, le=5)
    default_max_comments_per_video: int = Field(20, ge=0, le=100)
    queries: list[DiscoveryQueryInput] = Field(default_factory=list, max_length=20)


class DiscoveryTopicPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=160)
    description: str | None = Field(None, max_length=2000)
    status: Literal["active", "paused", "archived"] | None = None
    default_schedule: Schedule | None = None
    default_max_videos: int | None = Field(None, ge=1, le=100)
    default_max_pages: int | None = Field(None, ge=1, le=5)
    default_max_comments_per_video: int | None = Field(None, ge=0, le=100)


class DiscoveryQueryConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    topic_id: UUID
    query_text: str
    enabled: bool
    query_group: str
    discovery_mode: str
    max_videos: int | None
    max_pages: int | None
    max_comments_per_video: int | None
    schedule_override: str | None
    last_run_at: datetime | None


class DiscoveryRunSummary(BaseModel):
    id: UUID
    topic_id: UUID | None
    query_id: UUID | None
    query_text: str | None
    trigger_type: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    videos_discovered: int
    quota_estimate: int | None
    error_code: str | None = None
    error_message_safe: str | None
    worker_message_id: str | None
    topic_run_id: UUID | None = None


class DiscoveryTopicRunSummary(BaseModel):
    id: UUID
    topic_id: UUID
    trigger_type: str
    status: str
    requested_query_count: int
    queued_query_count: int
    queued: int
    running: int
    completed: int
    partial: int
    failed: int
    terminal_count: int
    quota_estimate: int
    started_at: datetime
    completed_at: datetime | None


class DiscoveryTopicRunDetail(DiscoveryTopicRunSummary):
    runs: list[DiscoveryRunSummary]


class DiscoveryTopicSummary(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: str
    default_schedule: str
    default_max_videos: int
    default_max_pages: int
    default_max_comments_per_video: int
    query_count: int
    last_run_at: datetime | None
    next_run_at: datetime | None
    latest_run: DiscoveryRunSummary | None = None
    current_topic_run: DiscoveryTopicRunSummary | None = None


class DiscoveryTopicDetail(DiscoveryTopicSummary):
    queries: list[DiscoveryQueryConfig]
    recent_runs: list[DiscoveryRunSummary]


class DiscoveryRunPage(BaseModel):
    items: list[DiscoveryRunSummary]
    total: int
    page: int
    page_size: int


class DiscoverySystemStatus(BaseModel):
    redis: Literal["configured", "unconfigured"]
    worker: Literal["unknown"] = "unknown"
    scheduler: Literal["configured"] = "configured"
    youtube_api: Literal["configured", "unconfigured"]
    openai_api: Literal["configured", "unconfigured"]
    runtime_profile: str
    database_host: str | None
    database_name: str | None
    redis_host: str | None
    config_fingerprint: str


class StaleRunRecoveryRequest(BaseModel):
    dry_run: bool = True
    limit: int = Field(100, ge=1, le=500)


class StaleRunRecoveryResult(BaseModel):
    queued_stale: int
    running_stale: int
    would_mark_failed: int
    marked_failed: int


QUEUED_STALE_AFTER = timedelta(minutes=15)
RUNNING_STALE_AFTER = timedelta(minutes=60)


class DiscoveryConflict(RuntimeError):
    pass


class DiscoveryNotFound(RuntimeError):
    pass


def next_run(schedule: str, now: datetime | None = None) -> datetime | None:
    base = now or datetime.now(UTC)
    delta = {
        "6h": timedelta(hours=6),
        "12h": timedelta(hours=12),
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
    }.get(schedule)
    return base + delta if delta else None


class DiscoveryOperationsService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]):
        self.sessions = sessions

    async def create(self, actor: UUID, body: DiscoveryTopicCreate) -> DiscoveryTopicDetail:
        normalized = [q.query_text.casefold() for q in body.queries]
        if len(normalized) != len(set(normalized)):
            raise DiscoveryConflict("Duplicate query in topic")
        async with self.sessions() as session, session.begin():
            created_at = datetime.now(UTC)
            topic = DiscoveryTopic(
                **body.model_dump(exclude={"queries"}),
                created_by=actor,
                next_run_at=next_run(body.default_schedule) if body.status == "active" else None,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(topic)
            await session.flush()
            for query in body.queries:
                session.add(
                    SearchQuery(
                        query=query.query_text,
                        topic_id=topic.id,
                        query_group="discovery",
                        discovery_mode="discovery",
                        priority=0,
                        language=None,
                        region=None,
                        last_run_at=None,
                        created_at=created_at,
                        updated_at=created_at,
                        **query.model_dump(exclude={"query_text"}),
                    )
                )
        return await self.detail(topic.id)

    async def list(self) -> list[DiscoveryTopicSummary]:
        async with self.sessions() as session:
            topics = list(
                await session.scalars(
                    select(DiscoveryTopic).order_by(DiscoveryTopic.updated_at.desc())
                )
            )
            counts = (
                dict(
                    (
                        await session.execute(
                            select(SearchQuery.topic_id, func.count())
                            .where(SearchQuery.topic_id.in_([x.id for x in topics]))
                            .group_by(SearchQuery.topic_id)
                        )
                    ).all()
                )
                if topics
                else {}
            )
            runs = await self._latest_runs(session, [x.id for x in topics])
            batches = await self._latest_topic_runs(session, [x.id for x in topics])
            return [
                self._topic(x, counts.get(x.id, 0), runs.get(x.id), batches.get(x.id))
                for x in topics
            ]

    async def detail(self, topic_id: UUID) -> DiscoveryTopicDetail:
        async with self.sessions() as session:
            topic = await session.get(DiscoveryTopic, topic_id)
            if not topic:
                raise DiscoveryNotFound()
            queries = list(
                await session.scalars(
                    select(SearchQuery)
                    .where(SearchQuery.topic_id == topic_id)
                    .order_by(SearchQuery.created_at)
                )
            )
            runs = (await self.runs(topic_id=topic_id, page=1, page_size=20)).items
            batches = await self._latest_topic_runs(session, [topic_id])
            base = self._topic(
                topic, len(queries), runs[0] if runs else None, batches.get(topic_id)
            ).model_dump()
            return DiscoveryTopicDetail(
                **base, queries=[self._query(x) for x in queries], recent_runs=runs
            )

    async def patch(self, topic_id: UUID, body: DiscoveryTopicPatch) -> DiscoveryTopicDetail:
        values = body.model_dump(exclude_unset=True)
        values["updated_at"] = datetime.now(UTC)
        if values.get("status") in {"paused", "archived"}:
            values["next_run_at"] = None
        elif values.get("status") == "active" or "default_schedule" in values:
            values["next_run_at"] = next_run(values.get("default_schedule", "manual"))
        async with self.sessions() as session, session.begin():
            result = await session.execute(
                update(DiscoveryTopic)
                .where(DiscoveryTopic.id == topic_id)
                .values(**values)
                .returning(DiscoveryTopic.id)
            )
            if result.scalar_one_or_none() is None:
                raise DiscoveryNotFound()
        return await self.detail(topic_id)

    async def duplicate(self, topic_id: UUID, actor: UUID) -> DiscoveryTopicDetail:
        source = await self.detail(topic_id)
        return await self.create(
            actor,
            DiscoveryTopicCreate(
                name=f"{source.name} Copy",
                description=source.description,
                status="paused",
                default_schedule=source.default_schedule,
                default_max_videos=source.default_max_videos,
                default_max_pages=source.default_max_pages,
                default_max_comments_per_video=source.default_max_comments_per_video,
                queries=[
                    DiscoveryQueryInput(
                        **q.model_dump(
                            include={
                                "query_text",
                                "enabled",
                                "max_videos",
                                "max_pages",
                                "max_comments_per_video",
                                "schedule_override",
                            }
                        )
                    )
                    for q in source.queries
                ],
            ),
        )

    async def add_query(self, body: DiscoveryQueryCreate) -> DiscoveryQueryConfig:
        async with self.sessions() as session, session.begin():
            if not await session.get(DiscoveryTopic, body.topic_id):
                raise DiscoveryNotFound()
            query = SearchQuery(
                query=body.query_text,
                topic_id=body.topic_id,
                query_group="discovery",
                discovery_mode="discovery",
                priority=0,
                language=None,
                region=None,
                last_run_at=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                **body.model_dump(exclude={"topic_id", "query_text"}),
            )
            session.add(query)
            try:
                await session.flush()
            except IntegrityError as error:
                raise DiscoveryConflict("Duplicate query in topic") from error
            return self._query(query)

    async def patch_query(self, query_id: UUID, body: DiscoveryQueryPatch) -> DiscoveryQueryConfig:
        values = body.model_dump(exclude_unset=True)
        if "query_text" in values:
            values["query"] = values.pop("query_text").strip()
        values["updated_at"] = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            query = await session.get(SearchQuery, query_id)
            if not query or not query.topic_id:
                raise DiscoveryNotFound()
            for key, value in values.items():
                setattr(query, key, value)
            try:
                await session.flush()
            except IntegrityError as error:
                raise DiscoveryConflict("Duplicate query in topic") from error
            return self._query(query)

    async def run_detail(self, run_id: UUID) -> DiscoveryRunSummary:
        async with self.sessions() as session:
            row = (
                await session.execute(
                    select(CollectionRun, SearchQuery.query)
                    .outerjoin(SearchQuery, SearchQuery.id == CollectionRun.search_query_id)
                    .where(CollectionRun.id == run_id, CollectionRun.run_type == "discovery")
                )
            ).one_or_none()
            if row is None:
                raise DiscoveryNotFound()
            return self._run(row[0], row[1])

    async def queue_run(self, query_id: UUID, trigger: str) -> tuple[DiscoveryRunSummary, dict]:
        async with self.sessions() as session, session.begin():
            query = await session.get(SearchQuery, query_id)
            if not query or not query.topic_id:
                raise DiscoveryNotFound()
            topic = await session.get(DiscoveryTopic, query.topic_id)
            if topic.status == "archived" or not query.enabled:
                raise DiscoveryConflict("Query is not runnable")
            run = CollectionRun(
                source_type="youtube",
                run_type="discovery",
                status="pending",
                search_query_id=query.id,
                discovery_topic_id=topic.id,
                trigger_type=trigger,
                items_discovered=0,
                items_processed=0,
                items_failed=0,
                metadata_={"quota_estimate": 0},
                created_at=datetime.now(UTC),
            )
            session.add(run)
            try:
                await session.flush()
            except IntegrityError as error:
                raise DiscoveryConflict("Discovery query already queued or running") from error
            topic.last_run_at = datetime.now(UTC)
            payload = {
                "discovery_run_id": str(run.id),
                "topic_run_id": None,
                "query_id": str(query.id),
                "payload": {
                    "max_pages": query.max_pages or topic.default_max_pages,
                    "max_results": query.max_videos or topic.default_max_videos,
                },
            }
            return self._run(run, query.query), payload

    async def create_topic_run(
        self, topic_id: UUID, trigger: str
    ) -> tuple[DiscoveryTopicRunDetail, list[tuple[UUID, dict]]]:
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            topic = await session.get(DiscoveryTopic, topic_id, with_for_update=True)
            if not topic:
                raise DiscoveryNotFound()
            if topic.status == "archived":
                raise DiscoveryConflict("Topic is not runnable")
            active = await session.scalar(
                select(DiscoveryTopicRun.id).where(
                    DiscoveryTopicRun.topic_id == topic_id,
                    DiscoveryTopicRun.status.in_(("queued", "running")),
                )
            )
            if active:
                raise DiscoveryConflict("Discovery topic already queued or running")
            queries = list(
                await session.scalars(
                    select(SearchQuery)
                    .where(SearchQuery.topic_id == topic_id, SearchQuery.enabled.is_(True))
                    .order_by(SearchQuery.created_at)
                )
            )
            if not queries:
                raise DiscoveryConflict("Topic has no enabled queries")
            active_child = await session.scalar(
                select(CollectionRun.id).where(
                    CollectionRun.search_query_id.in_([query.id for query in queries]),
                    CollectionRun.status.in_(("pending", "running")),
                )
            )
            if active_child:
                raise DiscoveryConflict("Topic has an active legacy query run")
            batch = DiscoveryTopicRun(
                topic_id=topic_id,
                trigger_type=trigger,
                status="queued",
                requested_query_count=len(queries),
                queued_query_count=0,
                started_at=now,
                completed_at=None,
                created_at=now,
            )
            session.add(batch)
            await session.flush()
            payloads: list[tuple[UUID, dict]] = []
            for query in queries:
                run = CollectionRun(
                    source_type="youtube",
                    run_type="discovery",
                    status="pending",
                    search_query_id=query.id,
                    discovery_topic_id=topic.id,
                    topic_run_id=batch.id,
                    trigger_type=trigger,
                    items_discovered=0,
                    items_processed=0,
                    items_failed=0,
                    metadata_={"quota_estimate": 0},
                    created_at=now,
                )
                session.add(run)
                await session.flush()
                payloads.append(
                    (
                        run.id,
                        {
                            "discovery_run_id": str(run.id),
                            "topic_run_id": str(batch.id),
                            "query_id": str(query.id),
                            "payload": {
                                "max_pages": query.max_pages or topic.default_max_pages,
                                "max_results": query.max_videos or topic.default_max_videos,
                            },
                        },
                    )
                )
            topic.last_run_at = now
        return await self.topic_run_detail(batch.id), payloads

    async def topic_run_detail(self, topic_run_id: UUID) -> DiscoveryTopicRunDetail:
        async with self.sessions() as session:
            batch = await session.get(DiscoveryTopicRun, topic_run_id)
            if not batch:
                raise DiscoveryNotFound()
            rows = (
                await session.execute(
                    select(CollectionRun, SearchQuery.query)
                    .outerjoin(SearchQuery, SearchQuery.id == CollectionRun.search_query_id)
                    .where(CollectionRun.topic_run_id == topic_run_id)
                    .order_by(CollectionRun.created_at)
                )
            ).all()
            return self._topic_run(batch, [self._run(run, query) for run, query in rows])

    async def topic_runs(self, topic_id: UUID) -> list[DiscoveryTopicRunSummary]:
        async with self.sessions() as session:
            if not await session.get(DiscoveryTopic, topic_id):
                raise DiscoveryNotFound()
            batches = list(
                await session.scalars(
                    select(DiscoveryTopicRun)
                    .where(DiscoveryTopicRun.topic_id == topic_id)
                    .order_by(DiscoveryTopicRun.created_at.desc())
                )
            )
        return [await self.topic_run_detail(batch.id) for batch in batches]

    async def increment_queued(self, topic_run_id: UUID) -> None:
        async with self.sessions() as session, session.begin():
            await session.execute(
                update(DiscoveryTopicRun)
                .where(DiscoveryTopicRun.id == topic_run_id)
                .values(queued_query_count=DiscoveryTopicRun.queued_query_count + 1)
            )

    async def refresh_topic_run(self, topic_run_id: UUID) -> DiscoveryTopicRunDetail:
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            batch = await session.get(DiscoveryTopicRun, topic_run_id, with_for_update=True)
            if not batch:
                raise DiscoveryNotFound()
            statuses = list(
                await session.scalars(
                    select(CollectionRun.status).where(CollectionRun.topic_run_id == topic_run_id)
                )
            )
            if any(value in {"pending", "running"} for value in statuses):
                batch.status = "running" if "running" in statuses else "queued"
                batch.completed_at = None
            else:
                completed = sum(value == "completed" for value in statuses)
                failed = sum(value == "failed" for value in statuses)
                if completed == len(statuses):
                    batch.status = "completed"
                elif failed == len(statuses):
                    batch.status = "failed"
                else:
                    batch.status = "partial"
                batch.completed_at = now
        return await self.topic_run_detail(topic_run_id)

    async def refresh_batch_for_run(self, run_id: UUID) -> None:
        async with self.sessions() as session:
            topic_run_id = await session.scalar(
                select(CollectionRun.topic_run_id).where(CollectionRun.id == run_id)
            )
        if topic_run_id:
            await self.refresh_topic_run(topic_run_id)

    async def runs(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        topic_id: UUID | None = None,
        query_id: UUID | None = None,
    ) -> DiscoveryRunPage:
        async with self.sessions() as session:
            base = (
                select(CollectionRun, SearchQuery.query)
                .outerjoin(SearchQuery, SearchQuery.id == CollectionRun.search_query_id)
                .where(CollectionRun.run_type == "discovery")
            )
            if status:
                base = base.where(CollectionRun.status == status)
            if topic_id:
                base = base.where(CollectionRun.discovery_topic_id == topic_id)
            if query_id:
                base = base.where(CollectionRun.search_query_id == query_id)
            total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
            rows = (
                await session.execute(
                    base.order_by(CollectionRun.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
            return DiscoveryRunPage(
                items=[self._run(r, q) for r, q in rows],
                total=total,
                page=page,
                page_size=page_size,
            )

    async def mark_message(self, run_id: UUID, message_id: str) -> None:
        async with self.sessions() as session, session.begin():
            await session.execute(
                update(CollectionRun)
                .where(CollectionRun.id == run_id)
                .values(worker_message_id=message_id)
            )

    async def mark_enqueue_failed(self, run_id: UUID) -> None:
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            await session.execute(
                update(CollectionRun)
                .where(CollectionRun.id == run_id, CollectionRun.status == "pending")
                .values(
                    status="failed",
                    started_at=now,
                    finished_at=now,
                    error_summary="queue_unavailable",
                )
            )
        await self.refresh_batch_for_run(run_id)

    async def finalize_failure(self, run_id: UUID, *, error_code: str, safe_message: str) -> bool:
        """Idempotently move only an active discovery run to failed."""
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            current = await session.get(CollectionRun, run_id, with_for_update=True)
            if current is None or current.run_type != "discovery":
                return False
            if current.status not in {"pending", "running"}:
                return False
            metadata = dict(current.metadata_ or {})
            metadata["error_code"] = error_code
            current.status = "failed"
            current.started_at = current.started_at or now
            current.finished_at = now
            current.error_summary = safe_message[:500]
            current.metadata_ = metadata
        await self.refresh_batch_for_run(run_id)
        return True

    async def recover_stale(
        self, body: StaleRunRecoveryRequest, *, now: datetime | None = None
    ) -> StaleRunRecoveryResult:
        clock = now or datetime.now(UTC)
        affected_batches: set[UUID] = set()
        async with self.sessions() as session, session.begin():
            rows = list(
                await session.scalars(
                    select(CollectionRun)
                    .where(
                        CollectionRun.run_type == "discovery",
                        (
                            (CollectionRun.status == "pending")
                            & (CollectionRun.created_at < clock - QUEUED_STALE_AFTER)
                        )
                        | (
                            (CollectionRun.status == "running")
                            & (CollectionRun.started_at < clock - RUNNING_STALE_AFTER)
                        ),
                    )
                    .order_by(CollectionRun.created_at)
                    .limit(body.limit)
                    .with_for_update(skip_locked=True)
                )
            )
            queued = sum(row.status == "pending" for row in rows)
            running = sum(row.status == "running" for row in rows)
            if not body.dry_run:
                for row in rows:
                    if row.topic_run_id:
                        affected_batches.add(row.topic_run_id)
                    metadata = dict(row.metadata_ or {})
                    metadata["error_code"] = "stale_run_recovered"
                    row.status = "failed"
                    row.started_at = row.started_at or clock
                    row.finished_at = clock
                    row.error_summary = "Stale discovery run recovered"
                    row.metadata_ = metadata
            result = StaleRunRecoveryResult(
                queued_stale=queued,
                running_stale=running,
                would_mark_failed=len(rows),
                marked_failed=0 if body.dry_run else len(rows),
            )
        for topic_run_id in affected_batches:
            await self.refresh_topic_run(topic_run_id)
        return result

    async def _latest_runs(self, session, ids):
        if not ids:
            return {}
        rows = list(
            await session.scalars(
                select(CollectionRun)
                .distinct(CollectionRun.discovery_topic_id)
                .where(
                    CollectionRun.discovery_topic_id.in_(ids), CollectionRun.run_type == "discovery"
                )
                .order_by(CollectionRun.discovery_topic_id, CollectionRun.created_at.desc())
            )
        )
        return {r.discovery_topic_id: self._run(r, None) for r in rows}

    async def _latest_topic_runs(self, session, ids):
        if not ids:
            return {}
        batches = list(
            await session.scalars(
                select(DiscoveryTopicRun)
                .distinct(DiscoveryTopicRun.topic_id)
                .where(DiscoveryTopicRun.topic_id.in_(ids))
                .order_by(DiscoveryTopicRun.topic_id, DiscoveryTopicRun.created_at.desc())
            )
        )
        if not batches:
            return {}
        rows = (
            (
                await session.execute(
                    select(CollectionRun).where(
                        CollectionRun.topic_run_id.in_([batch.id for batch in batches])
                    )
                )
            )
            .scalars()
            .all()
        )
        by_batch = {batch.id: [] for batch in batches}
        for run in rows:
            by_batch[run.topic_run_id].append(self._run(run, None))
        return {batch.topic_id: self._topic_run(batch, by_batch[batch.id]) for batch in batches}

    def _topic(self, x, count, run=None, topic_run=None):
        return DiscoveryTopicSummary(
            id=x.id,
            name=x.name,
            description=x.description,
            status=x.status,
            default_schedule=x.default_schedule,
            default_max_videos=x.default_max_videos,
            default_max_pages=x.default_max_pages,
            default_max_comments_per_video=x.default_max_comments_per_video,
            query_count=count,
            last_run_at=x.last_run_at,
            next_run_at=x.next_run_at,
            latest_run=run,
            current_topic_run=topic_run,
        )

    def _query(self, x):
        return DiscoveryQueryConfig(
            id=x.id,
            topic_id=x.topic_id,
            query_text=x.query,
            enabled=x.enabled,
            query_group=x.query_group,
            discovery_mode=x.discovery_mode,
            max_videos=x.max_videos,
            max_pages=x.max_pages,
            max_comments_per_video=x.max_comments_per_video,
            schedule_override=x.schedule_override,
            last_run_at=x.last_run_at,
        )

    def _run(self, x, query):
        meta = x.metadata_ or {}
        return DiscoveryRunSummary(
            id=x.id,
            topic_id=x.discovery_topic_id,
            query_id=x.search_query_id,
            query_text=query,
            trigger_type=x.trigger_type or "scheduled",
            status="queued" if x.status == "pending" else x.status,
            started_at=x.started_at,
            completed_at=x.finished_at,
            videos_discovered=x.items_discovered,
            quota_estimate=meta.get("estimated_quota_units", meta.get("quota_estimate")),
            error_code=meta.get("error_code"),
            error_message_safe=x.error_summary,
            worker_message_id=x.worker_message_id,
            topic_run_id=x.topic_run_id,
        )

    def _topic_run(self, batch, runs):
        counts = {key: 0 for key in ("queued", "running", "completed", "partial", "failed")}
        for run in runs:
            if run.status in counts:
                counts[run.status] += 1
        return DiscoveryTopicRunDetail(
            id=batch.id,
            topic_id=batch.topic_id,
            trigger_type=batch.trigger_type,
            status=batch.status,
            requested_query_count=batch.requested_query_count,
            queued_query_count=batch.queued_query_count,
            **counts,
            terminal_count=counts["completed"] + counts["partial"] + counts["failed"],
            quota_estimate=sum(run.quota_estimate or 0 for run in runs),
            started_at=batch.started_at,
            completed_at=batch.completed_at,
            runs=runs,
        )
