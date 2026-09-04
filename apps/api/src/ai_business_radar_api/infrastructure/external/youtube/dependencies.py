"""YouTube client construction without import-time network state."""

from collections.abc import AsyncIterator

from fastapi import HTTPException, Request, status

from .client import YouTubeClient


async def get_youtube_client(request: Request) -> AsyncIterator[YouTubeClient]:
    settings = request.app.state.settings
    if settings.youtube_api_key is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "YouTube API is not configured")
    client = YouTubeClient(
        settings.youtube_api_key.get_secret_value(),
        base_url=settings.youtube_api_base_url,
        timeout_seconds=settings.youtube_http_timeout_seconds,
        max_retries=settings.youtube_max_retries,
    )
    async with client:
        yield client
