"""Admin-only manual YouTube discovery trigger."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...infrastructure.auth import RequiredAdmin
from ...infrastructure.external.youtube import YouTubeClient
from ...infrastructure.external.youtube.dependencies import get_youtube_client
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
