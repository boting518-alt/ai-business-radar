"""Admin discovery topic configuration and asynchronous run orchestration."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..infrastructure.database.models import CollectionRun, DiscoveryTopic, SearchQuery

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
    error_message_safe: str | None
    worker_message_id: str | None


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
            return [self._topic(x, counts.get(x.id, 0), runs.get(x.id)) for x in topics]

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
            base = self._topic(topic, len(queries), runs[0] if runs else None).model_dump()
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
                "search_query_id": str(query.id),
                "collection_run_id": str(run.id),
                "max_pages": query.max_pages or topic.default_max_pages,
                "max_results": query.max_videos or topic.default_max_videos,
            }
            return self._run(run, query.query), payload

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
        async with self.sessions() as session, session.begin():
            await session.execute(
                update(CollectionRun)
                .where(CollectionRun.id == run_id, CollectionRun.status == "pending")
                .values(
                    status="failed",
                    finished_at=datetime.now(UTC),
                    error_summary="queue_unavailable",
                )
            )

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

    def _topic(self, x, count, run=None):
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
            error_message_safe=x.error_summary,
            worker_message_id=x.worker_message_id,
        )
