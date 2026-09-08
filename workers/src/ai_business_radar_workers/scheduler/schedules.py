import asyncio
from datetime import UTC, datetime

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import DiscoveryTopic, SearchQuery
from ai_business_radar_api.infrastructure.database.repositories import SearchQueryRepository
from ai_business_radar_api.services.discovery_operations import (
    DiscoveryConflict,
    DiscoveryOperationsService,
    next_run,
)
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import select, update

from ..broker import initialize_broker
from ..config import WorkerSettings


async def enqueue_scheduled_discovery(settings: WorkerSettings) -> int:
    from ..actors.youtube_discovery import run_youtube_discovery

    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        factory = create_session_factory(engine)
        now = datetime.now(UTC)
        async with factory() as session:
            managed = await SearchQueryRepository(session).list_enabled_discovery(
                limit=settings.youtube_discovery_schedule_batch_size
            )
            legacy = [query for query in managed if getattr(query, "topic_id", None) is None]
            if not hasattr(session, "scalars"):
                for query in legacy:
                    run_youtube_discovery.send(search_query_id=str(query.id))
                return len(legacy)
            queries = list(
                await session.scalars(
                    select(SearchQuery)
                    .join(DiscoveryTopic, DiscoveryTopic.id == SearchQuery.topic_id)
                    .where(
                        DiscoveryTopic.status == "active",
                        DiscoveryTopic.default_schedule != "manual",
                        DiscoveryTopic.next_run_at <= now,
                        SearchQuery.enabled.is_(True),
                        SearchQuery.discovery_mode == "discovery",
                    )
                    .order_by(DiscoveryTopic.next_run_at)
                    .limit(settings.youtube_discovery_schedule_batch_size)
                )
            )
        queued = 0
        for query in legacy:
            run_youtube_discovery.send(search_query_id=str(query.id))
            queued += 1
        ops = DiscoveryOperationsService(factory)
        for query in queries:
            try:
                run, payload = await ops.queue_run(query.id, "scheduled")
                message = run_youtube_discovery.send(**payload)
                await ops.mark_message(run.id, str(message.message_id))
                queued += 1
            except DiscoveryConflict:
                continue
        topic_ids = {query.topic_id for query in queries}
        async with factory() as session, session.begin():
            for topic_id in topic_ids:
                topic = await session.get(DiscoveryTopic, topic_id)
                await session.execute(
                    update(DiscoveryTopic)
                    .where(DiscoveryTopic.id == topic_id)
                    .values(last_run_at=now, next_run_at=next_run(topic.default_schedule, now))
                )
        return queued
    finally:
        await engine.dispose()


def enqueue_scheduled_trends(settings: WorkerSettings) -> int:
    from ..actors.trends import run_trend_aggregation

    for window_type in ("7d", "30d", "90d"):
        run_trend_aggregation.send(
            window_type=window_type, limit=settings.trend_aggregation_batch_size
        )
    return 3


def enqueue_scheduled_scoring(settings: WorkerSettings) -> None:
    from ..actors.scoring import run_opportunity_scoring

    run_opportunity_scoring.send(limit=settings.opportunity_scoring_batch_size)


def build_scheduler(settings: WorkerSettings) -> BlockingScheduler:
    from ..actors import (
        reconcile_translation_coverage,
        recover_stale_collection_claims,
        run_youtube_comment_collection,
        run_youtube_metadata_collection,
    )

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        lambda: asyncio.run(enqueue_scheduled_discovery(settings)),
        "interval",
        minutes=settings.youtube_discovery_schedule_minutes,
        id="youtube_discovery",
        max_instances=1,
    )
    scoring_hour = (
        settings.trend_aggregation_schedule_hour_utc
        + settings.opportunity_scoring_schedule_delay_minutes // 60
    ) % 24
    scoring_minute = settings.opportunity_scoring_schedule_delay_minutes % 60
    scheduler.add_job(
        lambda: enqueue_scheduled_scoring(settings),
        "cron",
        hour=scoring_hour,
        minute=scoring_minute,
        id="opportunity_scoring",
        max_instances=1,
    )
    scheduler.add_job(
        lambda: enqueue_scheduled_trends(settings),
        "cron",
        hour=settings.trend_aggregation_schedule_hour_utc,
        minute=0,
        id="trend_aggregation",
        max_instances=1,
    )
    scheduler.add_job(
        lambda: run_youtube_metadata_collection.send(limit=settings.youtube_metadata_batch_size),
        "interval",
        minutes=settings.youtube_metadata_schedule_minutes,
        id="youtube_metadata",
        max_instances=1,
    )
    scheduler.add_job(
        lambda: run_youtube_comment_collection.send(
            limit_videos=settings.youtube_comment_batch_size
        ),
        "interval",
        minutes=settings.youtube_comment_schedule_minutes,
        id="youtube_comments",
        max_instances=1,
    )
    scheduler.add_job(
        lambda: recover_stale_collection_claims.send(),
        "interval",
        minutes=settings.youtube_stale_recovery_schedule_minutes,
        id="stale_claim_recovery",
        max_instances=1,
    )
    scheduler.add_job(
        lambda: reconcile_translation_coverage.send(
            limit=settings.translation_reconciliation_batch_size
        ),
        "interval",
        minutes=settings.translation_reconciliation_schedule_minutes,
        id="translation_reconciliation",
        max_instances=1,
    )
    return scheduler


def main() -> None:
    settings = WorkerSettings()
    initialize_broker(settings)
    build_scheduler(settings).start()
