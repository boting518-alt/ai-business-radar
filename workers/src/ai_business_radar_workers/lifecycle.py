from contextlib import asynccontextmanager

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.external.youtube import YouTubeClient

from .config import WorkerSettings


@asynccontextmanager
async def collection_dependencies(settings: WorkerSettings):
    engine = create_database_engine(settings.database_url.get_secret_value())
    youtube = YouTubeClient(
        settings.youtube_api_key.get_secret_value(),
        base_url=settings.youtube_api_base_url,
        timeout_seconds=settings.youtube_http_timeout_seconds,
        max_retries=settings.youtube_max_retries,
    )
    try:
        async with youtube:
            yield create_session_factory(engine), youtube
    finally:
        await engine.dispose()
