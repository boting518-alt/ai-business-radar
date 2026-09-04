"""Admin-only manual YouTube discovery trigger."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...infrastructure.auth import RequiredAdmin
from ...infrastructure.external.youtube import YouTubeClient
from ...infrastructure.external.youtube.dependencies import get_youtube_client
from ...infrastructure.queue import JobEnqueuer, QueuedJob, QueueUnavailableError
from ...services.youtube_comments import (
    CanonicalVideosNotFound,
    CommentCollectionRequest,
    CommentCollectionResult,
    YouTubeCommentCollectionService,
)
from ...services.youtube_discovery import (
    DiscoveryRequest,
    DiscoveryResult,
    InvalidDiscoveryMode,
    SearchQueryDisabled,
    SearchQueryNotFound,
    YouTubeDiscoveryService,
)
from ...services.youtube_metadata import (
    MetadataCollectionRequest,
    MetadataCollectionResult,
    YouTubeMetadataCollectionService,
)

router = APIRouter(prefix="/admin/youtube", tags=["admin", "youtube"])


def get_job_enqueuer(request: Request) -> JobEnqueuer:
    redis_url = request.app.state.settings.redis_url
    if redis_url is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Collection queue is not configured"
        )
    return JobEnqueuer(redis_url.get_secret_value())


def enqueue_job(enqueuer: JobEnqueuer, *, queue: str, actor: str, payload: dict) -> QueuedJob:
    try:
        job_id = enqueuer.enqueue(queue=queue, actor=actor, payload=payload)
    except QueueUnavailableError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Collection queue is unavailable"
        ) from error
    return QueuedJob(job_id=job_id, queue=queue)


def get_youtube_discovery_service(
    request: Request,
    youtube: Annotated[YouTubeClient, Depends(get_youtube_client)],
) -> YouTubeDiscoveryService:
    factory = getattr(request.app.state, "database_session_factory", None)
    if factory is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    return YouTubeDiscoveryService(
        factory,
        youtube,
        max_quota_units_per_run=request.app.state.settings.youtube_discovery_max_quota_units_per_run,
    )


def get_youtube_metadata_service(
    request: Request,
    youtube: Annotated[YouTubeClient, Depends(get_youtube_client)],
) -> YouTubeMetadataCollectionService:
    factory = getattr(request.app.state, "database_session_factory", None)
    if factory is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    return YouTubeMetadataCollectionService(factory, youtube)


def get_youtube_comment_service(
    request: Request,
    youtube: Annotated[YouTubeClient, Depends(get_youtube_client)],
) -> YouTubeCommentCollectionService:
    factory = getattr(request.app.state, "database_session_factory", None)
    if factory is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    return YouTubeCommentCollectionService(
        factory,
        youtube,
        max_quota_units_per_run=request.app.state.settings.youtube_comment_max_quota_units_per_run,
    )


@router.post("/discovery", response_model=DiscoveryResult)
async def trigger_discovery(
    discovery_request: DiscoveryRequest,
    _: RequiredAdmin,
    service: Annotated[YouTubeDiscoveryService, Depends(get_youtube_discovery_service)],
) -> DiscoveryResult:
    try:
        return await service.discover(discovery_request)
    except SearchQueryNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Search query was not found") from error
    except (SearchQueryDisabled, InvalidDiscoveryMode) as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error


@router.post("/metadata", response_model=MetadataCollectionResult)
async def collect_metadata(
    metadata_request: MetadataCollectionRequest,
    _: RequiredAdmin,
    service: Annotated[YouTubeMetadataCollectionService, Depends(get_youtube_metadata_service)],
) -> MetadataCollectionResult:
    return await service.collect(metadata_request)


@router.post("/comments", response_model=CommentCollectionResult)
async def collect_comments(
    comment_request: CommentCollectionRequest,
    _: RequiredAdmin,
    service: Annotated[YouTubeCommentCollectionService, Depends(get_youtube_comment_service)],
) -> CommentCollectionResult:
    try:
        return await service.collect(comment_request)
    except CanonicalVideosNotFound as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "One or more canonical videos were not found or are ineligible",
        ) from error


@router.post("/discovery/jobs", response_model=QueuedJob, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_discovery(
    discovery_request: DiscoveryRequest,
    _: RequiredAdmin,
    enqueuer: Annotated[JobEnqueuer, Depends(get_job_enqueuer)],
) -> QueuedJob:
    return enqueue_job(
        enqueuer,
        queue="youtube_discovery",
        actor="run_youtube_discovery",
        payload=discovery_request.model_dump(mode="json", exclude_none=True),
    )


@router.post("/metadata/jobs", response_model=QueuedJob, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_metadata(
    metadata_request: MetadataCollectionRequest,
    _: RequiredAdmin,
    enqueuer: Annotated[JobEnqueuer, Depends(get_job_enqueuer)],
) -> QueuedJob:
    return enqueue_job(
        enqueuer,
        queue="youtube_metadata",
        actor="run_youtube_metadata_collection",
        payload=metadata_request.model_dump(mode="json", exclude_none=True),
    )


@router.post("/comments/jobs", response_model=QueuedJob, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_comments(
    comment_request: CommentCollectionRequest,
    _: RequiredAdmin,
    enqueuer: Annotated[JobEnqueuer, Depends(get_job_enqueuer)],
) -> QueuedJob:
    return enqueue_job(
        enqueuer,
        queue="youtube_comments",
        actor="run_youtube_comment_collection",
        payload=comment_request.model_dump(mode="json", exclude_none=True),
    )
