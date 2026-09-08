import asyncio
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
from pydantic import BaseModel, ConfigDict, ValidationError

from ..config import WorkerSettings
from ..lifecycle import collection_dependencies
from .runtime import run_async

logger = logging.getLogger(__name__)


class DiscoveryJobEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discovery_run_id: UUID
    topic_run_id: UUID | None = None
    query_id: UUID
    payload: dict


async def execute_discovery(envelope: DiscoveryJobEnvelope, runtime: WorkerSettings):
    payload = envelope.payload
    request = DiscoveryRequest(
        search_query_id=envelope.query_id,
        collection_run_id=envelope.discovery_run_id,
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
    envelope: DiscoveryJobEnvelope | None = None
    runtime = settings
    try:
        envelope = DiscoveryJobEnvelope.model_validate(payload)
        runtime = runtime or WorkerSettings()
        result = await execute_discovery(envelope, runtime)
        engine = create_database_engine(runtime.database_url.get_secret_value())
        try:
            await DiscoveryOperationsService(create_session_factory(engine)).refresh_batch_for_run(
                envelope.discovery_run_id
            )
        finally:
            await engine.dispose()
        return result
    except (
        ValidationError,
        ValueError,
        SearchQueryNotFound,
        SearchQueryDisabled,
        InvalidDiscoveryMode,
    ) as error:
        run_value = envelope.discovery_run_id if envelope else payload.get("discovery_run_id")
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
            envelope.query_id if envelope else payload.get("query_id"),
            type(error).__name__,
            location,
            message,
        )
        if run_value and runtime is not None:
            engine = create_database_engine(runtime.database_url.get_secret_value())
            try:
                await DiscoveryOperationsService(create_session_factory(engine)).finalize_failure(
                    UUID(str(run_value)),
                    error_code="invalid_discovery_request",
                    safe_message=message,
                )
            finally:
                await engine.dispose()
        return None


async def _finalize_retry_exhausted(original_message: dict) -> None:
    payload = original_message.get("kwargs", {})
    envelope = DiscoveryJobEnvelope.model_validate(payload)
    runtime = WorkerSettings()
    engine = create_database_engine(runtime.database_url.get_secret_value())
    try:
        await DiscoveryOperationsService(create_session_factory(engine)).finalize_failure(
            envelope.discovery_run_id,
            error_code="retry_exhausted",
            safe_message="Discovery worker retries exhausted",
        )
    finally:
        await engine.dispose()


@dramatiq.actor(queue_name="maintenance", max_retries=0)
def finalize_youtube_discovery_retry_exhausted(original_message: dict, _retry_metadata: dict):
    asyncio.run(_finalize_retry_exhausted(original_message))


@dramatiq.actor(
    queue_name="youtube_discovery",
    max_retries=2,
    min_backoff=5000,
    on_retry_exhausted="finalize_youtube_discovery_retry_exhausted",
)
def run_youtube_discovery(**payload):
    result = run_async(lambda: execute_discovery_safely(payload))
    logger.info(
        "youtube_discovery_actor_finished status=%s", getattr(result, "status", "permanent_error")
    )
