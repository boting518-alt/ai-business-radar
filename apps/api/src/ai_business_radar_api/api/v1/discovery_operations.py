"""Admin-only Discovery Operations Console API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ...infrastructure.auth import RequiredAdmin
from ...infrastructure.queue import JobEnqueuer, QueueUnavailableError
from ...services.discovery_operations import (
    DiscoveryConflict,
    DiscoveryNotFound,
    DiscoveryOperationsService,
    DiscoveryQueryConfig,
    DiscoveryQueryCreate,
    DiscoveryQueryPatch,
    DiscoveryRunPage,
    DiscoverySystemStatus,
    DiscoveryTopicCreate,
    DiscoveryTopicDetail,
    DiscoveryTopicPatch,
    DiscoveryTopicRunDetail,
    DiscoveryTopicRunSummary,
    DiscoveryTopicSummary,
    StaleRunRecoveryRequest,
    StaleRunRecoveryResult,
)

router = APIRouter(prefix="/admin/discovery", tags=["admin", "discovery"])


def service(request: Request) -> DiscoveryOperationsService:
    factory = getattr(request.app.state, "database_session_factory", None)
    if not factory:
        raise HTTPException(503, "Database is not configured")
    return DiscoveryOperationsService(factory)


def enqueuer(request: Request) -> JobEnqueuer:
    url = request.app.state.settings.redis_url
    if not url:
        raise HTTPException(503, "Collection queue is not configured")
    return JobEnqueuer(url.get_secret_value())


def translate(error: Exception):
    if isinstance(error, DiscoveryNotFound):
        raise HTTPException(404, "Discovery resource not found") from error
    raise HTTPException(409, str(error)) from error


@router.get("/topics", response_model=list[DiscoveryTopicSummary])
async def topics(_: RequiredAdmin, ops: Annotated[DiscoveryOperationsService, Depends(service)]):
    return await ops.list()


@router.post("/topics", response_model=DiscoveryTopicDetail, status_code=201)
async def create_topic(
    body: DiscoveryTopicCreate,
    user: RequiredAdmin,
    ops: Annotated[DiscoveryOperationsService, Depends(service)],
):
    try:
        return await ops.create(user.user_profile_id, body)
    except DiscoveryConflict as error:
        translate(error)


@router.get("/topics/{topic_id}", response_model=DiscoveryTopicDetail)
async def topic(
    topic_id: UUID, _: RequiredAdmin, ops: Annotated[DiscoveryOperationsService, Depends(service)]
):
    try:
        return await ops.detail(topic_id)
    except DiscoveryNotFound as error:
        translate(error)


@router.patch("/topics/{topic_id}", response_model=DiscoveryTopicDetail)
async def patch_topic(
    topic_id: UUID,
    body: DiscoveryTopicPatch,
    _: RequiredAdmin,
    ops: Annotated[DiscoveryOperationsService, Depends(service)],
):
    try:
        return await ops.patch(topic_id, body)
    except DiscoveryNotFound as error:
        translate(error)


@router.post("/topics/{topic_id}/pause", response_model=DiscoveryTopicDetail)
async def pause(
    topic_id: UUID, _: RequiredAdmin, ops: Annotated[DiscoveryOperationsService, Depends(service)]
):
    return await ops.patch(topic_id, DiscoveryTopicPatch(status="paused"))


@router.post("/topics/{topic_id}/resume", response_model=DiscoveryTopicDetail)
async def resume(
    topic_id: UUID, _: RequiredAdmin, ops: Annotated[DiscoveryOperationsService, Depends(service)]
):
    return await ops.patch(topic_id, DiscoveryTopicPatch(status="active"))


@router.post("/topics/{topic_id}/archive", response_model=DiscoveryTopicDetail)
async def archive(
    topic_id: UUID, _: RequiredAdmin, ops: Annotated[DiscoveryOperationsService, Depends(service)]
):
    return await ops.patch(topic_id, DiscoveryTopicPatch(status="archived"))


@router.post("/topics/{topic_id}/duplicate", response_model=DiscoveryTopicDetail, status_code=201)
async def duplicate(
    topic_id: UUID,
    user: RequiredAdmin,
    ops: Annotated[DiscoveryOperationsService, Depends(service)],
):
    return await ops.duplicate(topic_id, user.user_profile_id)


async def queue(
    query_id: UUID, ops: DiscoveryOperationsService, jobs: JobEnqueuer, trigger="manual"
):
    run = None
    try:
        run, payload = await ops.queue_run(query_id, trigger)
        message = jobs.enqueue(
            queue="youtube_discovery", actor="run_youtube_discovery", payload=payload
        )
        await ops.mark_message(run.id, str(message))
        run.worker_message_id = str(message)
        return run
    except (DiscoveryConflict, DiscoveryNotFound) as error:
        translate(error)
    except QueueUnavailableError as error:
        if run is not None:
            await ops.mark_enqueue_failed(run.id)
        raise HTTPException(503, "Collection queue is unavailable") from error


@router.post("/queries/{query_id}/run", status_code=202)
async def run_query(
    query_id: UUID,
    _: RequiredAdmin,
    ops: Annotated[DiscoveryOperationsService, Depends(service)],
    jobs: Annotated[JobEnqueuer, Depends(enqueuer)],
):
    return await queue(query_id, ops, jobs)


@router.post("/queries", response_model=DiscoveryQueryConfig, status_code=201)
async def create_query(
    body: DiscoveryQueryCreate,
    _: RequiredAdmin,
    ops: Annotated[DiscoveryOperationsService, Depends(service)],
):
    try:
        return await ops.add_query(body)
    except (DiscoveryConflict, DiscoveryNotFound) as error:
        translate(error)


@router.patch("/queries/{query_id}", response_model=DiscoveryQueryConfig)
async def patch_query(
    query_id: UUID,
    body: DiscoveryQueryPatch,
    _: RequiredAdmin,
    ops: Annotated[DiscoveryOperationsService, Depends(service)],
):
    try:
        return await ops.patch_query(query_id, body)
    except (DiscoveryConflict, DiscoveryNotFound) as error:
        translate(error)


@router.post("/topics/{topic_id}/run", response_model=DiscoveryTopicRunDetail, status_code=202)
async def run_topic(
    topic_id: UUID,
    _: RequiredAdmin,
    ops: Annotated[DiscoveryOperationsService, Depends(service)],
    jobs: Annotated[JobEnqueuer, Depends(enqueuer)],
):
    try:
        batch, payloads = await ops.create_topic_run(topic_id, "manual")
    except (DiscoveryConflict, DiscoveryNotFound) as error:
        translate(error)
    for run_id, payload in payloads:
        try:
            message = jobs.enqueue(
                queue="youtube_discovery", actor="run_youtube_discovery", payload=payload
            )
            await ops.mark_message(run_id, str(message))
            await ops.increment_queued(batch.id)
        except QueueUnavailableError:
            await ops.mark_enqueue_failed(run_id)
    return await ops.refresh_topic_run(batch.id)


@router.get("/topic-runs/{topic_run_id}", response_model=DiscoveryTopicRunDetail)
async def topic_run(
    topic_run_id: UUID,
    _: RequiredAdmin,
    ops: Annotated[DiscoveryOperationsService, Depends(service)],
):
    try:
        return await ops.refresh_topic_run(topic_run_id)
    except DiscoveryNotFound as error:
        translate(error)


@router.get("/topic-runs/{topic_run_id}/runs")
async def topic_run_children(
    topic_run_id: UUID,
    _: RequiredAdmin,
    ops: Annotated[DiscoveryOperationsService, Depends(service)],
):
    try:
        return (await ops.topic_run_detail(topic_run_id)).runs
    except DiscoveryNotFound as error:
        translate(error)


@router.get("/topics/{topic_id}/runs", response_model=list[DiscoveryTopicRunSummary])
async def topic_run_history(
    topic_id: UUID, _: RequiredAdmin, ops: Annotated[DiscoveryOperationsService, Depends(service)]
):
    try:
        return await ops.topic_runs(topic_id)
    except DiscoveryNotFound as error:
        translate(error)


@router.get("/runs", response_model=DiscoveryRunPage)
async def runs(
    _: RequiredAdmin,
    ops: Annotated[DiscoveryOperationsService, Depends(service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    run_status: str | None = Query(None, alias="status"),
    topic_id: UUID | None = None,
    query_id: UUID | None = None,
):
    return await ops.runs(
        page=page, page_size=page_size, status=run_status, topic_id=topic_id, query_id=query_id
    )


@router.post("/runs/recover-stale", response_model=StaleRunRecoveryResult)
async def recover_stale_runs(
    body: StaleRunRecoveryRequest,
    _: RequiredAdmin,
    ops: Annotated[DiscoveryOperationsService, Depends(service)],
):
    return await ops.recover_stale(body)


@router.get("/runs/{run_id}")
async def run_detail(
    run_id: UUID, _: RequiredAdmin, ops: Annotated[DiscoveryOperationsService, Depends(service)]
):
    try:
        return await ops.run_detail(run_id)
    except DiscoveryNotFound as error:
        translate(error)


@router.get("/system-status", response_model=DiscoverySystemStatus)
async def system_status(request: Request, _: RequiredAdmin):
    settings = request.app.state.settings
    target = settings.runtime_target
    return DiscoverySystemStatus(
        redis="configured" if settings.redis_url else "unconfigured",
        youtube_api="configured" if settings.youtube_api_key else "unconfigured",
        openai_api="configured" if settings.openai_api_key else "unconfigured",
        runtime_profile=target.runtime_profile,
        database_host=target.database_host,
        database_name=target.database_name,
        redis_host=target.redis_host,
        config_fingerprint=target.fingerprint,
    )
