import logging
from datetime import datetime
from uuid import UUID

import dramatiq
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.services.discovery_operations import DiscoveryOperationsService
from ai_business_radar_api.services.youtube_discovery import (
    DiscoveryRequest,
    InvalidDiscoveryMode,
    SearchQueryDisabled,
    SearchQueryNotFound,
    YouTubeDiscoveryService,
)
from pydantic import ValidationError

from ..config import WorkerSettings
from ..lifecycle import collection_dependencies
from .runtime import run_async

logger = logging.getLogger(__name__)


async def execute_discovery(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    request = DiscoveryRequest(
        search_query_id=UUID(payload["search_query_id"]),
        collection_run_id=(
            UUID(payload["collection_run_id"]) if payload.get("collection_run_id") else None
        ),
        max_pages=payload.get("max_pages", 1),
        max_results=payload.get("max_results", 50),
        order=payload.get("order", "date"),
        published_after=(
            datetime.fromisoformat(payload["published_after"])
            if payload.get("published_after")
            else None
        ),
    )
    async with collection_dependencies(runtime) as (sessions, youtube):
        return await YouTubeDiscoveryService(
            sessions,
            youtube,
            max_quota_units_per_run=runtime.youtube_discovery_max_quota_units_per_run,
        ).discover(request)


async def execute_discovery_safely(payload: dict, settings: WorkerSettings | None = None):
    runtime = settings or WorkerSettings()
    try:
        return await execute_discovery(payload, runtime)
    except (
        ValidationError,
        ValueError,
        SearchQueryNotFound,
        SearchQueryDisabled,
        InvalidDiscoveryMode,
    ) as error:
        run_value = payload.get("collection_run_id")
        location = None
        message = str(error).splitlines()[0][:200]
        if isinstance(error, ValidationError) and error.errors():
            detail = error.errors()[0]
            location = ".".join(str(part) for part in detail.get("loc", ()))
            message = str(detail.get("msg", "Invalid discovery request"))[:200]
        logger.error(
            "permanent_collection_job_failure actor=youtube_discovery run_id=%s "
            "query_id=%s error_type=%s validation_location=%s validation_message=%s",
            run_value,
            payload.get("search_query_id"),
            type(error).__name__,
            location,
            message,
        )
        if run_value:
            engine = create_database_engine(runtime.database_url.get_secret_value())
            try:
                await DiscoveryOperationsService(create_session_factory(engine)).finalize_failure(
                    UUID(run_value),
                    error_code="invalid_discovery_request",
                    safe_message=message,
                )
            finally:
                await engine.dispose()
        return None


@dramatiq.actor(queue_name="youtube_discovery", max_retries=2, min_backoff=5000)
def run_youtube_discovery(**payload):
    result = run_async(lambda: execute_discovery_safely(payload))
    logger.info(
        "youtube_discovery_actor_finished status=%s", getattr(result, "status", "permanent_error")
    )
