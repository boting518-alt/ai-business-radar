import asyncio

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.repositories import SearchQueryRepository
from apscheduler.schedulers.blocking import BlockingScheduler

from ..broker import initialize_broker
from ..config import WorkerSettings


async def enqueue_scheduled_discovery(settings: WorkerSettings) -> int:
    from ..actors.youtube_discovery import run_youtube_discovery

    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        async with create_session_factory(engine)() as session:
            queries = await SearchQueryRepository(session).list_enabled_discovery(
                limit=settings.youtube_discovery_schedule_batch_size
            )
        for query in queries:
            run_youtube_discovery.send(search_query_id=str(query.id))
        return len(queries)
    finally:
        await engine.dispose()


def enqueue_scheduled_trends(settings: WorkerSettings) -> int:
    from ..actors.trends import run_trend_aggregation

    for window_type in ("7d", "30d", "90d"):
        run_trend_aggregation.send(
            window_type=window_type, limit=settings.trend_aggregation_batch_size
        )
    return 3


def build_scheduler(settings: WorkerSettings) -> BlockingScheduler:
    from ..actors import (
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
    return scheduler


def main() -> None:
    settings = WorkerSettings()
    initialize_broker(settings)
    build_scheduler(settings).start()
